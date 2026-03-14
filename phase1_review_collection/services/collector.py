import json
import os
import uuid
from datetime import datetime
from google_play_scraper import reviews, Sort

class PlayStoreCollector:
    def __init__(self, package_id: str, count: int = 600):
        self.package_id = package_id
        self.count = count

    def generate_run_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:6]
        return f"run_{timestamp}_{unique_id}"

    def collect(self) -> tuple[str, str]:
        run_id = self.generate_run_id()
        
        # Fetch reviews from Google Play
        # Defaulting to India/English for Groww
        result, _ = reviews(
            self.package_id,
            lang='en',
            country='in',
            sort=Sort.NEWEST,
            count=self.count
        )

        extracted_reviews = []
        for r in result:
            extracted_reviews.append({
                "reviewId": r.get("reviewId"),
                "rating": r.get("score"),
                "review_text": r.get("content"),
                "review_date": str(r.get("at")) if r.get("at") else None
            })

        # Create output directory
        output_dir = os.path.join("phase1_review_collection")
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, "raw_reviews.json")
        
        # Save output to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(extracted_reviews, f, indent=2, ensure_ascii=False)
            
        return run_id, output_path
