"""
Pipeline orchestration and run archive.

Each run is archived under storage/runs/{run_id}/ (input, cleaned, analysis, output, logs)
and indexed in storage/runs/index.json for the run-history view.
"""
import json
import os
import shutil
import traceback
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

from phase1_review_collection.services.collector import PlayStoreCollector
from phase2_review_cleaning.services.cleaner import ReviewCleaner
from phase3_theme_analysis.services.analyzer import ThemeAnalyzer
from phase4_insight_generation.services.insight_generator import InsightGenerator
from phase5_weekly_pulse.services.pulse_generator import PulseGenerator
from services.csv_ingest import parse_reviews_csv, save_raw_reviews
from services import gemini_client

PACKAGE_ID = "com.nextbillion.groww"

RAW_REVIEWS_PATH = "phase1_review_collection/raw_reviews.json"
REVIEWS_CLEANED_PATH = "phase2_review_cleaning/filtered_reviews.json"
THEME_MAP_PATH = "phase3_theme_analysis/theme_map.json"
INSIGHTS_PATH = "phase4_insight_generation/insights.json"
PULSE_MD_PATH = "phase5_weekly_pulse/weekly_pulse.md"
PULSE_TXT_PATH = "phase5_weekly_pulse/weekly_pulse.txt"
EMAIL_MD_PATH = "phase6_email_delivery/email_draft.md"
EMAIL_TXT_PATH = "phase6_email_delivery/email_draft.txt"

RUNS_DIR = os.path.join("storage", "runs")
INDEX_PATH = os.path.join(RUNS_DIR, "index.json")

STEPS = [
    ("collect", "Collect reviews"),
    ("clean", "Clean and scrub PII"),
    ("analyze", "Discover and classify themes"),
    ("insight", "Select quotes and actions"),
    ("pulse", "Compose weekly pulse"),
]

ARCHIVE_LAYOUT = {
    "input": [RAW_REVIEWS_PATH],
    "cleaned": [REVIEWS_CLEANED_PATH],
    "analysis": [THEME_MAP_PATH, INSIGHTS_PATH],
    "output": [PULSE_MD_PATH, PULSE_TXT_PATH, EMAIL_MD_PATH, EMAIL_TXT_PATH],
}

ProgressFn = Callable[[int, str, str], None]  # (step_index, step_key, state)


def _read_index() -> List[Dict]:
    if not os.path.exists(INDEX_PATH):
        return []
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _write_index(runs: List[Dict]):
    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)


def list_runs() -> List[Dict]:
    return sorted(_read_index(), key=lambda r: r.get("started_at", ""), reverse=True)


def run_dir(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id)


def read_run_file(run_id: str, section: str, filename: str) -> Optional[str]:
    path = os.path.join(run_dir(run_id), section, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _archive(run_id: str):
    for section, paths in ARCHIVE_LAYOUT.items():
        target = os.path.join(run_dir(run_id), section)
        os.makedirs(target, exist_ok=True)
        for p in paths:
            if os.path.exists(p):
                shutil.copy2(p, target)
    log_dir = os.path.join(run_dir(run_id), "logs")
    os.makedirs(log_dir, exist_ok=True)
    if os.path.exists(gemini_client.LOG_PATH):
        shutil.copy2(gemini_client.LOG_PATH, log_dir)


def archive_email(run_id: Optional[str]):
    """Attach the latest email draft to an existing run."""
    if not run_id:
        return
    target = os.path.join(run_dir(run_id), "output")
    os.makedirs(target, exist_ok=True)
    for p in (EMAIL_MD_PATH, EMAIL_TXT_PATH):
        if os.path.exists(p):
            shutil.copy2(p, target)


def run_pipeline(
    source: str = "scrape",
    count: int = 300,
    weeks: Optional[int] = 8,
    csv_bytes: Optional[bytes] = None,
    progress: Optional[ProgressFn] = None,
) -> Dict:
    """Run phases 1-5 and archive the result. Raises on failure after recording a failed run."""
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    record = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "weeks": weeks,
        "status": "running",
        "review_count": 0,
        "theme_count": 0,
        "tokens": 0,
        "cost_usd": 0.0,
        "error": None,
    }
    tokens_before = gemini_client.usage.total
    cost_before = gemini_client.usage.cost

    def step(i: int, state: str):
        if progress:
            progress(i, STEPS[i][0], state)

    current = 0
    try:
        step(0, "running")
        if source == "csv":
            if not csv_bytes:
                raise ValueError("No CSV data provided.")
            save_raw_reviews(parse_reviews_csv(csv_bytes), RAW_REVIEWS_PATH)
        else:
            PlayStoreCollector(PACKAGE_ID, count=count).collect()
        step(0, "done")

        current = 1
        step(1, "running")
        record["review_count"] = ReviewCleaner(RAW_REVIEWS_PATH, REVIEWS_CLEANED_PATH, weeks=weeks).clean()
        if record["review_count"] == 0:
            raise ValueError("No usable reviews remained after cleaning. Try a longer review window.")
        step(1, "done")

        current = 2
        step(2, "running")
        result = ThemeAnalyzer(REVIEWS_CLEANED_PATH, THEME_MAP_PATH).analyze()
        record["theme_count"] = result[0] if result else 0
        step(2, "done")

        current = 3
        step(3, "running")
        InsightGenerator(THEME_MAP_PATH, INSIGHTS_PATH).generate()
        step(3, "done")

        current = 4
        step(4, "running")
        PulseGenerator(THEME_MAP_PATH, INSIGHTS_PATH, PULSE_MD_PATH, PULSE_TXT_PATH).generate()
        step(4, "done")

        record["status"] = "completed"
    except Exception as exc:  # noqa: BLE001
        record["status"] = "failed"
        record["error"] = str(exc)
        step(current, "failed")
        traceback.print_exc()
        raise
    finally:
        record["finished_at"] = datetime.now().isoformat(timespec="seconds")
        record["tokens"] = gemini_client.usage.total - tokens_before
        record["cost_usd"] = round(gemini_client.usage.cost - cost_before, 6)
        if record["status"] == "completed":
            _archive(run_id)
        runs = _read_index()
        runs.append(record)
        _write_index(runs)

    return record
