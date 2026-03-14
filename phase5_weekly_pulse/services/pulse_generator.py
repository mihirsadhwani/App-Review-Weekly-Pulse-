import os
import json
import re
from datetime import datetime
from services.gemini_client import generate_with_gemini

class PulseGenerator:
    def __init__(self, theme_map_path: str, insights_path: str, output_md_path: str, output_txt_path: str):
        self.theme_map_path = theme_map_path
        self.insights_path = insights_path
        self.output_md_path = output_md_path
        self.output_txt_path = output_txt_path

    def strip_markdown(self, text: str) -> str:
        # Simple markdown to text conversion
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text) # Bold
        text = re.sub(r'_(.*?)_', r'\1', text) # Italics
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE) # Headers
        text = re.sub(r'^>\s+', '  ', text, flags=re.MULTILINE) # Blockquotes
        text = re.sub(r'^\*\s+', '- ', text, flags=re.MULTILINE) # Unordered lists
        return text.strip()

    def generate(self):
        if not os.path.exists(self.theme_map_path):
            raise FileNotFoundError(f"Missing {self.theme_map_path}")
        if not os.path.exists(self.insights_path):
            raise FileNotFoundError(f"Missing {self.insights_path}")

        with open(self.theme_map_path, 'r', encoding='utf-8') as f:
            theme_map = json.load(f)
            
        with open(self.insights_path, 'r', encoding='utf-8') as f:
            insights = json.load(f)

        # Merge insights and counts
        total_reviews = 0
        theme_counts = {}
        for t in theme_map.get("themes", []):
            theme_counts[t["theme_id"]] = t.get("review_count", 0)
            total_reviews += t.get("review_count", 0)

        theme_details = []
        for t in insights.get("themes", []):
            t_id = t["theme_id"]
            count = theme_counts.get(t_id, 0)
            label = t["label"]
            quotes = t.get("quotes", [])
            theme_details.append({
                "label": label,
                "count": count,
                "quotes": quotes
            })
            
        action_ideas = insights.get("action_ideas", [])

        # Format input for prompt
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        prompt = f"""
Generate a weekly pulse report using the following data.

Date: {date_str}
Total Reviews Analysed: {total_reviews}

Themes:
{json.dumps(theme_details, indent=2)}

Action Ideas:
{json.dumps(action_ideas, indent=2)}

REQUIREMENTS & CONSTRAINTS:
1. Keep the total word count strictly UNDER 250 words.
2. Ensure up to 5 themes are included.
3. Do not make up quotes. Use verbatim strings from the provided data.
4. Generate **3 highly specific product improvement actions** based on the themes and user quotes.
   Constraints:
   - Each action must reference the **actual problem from the theme**.
   - Avoid generic suggestions like "improve performance", "enhance user experience", or "optimize the system".
   - Each action should propose a **clear product feature, system change, or workflow improvement**.
   - Each action must include:
     • Action Title
     • One-line product rationale explaining how it solves the user problem.

   EXAMPLE OF GOOD ACTION IDEA:
   Theme: Payment Failure Issues
   User Quote: "Payment failed but money got deducted"
   Correct Action Idea: Add a **payment retry and reconciliation system** that automatically retries failed transactions and instantly refunds deducted funds if confirmation fails.

5. Format exactly identically to the template below:

# Groww Mutual Fund — Weekly Review Pulse

Week Ending: {date_str}
Reviews Analysed: {total_reviews}

## Top Themes

[Theme Name] — [count] mentions

> "[exact quote from data]"

(repeat for each theme)

## Product Action Ideas

1. **[Action Title]** — [rationale]
2. **[Action Title]** — [rationale]
3. **[Action Title]** — [rationale]
"""

        md_content = generate_with_gemini(prompt)

        # Validate word count and retry if needed
        word_count = len(md_content.split())
        if word_count > 250:
            shorten_prompt = f"""
            The following report is {word_count} words. It MUST be under 250 words.
            Rewrite it to be shorter while keeping exactly the same structure, all themes, and all 3 action ideas.
            
            Report:
            {md_content}
            """
            md_content = generate_with_gemini(shorten_prompt)

        # Generate txt version
        txt_content = self.strip_markdown(md_content)

        # Save files
        output_dir = os.path.dirname(self.output_md_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
        with open(self.output_md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
        with open(self.output_txt_path, 'w', encoding='utf-8') as f:
            f.write(txt_content)

        return md_content, txt_content

