import unittest
import os
import json
from phase2_review_cleaning.services.cleaner import ReviewCleaner

class TestReviewCleaner(unittest.TestCase):
    def setUp(self):
        self.test_input = "test_raw_reviews.json"
        self.test_output = "test_filtered_reviews.json"
        
        self.raw_data = [
            {"reviewId": "1", "review_text": "withdrawal takes too long", "rating": 2},
            {"reviewId": "2", "review_text": "good", "rating": 5},
            {"reviewId": "3", "review_text": "very good app", "rating": 5},
            {"reviewId": "4", "review_text": "👍👍👍", "rating": 5},
            {"reviewId": "5", "review_text": "withdrawal takes too long", "rating": 2}, # Duplicate
            {"reviewId": "6", "review_text": "kyc verification stuck for hours", "rating": 1},
            {"reviewId": "7", "review_text": "", "rating": 3}, # Empty
            {"reviewId": "8", "review_text": "orders execution me problem hoti hai", "rating": 1}, # Hinglish
            {"reviewId": "9", "review_text": "groww app daily timeframe candlestick wrong showing", "rating": 2}, # Domain specific
            {"reviewId": "10", "review_text": "very secure and advance", "rating": 5}, # Vague generic
            {"reviewId": "11", "review_text": "so very nice good app", "rating": 5}, # generic praise
            {"reviewId": "12", "review_text": "widra very good", "rating": 3} # Semantic removal (short + generic)
        ]
        
        with open(self.test_input, 'w', encoding='utf-8') as f:
            json.dump(self.raw_data, f)
            
    def tearDown(self):
        if os.path.exists(self.test_input):
            os.remove(self.test_input)
        if os.path.exists(self.test_output):
            os.remove(self.test_output)

    def test_cleaning_logic(self):
        cleaner = ReviewCleaner(self.test_input, self.test_output)
        count = cleaner.clean()
        
        self.assertTrue(os.path.exists(self.test_output))
        
        with open(self.test_output, 'r', encoding='utf-8') as f:
            result = json.load(f)
            
        # Expected to keep: 
        # 1. "withdrawal takes too long"
        # 6. "kyc verification stuck for hours"
        # 8. "orders execution me problem hoti hai"
        # 9. "groww app daily timeframe candlestick wrong showing"
        self.assertEqual(result["review_count"], 4)
        
        texts = [r["review_text"] for r in result["reviews"]]
        self.assertIn("withdrawal takes too long", texts)
        self.assertIn("kyc verification stuck for hours", texts)
        self.assertIn("orders execution me problem hoti hai", texts)
        self.assertIn("groww app daily timeframe candlestick wrong showing", texts)
        
        # Verify removals
        self.assertNotIn("good", texts)
        self.assertNotIn("very good app", texts)
        self.assertNotIn("👍👍👍", texts)
        self.assertNotIn("", texts)
        self.assertNotIn("very secure and advance", texts)
        self.assertNotIn("so very nice good app", texts)
        self.assertNotIn("widra very good", texts)

if __name__ == "__main__":
    unittest.main()
