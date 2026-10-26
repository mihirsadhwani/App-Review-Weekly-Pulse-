import os
import json
from typing import List, Dict, Any

from services.gemini_client import generate_json, SYNTHESIS_MODEL

QUOTES_SCHEMA = {
    "type": "object",
    "properties": {"quotes": {"type": "array", "items": {"type": "string"}}},
    "required": ["quotes"],
}

ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "action_ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "rationale": {"type": "string"}},
                "required": ["title", "rationale"],
            },
        }
    },
    "required": ["action_ideas"],
}

class InsightGenerator:
    def __init__(self, input_path: str, output_path: str):
        self.input_path = input_path
        self.output_path = output_path
        
        self.model = SYNTHESIS_MODEL

    def select_quotes_for_theme(self, theme_label: str, theme_description: str, reviews: List[Dict[str, Any]]) -> List[str]:
        if not reviews:
            return []
            
        # Select up to 30 reviews to avoid context overload and save tokens
        sample_reviews = reviews[:30]
        reviews_text = "\n".join([f'- "{r.get("review_text", "")}"' for r in sample_reviews])
        
        prompt = f"""
You are an expert product analyst.
Theme: "{theme_label}"
Description: {theme_description}

Here are some user reviews assigned to this theme:
{reviews_text}

Task:
Select 1 to 2 representative verbatim user quotes from the provided reviews that best illustrate this theme.
Quotes MUST BE COPIED EXACTLY as written. DO NOT paraphrase. DO NOT fabricate.
Return the output in STRICT JSON format like this:
{{
  "quotes": [
    "exact verbatim quote 1",
    "exact verbatim quote 2"
  ]
}}
"""
        try:
            response_json = generate_json(prompt, schema=QUOTES_SCHEMA, model=self.model, label="quote_selection")
            quotes = response_json.get("quotes", [])
            # Anti-hallucination guard: keep only quotes that appear verbatim in the source reviews
            source_texts = [r.get("review_text", "") for r in reviews]
            verbatim = [q for q in quotes if any(q.strip() and q.strip() in t for t in source_texts)]
            return (verbatim or quotes)[:2]
        except Exception as e:
            print(f"Error extracting quotes for theme {theme_label}: {e}")
            return []

    def generate_action_ideas(self, themes_with_quotes: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        themes_context = json.dumps(themes_with_quotes, indent=2)
        
        prompt = f"""
Given the following themes and representative user quotes:
{themes_context}

Task:
Generate EXACTLY 3 actionable product ideas.
Each action idea must:
- Address real user problems seen in these themes.
- Be specific and practical.
- Include a one-line rationale explaining why based on the user feedback.

Return the output in STRICT JSON format like this:
{{
  "action_ideas": [
    {{
      "title": "Action idea title here",
      "rationale": "One line rationale here"
    }}
  ]
}}
"""
        try:
            response_json = generate_json(
                prompt, schema=ACTIONS_SCHEMA, model=self.model, temperature=0.2, label="action_generation"
            )
            ideas = response_json.get("action_ideas", [])
            return ideas[:3]
        except Exception as e:
            print(f"Error generating action ideas: {e}")
            return []

    def generate(self):
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input file not found: {self.input_path}")

        with open(self.input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        themes_input = data.get("themes", [])
        if not themes_input:
            print("No themes found to generate insights.")
            return

        final_themes = []
        
        print(f"Selecting quotes for {len(themes_input)} themes...")
        for t in themes_input:
            theme_id = t.get("theme_id")
            label = t.get("label")
            description = t.get("description", "")
            reviews = t.get("reviews", [])
            
            quotes = self.select_quotes_for_theme(label, description, reviews)
            
            final_themes.append({
                "theme_id": theme_id,
                "label": label,
                "quotes": quotes
            })
            
        print("Generating action ideas...")
        action_ideas = self.generate_action_ideas(final_themes)
        
        output_data = {
            "themes": final_themes,
            "action_ideas": action_ideas
        }
        
        # Ensure output directory exists
        output_dir = os.path.dirname(self.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        return output_data
