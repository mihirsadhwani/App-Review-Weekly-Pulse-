import os
import streamlit as st
import json
import random
from typing import List, Dict, Any
from groq import Groq

def get_config(key):
    return os.getenv(key) or st.secrets.get(key)

class ThemeAnalyzer:
    def __init__(self, input_path: str, output_path: str):
        self.input_path = input_path
        self.output_path = output_path
        
        # Ensure API key is loaded
        api_key = get_config("GROQ_API_KEY")
        if not api_key:
            print("ERROR: GROQ_API_KEY is missing from both environment variables and st.secrets.")
            raise ValueError("GROQ_API_KEY configuration missing")
            
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile" 

    def _get_balanced_sample(self, reviews: List[Dict[str, Any]], sample_size: int = 150) -> List[Dict[str, Any]]:
        if len(reviews) <= sample_size:
            return reviews
            
        # Group by rating
        by_rating = {1: [], 2: [], 3: [], 4: [], 5: []}
        for review in reviews:
            rating = review.get("rating", 0)
            if rating in by_rating:
                by_rating[rating].append(review)
                
        # Try to take an equal number from each rating bucket
        sample = []
        per_bucket = sample_size // 5
        
        for rating, bucket_reviews in by_rating.items():
            if not bucket_reviews:
                continue
            k = min(len(bucket_reviews), per_bucket)
            sample.extend(random.sample(bucket_reviews, k))
            
        # If we are short (because some buckets were small), fill randomly from remaining
        if len(sample) < sample_size:
            remaining = [r for r in reviews if r not in sample]
            k_needed = min(len(remaining), sample_size - len(sample))
            sample.extend(random.sample(remaining, k_needed))
            
        return sample

    def discover_themes(self, sample_reviews: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        reviews_text = "\n".join([f"- [Rating: {r.get('rating')}] {r.get('review_text')}" for r in sample_reviews])
        
        prompt = f"""
You are an expert product analyst. Review the following mobile app feedback.
Generate exactly 3 to 5 dominant product themes strictly related to user experiences, bugs, issues, or specific features.
DO NOT use vague themes like "General Feedback" or "User Experience".
Themes must describe specific product areas (e.g., "Withdrawal Delays", "Order Execution Issues", "App Performance").

Return the output in STRICT JSON format with the following structure:
{{
  "themes": [
    {{
      "theme_id": "theme_1",
      "label": "Theme Name",
      "description": "Short description of the theme"
    }}
  ]
}}

Reviews:
{reviews_text}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        response_json = json.loads(response.choices[0].message.content)
        return response_json.get("themes", [])

    def classify_reviews(self, all_reviews: List[Dict[str, Any]], themes: List[Dict[str, str]]) -> Dict[str, str]:
        # Batch reviews to avoid token limits. We'll do simple batching.
        batch_size = 50
        review_to_theme = {}
        
        themes_context = json.dumps(themes, indent=2)
        
        for i in range(0, len(all_reviews), batch_size):
            batch = all_reviews[i:i+batch_size]
            reviews_list_str = json.dumps([{"reviewId": r["reviewId"], "text": r["review_text"]} for r in batch])
            
            prompt = f"""
Given the following list of themes:
{themes_context}

Assign EXACTLY ONE theme to each of the following reviews.
Return the output in STRICT JSON format like this:
{{
  "assignments": [
    {{"reviewId": "id_here", "theme_id": "theme_id_here"}}
  ]
}}

Reviews to classify:
{reviews_list_str}
"""
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            try:
                assignments = json.loads(response.choices[0].message.content).get("assignments", [])
                for a in assignments:
                    review_to_theme[a.get("reviewId")] = a.get("theme_id")
            except Exception as e:
                print(f"Error parsing classification batch: {e}")
                
        return review_to_theme

    def analyze(self):
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input file not found: {self.input_path}")

        with open(self.input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        all_reviews = data.get("reviews", [])
        if not all_reviews:
            print("No reviews found to analyze.")
            return
            
        # 1. Theme Discovery
        sample_size = min(150, len(all_reviews))
        sample_reviews = self._get_balanced_sample(all_reviews, sample_size=sample_size)
        
        print(f"Discovering themes from a sample of {len(sample_reviews)} reviews...")
        themes = self.discover_themes(sample_reviews)
        
        # 2. Theme Classification
        print(f"Classifying {len(all_reviews)} reviews into {len(themes)} themes...")
        assignments = self.classify_reviews(all_reviews, themes)
        
        # 3. Grouping
        grouped_themes = []
        for theme in themes:
            theme_id = theme.get("theme_id")
            # Find all reviews assigned to this theme
            assigned_reviews = [r for r in all_reviews if assignments.get(r.get("reviewId")) == theme_id]
            
            grouped_themes.append({
                "theme_id": theme_id,
                "label": theme.get("label"),
                "description": theme.get("description"),
                "review_count": len(assigned_reviews),
                "reviews": assigned_reviews
            })
            
        output_data = {
            "theme_count": len(grouped_themes),
            "themes": grouped_themes
        }
        
        # Ensure output directory exists
        output_dir = os.path.dirname(self.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        return len(grouped_themes), len(all_reviews)
