"""
Stateless pipeline steps for the HTTP API.

Each step takes the previous step's output as input and returns its own output, so a run can be driven from the
browser as a sequence of short requests. This fits serverless time limits and needs no shared storage between calls.
Phases still use their file-based interfaces; every step works inside a throw-away temp directory.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phase1_review_collection.services.collector import PlayStoreCollector, fetch_latest
from phase2_review_cleaning.services.cleaner import ReviewCleaner, scrub_pii
from phase3_theme_analysis.services.analyzer import ThemeAnalyzer
from phase4_insight_generation.services.insight_generator import InsightGenerator
from phase5_weekly_pulse.services.pulse_generator import PulseGenerator
from phase6_email_delivery.services.email_sender import EmailSender
from services.csv_ingest import parse_reviews_csv

PACKAGE_ID = "com.nextbillion.groww"
MAX_REVIEWS = 300


def _write(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _read(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect(source: str, count: int = 500, csv_text: Optional[str] = None) -> List[Dict[str, Any]]:
    if source == "csv":
        if not csv_text:
            raise ValueError("No CSV data provided.")
        return parse_reviews_csv(csv_text)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "raw.json")
        PlayStoreCollector(PACKAGE_ID, count=count).collect(out)
        return _read(out)


def clean(reviews: List[Dict[str, Any]], weeks: Optional[int]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        raw, out = os.path.join(d, "raw.json"), os.path.join(d, "clean.json")
        _write(raw, reviews)
        ReviewCleaner(raw, out, weeks=weeks, max_reviews=MAX_REVIEWS).clean()
        cleaned = _read(out)["reviews"]
    return {"raw_count": len(reviews), "reviews": cleaned}


def analyze(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        inp, out = os.path.join(d, "clean.json"), os.path.join(d, "themes.json")
        _write(inp, {"review_count": len(reviews), "reviews": reviews})
        ThemeAnalyzer(inp, out).analyze()
        return {"themes": _read(out)["themes"]}


def insights(themes: List[Dict[str, Any]]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        inp, out = os.path.join(d, "themes.json"), os.path.join(d, "insights.json")
        _write(inp, {"theme_count": len(themes), "themes": themes})
        data = InsightGenerator(inp, out).generate()
    return {"themes": data["themes"], "action_ideas": data["action_ideas"]}


def pulse(themes: List[Dict[str, Any]], insight_data: Dict[str, Any]) -> Dict[str, str]:
    with tempfile.TemporaryDirectory() as d:
        tm, ins = os.path.join(d, "themes.json"), os.path.join(d, "insights.json")
        md, txt = os.path.join(d, "pulse.md"), os.path.join(d, "pulse.txt")
        _write(tm, {"theme_count": len(themes), "themes": [{"theme_id": t["theme_id"], "review_count": t.get("review_count", 0)} for t in themes]})
        _write(ins, insight_data)
        md_content, txt_content = PulseGenerator(tm, ins, md, txt).generate()
    return {"markdown": md_content, "text": txt_content}


def email(pulse_md: str, pulse_txt: str, recipient: Optional[str], send: bool) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        md_in, txt_in = os.path.join(d, "pulse.md"), os.path.join(d, "pulse.txt")
        out_md, out_txt = os.path.join(d, "email.md"), os.path.join(d, "email.txt")
        for path, content in ((md_in, pulse_md), (txt_in, pulse_txt or pulse_md)):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        EmailSender(md_in, out_md, out_txt).process(send_mode=send, recipient=recipient)
        with open(out_txt, "r", encoding="utf-8") as f:
            draft = f.read()
    return {"draft": draft, "sent": bool(send)}


def live(count: int) -> List[Dict[str, Any]]:
    data = fetch_latest(PACKAGE_ID, count)
    for r in data:
        r["review_text"] = scrub_pii(r.get("review_text") or "")
        # The scraper returns naive local time; send an unambiguous UTC timestamp so every browser shows the right time.
        try:
            r["review_date"] = datetime.fromisoformat(r["review_date"]).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
    return data
