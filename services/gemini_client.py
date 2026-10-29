"""
AI service layer. All LLM calls in the pipeline go through this module.

- Analytical tasks (theme discovery, classification, insights) use `generate_json`
  with schema-constrained output.
- Composition tasks (pulse, email) use `generate_text`.
- Retries with exponential backoff on transient errors (429 / 5xx).
- Token usage and latency are tracked per process and logged to a JSONL audit file.
"""
import json
import logging
import os
import re
import threading
import contextlib
import contextvars
import time
from datetime import datetime, date
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from services.config_loader import get_config

logger = logging.getLogger("pulse.ai")

# Fast, low-cost model for high-volume analytical calls; stronger model for synthesis.
ANALYSIS_MODEL = get_config("GEMINI_ANALYSIS_MODEL", "gemini-3.5-flash-lite")
SYNTHESIS_MODEL = get_config("GEMINI_SYNTHESIS_MODEL", "gemini-3.6-flash")

MAX_RETRIES = 3
LOG_BASE = "/tmp" if os.environ.get("VERCEL") else "storage"
LOG_PATH = os.path.join(LOG_BASE, "logs", "llm_calls.jsonl")
_capture: contextvars.ContextVar = contextvars.ContextVar("llm_capture", default=None)


@contextlib.contextmanager
def capture():
    """Collect a record of every LLM call made inside the block (used for per-request cost reporting)."""
    calls: list = []
    token = _capture.set(calls)
    try:
        yield calls
    finally:
        _capture.reset(token)
TOKEN_BUDGET = int(get_config("LLM_TOKEN_BUDGET", "2000000"))


_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]+")


KEY_HELP = (
    "Gemini rejected the API key (401/403). Check that GEMINI_API_KEY is a current Gemini API key from "
    "https://aistudio.google.com/apikey, that it was copied in full, and that it has not been revoked or restricted. "
    "Update it in your environment (Vercel: Project Settings, Environment Variables) and redeploy."
)


class LLMError(RuntimeError):
    pass


# USD per 1M tokens: (input, output). Output includes thinking tokens.
# Source: https://ai.google.dev/gemini-api/docs/pricing (paid tier, standard, text). Verify before relying on it.
_FLASH_PROMO_END = date(2026, 12, 31)
PRICING = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3-flash-preview": (0.50, 3.00),
}
# Flash models whose price rises on 2027-01-01: (price until promo end, price after)
PRICING_STEPPED = {
    "gemini-3.6-flash": ((0.75, 3.75), (1.50, 7.50)),
    "gemini-3.8-flash": ((0.75, 3.75), (1.50, 7.50)),
}
FALLBACK_PRICE = (0.75, 3.75)


def price_for(model: str, on: Optional[date] = None) -> tuple:
    on = on or date.today()
    if model in PRICING_STEPPED:
        before, after = PRICING_STEPPED[model]
        return before if on <= _FLASH_PROMO_END else after
    return PRICING.get(model, FALLBACK_PRICE)


def cost_usd(model: str, prompt_tokens: int, output_tokens: int, on: Optional[date] = None) -> float:
    p_in, p_out = price_for(model, on)
    return (prompt_tokens * p_in + output_tokens * p_out) / 1_000_000


class TokenUsage:
    def __init__(self):
        self._lock = threading.Lock()
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self.cost = 0.0
        self.by_model: Dict[str, Dict[str, float]] = {}

    def add(self, model: str, prompt: int, output: int):
        with self._lock:
            self.prompt_tokens += prompt
            self.output_tokens += output
            self.calls += 1
            c = cost_usd(model, prompt, output)
            self.cost += c
            m = self.by_model.setdefault(model, {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
            m["calls"] += 1
            m["prompt_tokens"] += prompt
            m["output_tokens"] += output
            m["cost_usd"] += c

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.output_tokens

    def snapshot(self) -> Dict[str, Any]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total,
            "cost_usd": round(self.cost, 6),
        }


usage = TokenUsage()
_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = get_config("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            raise LLMError("GEMINI_API_KEY is missing from environment variables and st.secrets.")
        _client = genai.Client(api_key=api_key)
    return _client


def _log_call(label: str, model: str, prompt: str, response: str, latency: float, tokens: Dict[str, int]):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(timespec="seconds"),
                "label": label,
                "model": model,
                "latency_s": round(latency, 2),
                **tokens,
                "prompt": prompt,
                "response": response,
            }, ensure_ascii=False) + "\n")
    except OSError:
        logger.debug("Could not write LLM audit log", exc_info=True)


