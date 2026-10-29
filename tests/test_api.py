import json
import os
import sys
import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import main  # noqa: E402
from services import gemini_client  # noqa: E402
from services.store import FileStore  # noqa: E402

REVIEWS = [
    {"reviewId": "r1", "rating": 1, "review_text": "Withdrawal takes too long, call me on 9876543210 or mail a@b.com", "review_date": "2099-01-01 10:00:00"},
    {"reviewId": "r2", "rating": 5, "review_text": "good", "review_date": "2099-01-01 10:00:00"},
    {"reviewId": "r3", "rating": 2, "review_text": "App crashes during SIP purchase every time I try", "review_date": "2099-01-01 11:00:00"},
]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_config_exposes_pricing_without_secrets(self):
        data = self.client.get("/api/config").json()
        self.assertEqual(len(data["pricing"]), 2)
        self.assertNotIn("GEMINI_API_KEY", json.dumps(data))

    @patch.dict(os.environ, {"APP_PASSWORD": "s3cret"})
    def test_auth_gate(self):
        self.assertTrue(self.client.get("/api/config").json()["authRequired"])
        self.assertEqual(self.client.get("/api/runs").status_code, 401)
        self.assertEqual(self.client.get("/api/runs", headers={"X-Access-Key": "wrong"}).status_code, 401)
        self.assertEqual(self.client.get("/api/runs", headers={"X-Access-Key": "s3cret"}).status_code, 200)
        self.assertEqual(self.client.post("/api/login", json={"password": "s3cret"}).status_code, 200)

    def test_clean_scrubs_pii_and_filters_low_signal(self):
        res = self.client.post("/api/pipeline/clean", json={"reviews": REVIEWS, "weeks": None}).json()
        texts = " ".join(r["review_text"] for r in res["reviews"])
        self.assertNotIn("9876543210", texts)
        self.assertNotIn("a@b.com", texts)
        self.assertNotIn("good", [r["review_text"] for r in res["reviews"]])
        self.assertEqual(res["raw_count"], 3)

    def test_collect_from_csv(self):
        csv_text = "Rating,Review,Date\n1,Withdrawal is slow,2099-01-01\n5,ok,2099-01-02\n"
        res = self.client.post("/api/pipeline/collect", json={"source": "csv", "csv": csv_text}).json()
        self.assertEqual(len(res["reviews"]), 2)
        self.assertEqual(res["reviews"][0]["rating"], 1)

    def test_csv_missing_columns_is_a_client_error(self):
        res = self.client.post("/api/pipeline/collect", json={"source": "csv", "csv": "foo,bar\n1,2\n"})
        self.assertEqual(res.status_code, 400)

    @patch("phase3_theme_analysis.services.analyzer.generate_json")
    def test_analyze_groups_reviews_by_theme(self, gen):
        gen.side_effect = [
            {"themes": [{"theme_id": "theme_1", "label": "Withdrawals", "description": "d"}, {"theme_id": "theme_2", "label": "Crashes", "description": "d"}]},
            {"assignments": [{"reviewId": "r1", "theme_id": "theme_1"}, {"reviewId": "r3", "theme_id": "theme_2"}]},
        ]
        res = self.client.post("/api/pipeline/analyze", json={"reviews": [REVIEWS[0], REVIEWS[2]]}).json()
        counts = {t["label"]: t["review_count"] for t in res["themes"]}
        self.assertEqual(counts, {"Withdrawals": 1, "Crashes": 1})

    def test_run_history_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, patch("main.get_store", return_value=FileStore(d)):
            bundle = {"id": "run_1", "status": "completed", "started_at": "2026-01-01T00:00:00", "review_count": 3, "pulse_md": "# x", "calls": []}
            self.assertEqual(self.client.put("/api/runs/run_1", json=bundle).status_code, 200)
            self.assertEqual(self.client.put("/api/runs/other", json=bundle).status_code, 400)
            listed = self.client.get("/api/runs").json()["runs"]
            self.assertEqual([r["id"] for r in listed], ["run_1"])
            self.assertNotIn("pulse_md", listed[0])
            self.assertEqual(self.client.get("/api/runs/run_1").json()["pulse_md"], "# x")
            self.assertEqual(self.client.get("/api/runs/missing").status_code, 404)


class UsageCaptureTests(unittest.TestCase):
    def test_capture_records_tokens_and_cost(self):
        meta = types.SimpleNamespace(prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=0)
        fake = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=lambda **kw: types.SimpleNamespace(text='{"ok": true}', usage_metadata=meta)))
        with patch.object(gemini_client, "_get_client", return_value=fake), gemini_client.capture() as calls:
            out = gemini_client.generate_json("hi", label="theme_classification_3", model="gemini-3.5-flash-lite")
        self.assertEqual(out, {"ok": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["step"], "theme_classification")
        expected = (1000 * 0.30 + 200 * 2.50) / 1_000_000
        self.assertAlmostEqual(calls[0]["cost_usd"], expected, places=6)

    def test_rejected_key_fails_fast_with_actionable_message(self):
        class Rejected(Exception):
            code = 401

        calls = []

        def boom(**kw):
            calls.append(1)
            raise Rejected("API key not valid")

        fake = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=boom))
        with patch.object(gemini_client, "_get_client", return_value=fake):
            with self.assertRaises(gemini_client.LLMError) as ctx:
                gemini_client.generate_json("hi", label="x")
        self.assertIn("aistudio.google.com/apikey", str(ctx.exception))
        self.assertEqual(len(calls), 1)  # no pointless retries


if __name__ == "__main__":
    unittest.main()
