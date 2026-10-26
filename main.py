"""
HTTP API and static host for the Weekly Review Pulse (Vercel entrypoint: exports `app`).

Local:   uvicorn main:app --reload
Vercel:  zero-config FastAPI; static files in public/ are served by the CDN, /api/* is handled here.

The pipeline is exposed as stateless steps (collect, clean, analyze, insights, pulse) which the browser calls in
sequence, so every request stays well inside serverless time limits.
"""
import hmac
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services import gemini_client, pipeline_api
from services.config_loader import get_config
from services.gemini_client import LLMError
from services.store import get_store, summarize

app = FastAPI(title="Weekly Review Pulse", docs_url=None, redoc_url=None, openapi_url=None)


# ---------------------------------------------------------------------------
# Auth: optional shared password (set APP_PASSWORD). Strongly recommended on a public deployment,
# because the API spends Gemini credits and can send email.
# ---------------------------------------------------------------------------
def auth_required() -> bool:
    return bool(get_config("APP_PASSWORD"))


def require_auth(x_access_key: Optional[str] = Header(default=None)):
    expected = get_config("APP_PASSWORD")
    if expected and not (x_access_key and hmac.compare_digest(x_access_key.encode(), expected.encode())):
        raise HTTPException(status_code=401, detail="Access key required.")


class LoginBody(BaseModel):
    password: str


@app.post("/api/login")
def login(body: LoginBody):
    expected = get_config("APP_PASSWORD")
    if expected and not hmac.compare_digest(body.password.encode(), expected.encode()):
        time.sleep(0.8)  # slow down guessing
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"ok": True}


@app.get("/api/config")
def config():
    models = {"analysis": gemini_client.ANALYSIS_MODEL, "synthesis": gemini_client.SYNTHESIS_MODEL}
    pricing = []
    for key, role in (("analysis", "Review classification"), ("synthesis", "Discovery, quotes, actions, pulse, email")):
        p_in, p_out = gemini_client.price_for(models[key])
        pricing.append({"model": models[key], "role": role, "input": p_in, "output": p_out})
    return {
        "geminiReady": bool(get_config("GEMINI_API_KEY")),
        "authRequired": auth_required(),
        "persistent": get_store().persistent,
        "defaultRecipient": bool(get_config("EMAIL_TO")),
        "emailConfigured": all(get_config(k) for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")),
        "models": models,
        "pricing": pricing,
        "pricingNote": "Paid-tier standard text pricing from Google. gemini-3.6-flash rises to $1.50 input and $7.50 output on 1 Jan 2027.",
    }


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------
def guarded(fn, *args, **kwargs):
    """Run a pipeline step, capturing LLM usage and translating failures into clean HTTP errors."""
    try:
        with gemini_client.capture() as calls:
            result = fn(*args, **kwargs)
        return {**result, "calls": calls} if isinstance(result, dict) else {"result": result, "calls": calls}
    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


class CollectBody(BaseModel):
    source: str = "scrape"
    count: int = 500
    csv: Optional[str] = None


class CleanBody(BaseModel):
    reviews: List[Dict[str, Any]]
    weeks: Optional[int] = None


class AnalyzeBody(BaseModel):
    reviews: List[Dict[str, Any]]


class InsightsBody(BaseModel):
    themes: List[Dict[str, Any]]


class PulseBody(BaseModel):
    themes: List[Dict[str, Any]]
    insights: Dict[str, Any]


class EmailBody(BaseModel):
    pulse_md: str
    pulse_txt: Optional[str] = None
    recipient: Optional[str] = None
    send: bool = False


@app.post("/api/pipeline/collect", dependencies=[Depends(require_auth)])
def step_collect(body: CollectBody):
    count = max(50, min(body.count, 1000))
    data = guarded(pipeline_api.collect, body.source, count, body.csv)
    return {"reviews": data["result"]}


@app.post("/api/pipeline/clean", dependencies=[Depends(require_auth)])
def step_clean(body: CleanBody):
    return guarded(pipeline_api.clean, body.reviews, body.weeks)


@app.post("/api/pipeline/analyze", dependencies=[Depends(require_auth)])
def step_analyze(body: AnalyzeBody):
    if not body.reviews:
        raise HTTPException(status_code=400, detail="No reviews to analyze.")
    return guarded(pipeline_api.analyze, body.reviews)


@app.post("/api/pipeline/insights", dependencies=[Depends(require_auth)])
def step_insights(body: InsightsBody):
    return guarded(pipeline_api.insights, body.themes)


@app.post("/api/pipeline/pulse", dependencies=[Depends(require_auth)])
def step_pulse(body: PulseBody):
    return guarded(pipeline_api.pulse, body.themes, body.insights)


@app.post("/api/email", dependencies=[Depends(require_auth)])
def step_email(body: EmailBody):
    if body.send and not (body.recipient or get_config("EMAIL_TO")):
        raise HTTPException(status_code=400, detail="Enter a recipient to send.")
    try:
        with gemini_client.capture() as calls:
            out = pipeline_api.email(body.pulse_md, body.pulse_txt or "", body.recipient, body.send)
        return {**out, "calls": calls}
    except RuntimeError as e:  # SMTP / config problems
        raise HTTPException(status_code=400, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {e}")


# ---------------------------------------------------------------------------
# Live feed
# ---------------------------------------------------------------------------
_live_cache: Dict[int, Any] = {}


@app.get("/api/live", dependencies=[Depends(require_auth)])
def live_feed(count: int = Query(50, ge=10, le=100), fresh: bool = False):
    hit = _live_cache.get(count)
    if hit and not fresh and time.time() - hit[0] < 20:
        return {"reviews": hit[1], "cached": True, "fetched_at": hit[0]}
    try:
        data = pipeline_api.live(count)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Could not reach Google Play: {e}")
    _live_cache[count] = (time.time(), data)
    return {"reviews": data, "cached": False, "fetched_at": time.time()}


# ---------------------------------------------------------------------------
# Run history (optional persistence)
# ---------------------------------------------------------------------------
@app.get("/api/runs", dependencies=[Depends(require_auth)])
def list_runs():
    store = get_store()
    return {"persistent": store.persistent, "runs": store.list_runs()}


@app.get("/api/runs/{run_id}", dependencies=[Depends(require_auth)])
def get_run(run_id: str):
    bundle = get_store().get_run(run_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Run not found.")
    return bundle


@app.put("/api/runs/{run_id}", dependencies=[Depends(require_auth)])
def put_run(run_id: str, bundle: Dict[str, Any]):
    if bundle.get("id") != run_id:
        raise HTTPException(status_code=400, detail="Run id mismatch.")
    store = get_store()
    store.put_run(bundle)
    return {"ok": True, "persistent": store.persistent, "summary": summarize(bundle)}


# ---------------------------------------------------------------------------
# Static frontend (local dev; on Vercel public/ is served by the CDN before reaching this app)
# ---------------------------------------------------------------------------
_public = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
if os.path.isdir(_public):
    app.mount("/", StaticFiles(directory=_public, html=True), name="static")
