import os
import json
import unittest
from unittest.mock import patch, MagicMock
from phase3_theme_analysis.services.analyzer import ThemeAnalyzer

class TestThemeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.test_input = "test_filtered_reviews.json"
        self.test_output = "test_theme_map.json"
        
        # We need a proper structure matching what Phase 2 outputs
        self.raw_data = {
            "review_count": 6,
            "reviews": [
                {"reviewId": "r1", "review_text": "Withdrawal takes too long", "rating": 1},
                {"reviewId": "r2", "review_text": "App is very slow sometimes", "rating": 2},
                {"reviewId": "r3", "review_text": "Deposit not showing up", "rating": 1},
                {"reviewId": "r4", "review_text": "Fast execution", "rating": 5},
                {"reviewId": "r5", "review_text": "Graphs are wrong on the daily timeframe", "rating": 2},
                {"reviewId": "r6", "review_text": "SIP payment failed", "rating": 1}
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
    @patch("phase3_theme_analysis.services.analyzer.Groq")
    def test_analysis_flow(self, mock_groq_class):
        # Setup Mock Groq Instance
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        
        # Configure the mock responses
        # First call: theme discovery
        discovery_response = MagicMock()
        discovery_response.choices[0].message.content = json.dumps({
            "themes": [
                {"theme_id": "theme_1", "label": "Payment Issues", "description": "Issues with withdrawal or deposit"},
                {"theme_id": "theme_2", "label": "App Performance", "description": "App is slow or graphs are wrong"},
                {"theme_id": "theme_3", "label": "Execution", "description": "Fast or slow execution"}
            ]
        })
        
        # Second call: theme classification
        classification_response = MagicMock()
        classification_response.choices[0].message.content = json.dumps({
            "assignments": [
                {"reviewId": "r1", "theme_id": "theme_1"},
                {"reviewId": "r2", "theme_id": "theme_2"},
                {"reviewId": "r3", "theme_id": "theme_1"},
                {"reviewId": "r4", "theme_id": "theme_3"},
                {"reviewId": "r5", "theme_id": "theme_2"},
                {"reviewId": "r6", "theme_id": "theme_1"}
            ]
        })
        
        mock_client.chat.completions.create.side_effect = [discovery_response, classification_response]
        
        # Run analyzer
        analyzer = ThemeAnalyzer(self.test_input, self.test_output)
        num_themes, num_reviews = analyzer.analyze()
        
        # Verify outputs
        self.assertEqual(num_themes, 3)
        self.assertEqual(num_reviews, 6)
        
        self.assertTrue(os.path.exists(self.test_output))
        with open(self.test_output, 'r', encoding='utf-8') as f:
            result = json.load(f)
            
        self.assertIn("theme_count", result)
        self.assertIn("themes", result)
        self.assertTrue(result["theme_count"] <= 5)
        
        # Verify each review is assigned exactly once (total count matches)
        total_assigned = sum(t["review_count"] for t in result["themes"])
        self.assertEqual(total_assigned, 6)
        
        # Check specific mapping
        theme_1 = next(t for t in result["themes"] if t["theme_id"] == "theme_1")
        self.assertEqual(theme_1["review_count"], 3)
        
if __name__ == "__main__":
    unittest.main()
