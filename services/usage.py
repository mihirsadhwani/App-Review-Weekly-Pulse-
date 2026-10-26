"""Reads the LLM audit log and summarises token usage and estimated API cost."""
import json
import os
import re
from typing import Optional

import pandas as pd

from services.gemini_client import LOG_PATH, cost_usd, price_for, ANALYSIS_MODEL, SYNTHESIS_MODEL

COLUMNS = ["ts", "step", "model", "prompt_tokens", "output_tokens", "cost_usd", "latency_s"]


def _step(label: str) -> str:
    return re.sub(r"(_\d+)?(_retry)?$", "", label or "unknown")


def load_calls(path: str = LOG_PATH) -> pd.DataFrame:
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                p, o = int(r.get("prompt_tokens", 0) or 0), int(r.get("output_tokens", 0) or 0)
                rows.append({
                    "ts": r.get("ts"),
                    "step": _step(r.get("label")),
                    "model": r.get("model"),
                    "prompt_tokens": p,
                    "output_tokens": o,
                    "cost_usd": r.get("cost_usd") if r.get("cost_usd") is not None else cost_usd(r.get("model", ""), p, o),
                    "latency_s": r.get("latency_s", 0),
                })
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"])
    return df


def pricing_table() -> pd.DataFrame:
    rows = []
    for model, role in ((ANALYSIS_MODEL, "Review classification"), (SYNTHESIS_MODEL, "Discovery, quotes, actions, pulse, email")):
        p_in, p_out = price_for(model)
        rows.append({"Model": model, "Used for": role, "Input $/1M": p_in, "Output $/1M": p_out})
    return pd.DataFrame(rows)


def fmt_usd(v: Optional[float]) -> str:
    if v is None:
        return "-"
    return f"${v:,.2f}" if v >= 1 else f"${v:,.4f}"
