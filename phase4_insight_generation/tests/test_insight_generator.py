import os
import json
import unittest
from unittest.mock import patch, MagicMock
from phase4_insight_generation.services.insight_generator import InsightGenerator

class TestInsightGenerator(unittest.TestCase):
    def setUp(self):
        self.test_input = "test_theme_map.json"
        self.test_output = "test_insights.json"
        
        # We need a dummy theme map matching Phase 3 output
        self.raw_data = {
            "themes": [
                {
                    "theme_id": "theme_1",
                    "label": "Withdrawal Delays",
                    "description": "Difficulty withdrawing funds",
                    "reviews": [
                        {"reviewId": "r1", "review_text": "Withdrawal takes 3 days to reflect in bank", "rating": 1},
                        {"reviewId": "r2", "review_text": "Money withdrawal is very slow", "rating": 1}
                    ]
                },
                {
                    "theme_id": "theme_2",
                    "label": "App Bugs",
                    "description": "App crashes or hangs",
                    "reviews": [
                        {"reviewId": "r3", "review_text": "app crashes during SIP purchase", "rating": 1}
                    ]
                }
            ]
        }
        
        with open(self.test_input, 'w', encoding='utf-8') as f:
            json.dump(self.raw_data, f)
            
    def tearDown(self):
        if os.path.exists(self.test_input):
            os.remove(self.test_input)
        if os.path.exists(self.test_output):
            os.remove(self.test_output)

    @patch.dict(os.environ, {"GROQ_API_KEY": "fake_test_key"})
    @patch("phase4_insight_generation.services.insight_generator.Groq")
    def test_insight_generation_flow(self, mock_groq_class):
        # Setup Mock Groq Instance
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        
        # We have 2 themes, so we expect two calls for theme quotes and one call for action ideas.
        
        quote_response_1 = MagicMock()
        quote_response_1.choices[0].message.content = json.dumps({
            "quotes": ["Withdrawal takes 3 days to reflect in bank", "Money withdrawal is very slow"]
        })
        
        quote_response_2 = MagicMock()
        quote_response_2.choices[0].message.content = json.dumps({
            "quotes": ["app crashes during SIP purchase"]
        })
        
        action_ideas_response = MagicMock()
        action_ideas_response.choices[0].message.content = json.dumps({
            "action_ideas": [
                {"title": "Idea 1", "rationale": "Rationale 1"},
                {"title": "Idea 2", "rationale": "Rationale 2"},
                {"title": "Idea 3", "rationale": "Rationale 3"}
            ]
        })
        
        mock_client.chat.completions.create.side_effect = [
            quote_response_1,
            quote_response_2,
            action_ideas_response
        ]
        
        # Run generator
        generator = InsightGenerator(self.test_input, self.test_output)
        output_data = generator.generate()
        
        # Verify
        self.assertTrue(os.path.exists(self.test_output))
        
        # Verify structure
        self.assertIn("themes", output_data)
        self.assertIn("action_ideas", output_data)
        
        # Verify exactly 3 action ideas
        self.assertEqual(len(output_data["action_ideas"]), 3)
        
        # Verify quotes per theme <= 2
        for theme in output_data["themes"]:
            self.assertTrue(len(theme.get("quotes", [])) <= 2)

if __name__ == "__main__":
    unittest.main()
