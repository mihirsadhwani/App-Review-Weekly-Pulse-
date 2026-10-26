"""Phase 1 fallback: convert an uploaded CSV into the raw review schema (no pandas, keeps the serverless bundle small)."""
import csv
import io
import json
import os
from typing import List, Dict, Any, Union

COLUMN_ALIASES = {
    "reviewId": ["reviewid", "review_id", "id"],
    "rating": ["rating", "score", "stars"],
    "review_text": ["review_text", "text", "review", "content", "body"],
    "review_date": ["review_date", "date", "at", "created_at", "timestamp"],
}


def parse_reviews_csv(data: Union[bytes, str]) -> List[Dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace") if isinstance(data, bytes) else data
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")
    lookup = {c.strip().lower(): c for c in reader.fieldnames if c}

    mapping = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                mapping[target] = lookup[alias]
                break

    missing = [f for f in ("rating", "review_text") if f not in mapping]
    if missing:
        raise ValueError(
            f"CSV is missing required column(s): {', '.join(missing)}. "
            "Expected columns: rating, review_text and optionally reviewId, review_date."
        )

    reviews = []
    for idx, row in enumerate(reader):
        body = (row.get(mapping["review_text"]) or "").strip()
        if not body:
            continue
        try:
            rating = int(float(row.get(mapping["rating"])))
        except (TypeError, ValueError):
            rating = None
        rid = (row.get(mapping["reviewId"]) or "").strip() if "reviewId" in mapping else ""
        date = (row.get(mapping["review_date"]) or "").strip() if "review_date" in mapping else ""
        reviews.append({
            "reviewId": rid or f"csv:{idx}",
            "rating": rating,
            "review_text": body,
            "review_date": date or None,
        })
    return reviews


def save_raw_reviews(reviews: List[Dict[str, Any]], output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, indent=2, ensure_ascii=False)
    return output_path
