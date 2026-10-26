"""
Optional persistence for run history.

- Redis over REST (Upstash, also what Vercel's Redis/KV integration provides) when its env vars are present.
- Otherwise a local JSON file store (survives on a dev machine; ephemeral on serverless).

The pipeline itself is stateless; this only keeps finished run bundles so history survives across sessions.
"""
import json
import os
from typing import Any, Dict, List, Optional

import httpx

from services.config_loader import get_config

LIST_KEY = "pulse:runs"
KEEP = 50
SUMMARY_FIELDS = ("id", "started_at", "finished_at", "source", "weeks", "status", "review_count", "raw_count",
                  "theme_count", "tokens", "cost_usd", "error", "calls")


def summarize(bundle: Dict[str, Any]) -> Dict[str, Any]:
    return {k: bundle.get(k) for k in SUMMARY_FIELDS}


class RedisStore:
    persistent = True

    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def _cmd(self, *args) -> Any:
        r = httpx.post(self.url, headers=self.headers, json=list(args), timeout=10)
        r.raise_for_status()
        return r.json().get("result")

    def put_run(self, bundle: Dict[str, Any]):
        rid = bundle["id"]
        self._cmd("SET", f"pulse:run:{rid}", json.dumps(bundle, ensure_ascii=False))
        self._cmd("SET", f"pulse:sum:{rid}", json.dumps(summarize(bundle)))
        self._cmd("LREM", LIST_KEY, 0, rid)
        self._cmd("LPUSH", LIST_KEY, rid)
        self._cmd("LTRIM", LIST_KEY, 0, KEEP - 1)

    def list_runs(self) -> List[Dict[str, Any]]:
        ids = self._cmd("LRANGE", LIST_KEY, 0, KEEP - 1) or []
        if not ids:
            return []
        rows = self._cmd("MGET", *[f"pulse:sum:{i}" for i in ids]) or []
        return [json.loads(r) for r in rows if r]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        raw = self._cmd("GET", f"pulse:run:{run_id}")
        return json.loads(raw) if raw else None


class FileStore:
    persistent = False

    def __init__(self, root: str):
        self.root = root

    def _path(self, run_id: str) -> str:
        safe = "".join(c for c in run_id if c.isalnum() or c in "_-")
        return os.path.join(self.root, f"{safe}.json")

    def put_run(self, bundle: Dict[str, Any]):
        os.makedirs(self.root, exist_ok=True)
        with open(self._path(bundle["id"]), "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False)

    def list_runs(self) -> List[Dict[str, Any]]:
        if not os.path.isdir(self.root):
            return []
        rows = []
        for name in os.listdir(self.root):
            try:
                with open(os.path.join(self.root, name), "r", encoding="utf-8") as f:
                    rows.append(summarize(json.load(f)))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(rows, key=lambda r: r.get("started_at") or "", reverse=True)[:KEEP]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            with open(self._path(run_id), "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None


def get_store():
    url = get_config("KV_REST_API_URL") or get_config("UPSTASH_REDIS_REST_URL")
    token = get_config("KV_REST_API_TOKEN") or get_config("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return RedisStore(url, token)
    root = os.path.join("/tmp" if os.environ.get("VERCEL") else "storage", "runs_api")
    return FileStore(root)