def _is_transient(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if isinstance(code, int) and (code == 429 or code >= 500):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in ("429", "503", "500", "timeout", "unavailable", "overloaded"))


def _call(prompt: str, model: str, config: types.GenerateContentConfig, label: str) -> str:
    if usage.total >= TOKEN_BUDGET:
        raise LLMError(f"Token budget of {TOKEN_BUDGET} exceeded; aborting run.")

    client = _get_client()
    last_exc: Optional[Exception] = None

    for attempt in range(MAX_RETRIES):
        started = time.time()
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            text = response.text or ""
            meta = response.usage_metadata
            # Thinking tokens are billed as output tokens
            tokens = {
                "prompt_tokens": getattr(meta, "prompt_token_count", 0) or 0,
                "output_tokens": (getattr(meta, "candidates_token_count", 0) or 0)
                + (getattr(meta, "thoughts_token_count", 0) or 0),
            }
            tokens["cost_usd"] = round(cost_usd(model, tokens["prompt_tokens"], tokens["output_tokens"]), 6)
            usage.add(model, tokens["prompt_tokens"], tokens["output_tokens"])
            latency = time.time() - started
            sink = _capture.get()
            if sink is not None:
                sink.append({"step": re.sub(r"(_\d+)?(_retry)?$", "", label), "model": model, "prompt_tokens": tokens["prompt_tokens"],
                             "output_tokens": tokens["output_tokens"], "cost_usd": tokens["cost_usd"], "latency_s": round(latency, 2),
                             "ts": datetime.now().isoformat(timespec="seconds")})
            _log_call(label, model, prompt, text, latency, tokens)
            if not text.strip():
                raise LLMError("Empty response from model.")
            return text
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if getattr(exc, "code", None) in (401, 403):
                # Bad credentials never succeed on retry; fail fast with an actionable message
                raise LLMError(KEY_HELP) from exc
            if attempt < MAX_RETRIES - 1 and (_is_transient(exc) or isinstance(exc, LLMError)):
                delay = 2 ** attempt * 2
                logger.warning("%s failed (%s); retrying in %ss", label, exc, delay)
                time.sleep(delay)
                continue
            break

    raise LLMError(f"{label} failed: {last_exc}")


def _extract_json(text: str) -> Any:
    """Parse JSON, falling back to extracting the outermost object/array from noisy output."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def generate_json(
    prompt: str,
    schema: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    label: str = "json_call",
    thinking: str = "minimal",
    system: str = "You are a senior product analyst at a fintech company. Output only valid JSON. Never use emojis.",
) -> Any:
    """Schema-constrained JSON generation. Re-asks once with a stricter prompt if parsing fails."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
    )
    model = model or ANALYSIS_MODEL

    text = _call(prompt, model, config, label)
    try:
        return _extract_json(text)
    except json.JSONDecodeError:
        retry_prompt = prompt + "\n\nYour previous reply was not valid JSON. Reply with valid JSON only."
        return _extract_json(_call(retry_prompt, model, config, f"{label}_retry"))


def generate_text(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    label: str = "text_call",
    thinking: str = "minimal",
    system: str = "You are a senior product analyst writing for product leadership at a fintech company. Never use emojis.",
) -> str:
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
    )
    return _EMOJI_RE.sub("", _call(prompt, model or SYNTHESIS_MODEL, config, label)).strip()


def generate_with_gemini(prompt: str) -> str:
    """Backwards-compatible helper. Raises LLMError on failure instead of returning an error string."""
    return generate_text(prompt)
