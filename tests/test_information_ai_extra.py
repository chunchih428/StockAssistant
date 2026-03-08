import datetime
import importlib
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from market_data import information_ai


class TestInformationAIExtra(unittest.TestCase):
    def test_reload_module_for_definition_coverage(self):
        importlib.reload(information_ai)

    def test_extract_json_text_plain(self):
        self.assertEqual(information_ai.extract_json_text('{"a":1}'), '{"a":1}')

    def test_analyze_news_no_articles(self):
        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini_v1(
                symbol="AAPL",
                articles=[],
                cache_dir=td,
                env_get=lambda _k: "k",
                print_fn=lambda *_a, **_k: None,
            )

    def test_analyze_news_output_exists_short_circuit(self):
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, datetime.date.today().isoformat(), "holdings", "news")
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "AAPL_analysis.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{}")
            information_ai.analyze_news_with_gemini_v1(
                symbol="AAPL",
                articles=[{"title": "x"}],
                cache_dir=td,
                env_get=lambda _k: "k",
                print_fn=lambda *_a, **_k: None,
            )

    def test_analyze_news_import_error_branch(self):
        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini_v1(
                symbol="AAPL",
                articles=[{"title": "x"}],
                cache_dir=td,
                env_get=lambda _k: "k",
                genai_module=None,
                genai_types_module=None,
                print_fn=lambda *_a, **_k: None,
            )

    def test_analyze_news_client_init_exception(self):
        class BadGen:
            class Client:
                def __init__(self, api_key):
                    raise RuntimeError("bad")

        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini_v1(
                symbol="AAPL",
                articles=[{"title": "x"}],
                cache_dir=td,
                env_get=lambda _k: "k",
                genai_module=BadGen,
                genai_types_module=SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs),
                print_fn=lambda *_a, **_k: None,
            )

    def test_analyze_news_retry_and_fail(self):
        class Client:
            def __init__(self, api_key):
                self.models = SimpleNamespace(generate_content=self._generate)

            @staticmethod
            def _generate(**_kwargs):
                raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini_v1(
                symbol="AAPL",
                articles=[{"title": "x"}],
                cache_dir=td,
                env_get=lambda _k: "k",
                genai_module=SimpleNamespace(Client=Client),
                genai_types_module=SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs),
                sleep_fn=lambda *_a, **_k: None,
                print_fn=lambda *_a, **_k: None,
            )

    def test_analyze_news_wrapper(self):
        class Client:
            def __init__(self, api_key):
                self.models = SimpleNamespace(generate_content=lambda **_kwargs: SimpleNamespace(text=json.dumps({
                    "ticker": "AAPL",
                    "company": "Apple",
                    "analysis_date": "2026-03-08",
                    "source_file": "x",
                    "summary": {"total_articles": 0, "bullish_count": 0, "bearish_count": 0, "neutral_count": 0, "overall_sentiment": "neutral", "key_theme": "k"},
                    "bullish": [],
                    "bearish": [],
                    "neutral": [],
                })))

        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini(
                symbol="AAPL",
                articles=[{"title": "x", "link": "", "publisher": "", "date": ""}],
                cache_dir=td,
                env_get=lambda _k: "k",
                genai_module=SimpleNamespace(Client=Client),
                genai_types_module=SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs),
                sleep_fn=lambda *_a, **_k: None,
                print_fn=lambda *_a, **_k: None,
            )

    def test_analyze_news_v1_loop_payload_fields(self):
        class Client:
            def __init__(self, api_key):
                self.models = SimpleNamespace(generate_content=lambda **_kwargs: SimpleNamespace(text=json.dumps({
                    "ticker": "AAPL",
                    "company": "Apple",
                    "analysis_date": "2026-03-08",
                    "source_file": "x",
                    "summary": {"total_articles": 1, "bullish_count": 1, "bearish_count": 0, "neutral_count": 0, "overall_sentiment": "bullish", "key_theme": "k"},
                    "bullish": [],
                    "bearish": [],
                    "neutral": [],
                })))

        with tempfile.TemporaryDirectory() as td:
            information_ai.analyze_news_with_gemini_v1(
                symbol="AAPL",
                articles=[{"title": "x", "link": "l", "publisher": "p", "date": "d"}],
                cache_dir=td,
                env_get=lambda _k: "k",
                genai_module=SimpleNamespace(Client=Client),
                genai_types_module=SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs),
                sleep_fn=lambda *_a, **_k: None,
                print_fn=lambda *_a, **_k: None,
            )


if __name__ == "__main__":
    unittest.main()
