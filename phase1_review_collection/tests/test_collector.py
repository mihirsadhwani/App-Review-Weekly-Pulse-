import os
import json
import unittest
from phase1_review_collection.services.collector import PlayStoreCollector

class TestCollector(unittest.TestCase):
    def test_collect_reviews(self):
        # Initialize collector with com.nextbillion.groww, fetching 600 reviews
        # to ensure we meet the required threshold.
        collector = PlayStoreCollector('com.nextbillion.groww', count=600)
        run_id, output_path = collector.collect()
        
        print(f"Test generated run_id: {run_id}")
        
        # Verify run_id is generated
        self.assertTrue(run_id.startswith("run_"))
        
        # Verify JSON file is created in expected location
        self.assertTrue("phase1_review_collection" in output_path)
        
        # Verify content schema
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 600)
        
        # Verify exact fields extracted
        first_review = data[0]
        self.assertIn("reviewId", first_review)
        self.assertIn("rating", first_review)
        self.assertIn("review_text", first_review)
        self.assertIn("review_date", first_review)

if __name__ == '__main__':
    unittest.main()
