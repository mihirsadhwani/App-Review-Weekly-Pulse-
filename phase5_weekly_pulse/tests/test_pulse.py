import os
import json
import unittest
from unittest.mock import patch, MagicMock
from phase5_weekly_pulse.services.pulse_generator import PulseGenerator

class TestPulseGenerator(unittest.TestCase):
    def setUp(self):
        self.test_theme_map = "test_theme_map.json"
        self.test_insights = "test_insights.json"
        self.output_md = "test_weekly_pulse.md"
        self.output_txt = "test_weekly_pulse.txt"
        
        # Mock theme map
        with open(self.test_theme_map, 'w', encoding='utf-8') as f:
            json.dump({
                "theme_count": 2,
                "themes": [
                    {"theme_id": "theme_1", "review_count": 10},
                    {"theme_id": "theme_2", "review_count": 5}
                ]
            }, f)
            
        # Mock insights
        with open(self.test_insights, 'w', encoding='utf-8') as f:
            json.dump({
                "themes": [
                    {"theme_id": "theme_1", "label": "Bugs", "quotes": ["bug 1"]},
                    {"theme_id": "theme_2", "label": "UI", "quotes": ["ui 1"]}
                ],
                "action_ideas": [
                    {"title": "Idea 1", "rationale": "Rationale 1"},
                    {"title": "Idea 2", "rationale": "Rationale 2"},
                    {"title": "Idea 3", "rationale": "Rationale 3"}
                ]
            }, f)

    def tearDown(self):
        for f in [self.test_theme_map, self.test_insights, self.output_md, self.output_txt]:
            if os.path.exists(f):
                os.remove(f)

    @patch("phase5_weekly_pulse.services.pulse_generator.generate_with_gemini")
    def test_pulse_generation(self, mock_gemini):
        # Configure mock return value
        mock_output = """# Groww Mutual Fund — Weekly Review Pulse

Week Ending: 2026-03-10
Reviews Analysed: 15

## Top Themes

Bugs — 10 mentions
> "bug 1"

UI — 5 mentions
> "ui 1"

## Product Action Ideas

1. **Idea 1** — Rationale 1
2. **Idea 2** — Rationale 2
3. **Idea 3** — Rationale 3
"""
        mock_gemini.return_value = mock_output
        
        generator = PulseGenerator(self.test_theme_map, self.test_insights, self.output_md, self.output_txt)
        md_content, txt_content = generator.generate()
        
        # Verify files created
        self.assertTrue(os.path.exists(self.output_md))
        self.assertTrue(os.path.exists(self.output_txt))
        
        # Verify word count < 250
        self.assertTrue(len(md_content.split()) <= 250)
        
        # Verify action ideas count
        self.assertEqual(md_content.count("Idea 1"), 1)
        self.assertEqual(md_content.count("Idea 2"), 1)
        self.assertEqual(md_content.count("Idea 3"), 1)

if __name__ == "__main__":
    unittest.main()
