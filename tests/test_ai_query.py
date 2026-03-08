import datetime
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from market_data import fundamental_ai
from market_data import information_ai


class TestAIQuery(unittest.TestCase):
    def test_extract_json_text_from_code_fence(self):
        raw = "```json\n{\"k\":1}\n```"
        self.assertEqual(information_ai.extract_json_text(raw), '{"k":1}')

    def test_translate_summary_no_text(self):
        self.assertEqual(fundamental_ai.translate_summary_with_gemini(""), "")

    def test_translate_summary_no_key(self):
        out = fundamental_ai.translate_summary_with_gemini(
            "abc",
            env_get=lambda _k: None,
        )
        self.assertEqual(out, "abc")

    def test_analyze_news_with_gemini_no_key(self):
        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini(
                symbol="AAPL",
                articles=[{"title": "x"}],
                cache_dir=td,
                env_get=lambda _k: None,
                print_fn=lambda *_args, **_kwargs: None,
            )
            out = os.path.join(td, datetime.date.today().isoformat(), "holdings", "news", "AAPL_analysis.json")
            self.assertFalse(os.path.exists(out))

    def test_analyze_news_with_gemini_success_with_injected_client(self):
        class FakeClient:
            def __init__(self, api_key):
                self.models = SimpleNamespace(generate_content=self._generate)

            @staticmethod
            def _generate(**_kwargs):
                payload = {
                    "ticker": "AAPL",
                    "company": "Apple",
                    "analysis_date": "2026-01-01",
                    "source_file": "cache/2026-01-01/holdings/news/AAPL.json",
                    "summary": {
                        "total_articles": 1,
                        "bullish_count": 1,
                        "bearish_count": 0,
                        "neutral_count": 0,
                        "overall_sentiment": "bullish",
                        "key_theme": "皜祈岫",
                    },
                    "bullish": [],
                    "bearish": [],
                    "neutral": [],
                }
                return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))

        fake_genai = SimpleNamespace(Client=FakeClient)
        fake_types = SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs)
        fixed_date = datetime.date(2026, 1, 1)

        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini(
                symbol="AAPL",
                articles=[{"title": "x", "link": "", "publisher": "", "date": ""}],
                cache_dir=td,
                env_get=lambda _k: "mock-key",
                print_fn=lambda *_args, **_kwargs: None,
                sleep_fn=lambda *_args, **_kwargs: None,
                genai_module=fake_genai,
                genai_types_module=fake_types,
                today=fixed_date,
            )
            out = os.path.join(td, "2026-01-01", "holdings", "news", "AAPL_analysis.json")
            self.assertTrue(os.path.exists(out))
            data = json.loads(open(out, "r", encoding="utf-8").read())
            self.assertEqual(data["ticker"], "AAPL")
            self.assertEqual(data["_schema_version"], "1.1")


if __name__ == "__main__":
    unittest.main()

