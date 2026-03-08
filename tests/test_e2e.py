import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import stock_assistant


class TestE2E(unittest.TestCase):
    def test_test_mode_writes_to_test_cache_and_test_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            test_e2e_dir = base / "tests" / "test_e2e"
            test_e2e_dir.mkdir(parents=True, exist_ok=True)
            (test_e2e_dir / "holdings.csv").write_text(
                "股名,股數,買價,類別\nAAPL,1,100,美股個股\n",
                encoding="utf-8",
            )
            (test_e2e_dir / "competitors.json").write_text("{}", encoding="utf-8")
            (base / "system_prompt.txt").write_text("test prompt", encoding="utf-8")
            old_paths = {
                "PORTFOLIO_FILE": stock_assistant.PORTFOLIO_FILE,
                "CONFIG_FILE": stock_assistant.CONFIG_FILE,
                "SYSTEM_PROMPT_FILE": stock_assistant.SYSTEM_PROMPT_FILE,
                "COMPANY_NAMES_FILE": stock_assistant.COMPANY_NAMES_FILE,
                "COMPETITORS_FILE": stock_assistant.COMPETITORS_FILE,
                "CACHE_DIR": stock_assistant.CACHE_DIR,
                "RESULTS_FILE": stock_assistant.RESULTS_FILE,
                "HTML_FILE": stock_assistant.HTML_FILE,
            }

            try:
                with patch.object(stock_assistant, "BASE_DIR", base), \
                     patch.object(stock_assistant, "fetch_stock_data", return_value={
                         "symbol": "AAPL",
                         "fundamental": {"company_name": "Apple", "current_price": 123.0},
                         "technical": {"ma50": 120.0, "ma200": 110.0},
                     }), \
                     patch.object(stock_assistant, "fetch_news", return_value=[]), \
                     patch.object(stock_assistant, "fetch_competitor_data", return_value=[]), \
                     patch.object(stock_assistant, "generate_html", return_value="<html>test</html>"), \
                     patch.object(stock_assistant, "count_recommendations", return_value={"add": 0, "reduce": 0, "close": 0}), \
                     patch.object(stock_assistant.time, "sleep", return_value=None), \
                     patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False), \
                     patch.object(sys, "argv", ["stock_assistant.py", "--test"]):
                    stock_assistant.main()
            finally:
                stock_assistant.PORTFOLIO_FILE = old_paths["PORTFOLIO_FILE"]
                stock_assistant.CONFIG_FILE = old_paths["CONFIG_FILE"]
                stock_assistant.SYSTEM_PROMPT_FILE = old_paths["SYSTEM_PROMPT_FILE"]
                stock_assistant.COMPANY_NAMES_FILE = old_paths["COMPANY_NAMES_FILE"]
                stock_assistant.COMPETITORS_FILE = old_paths["COMPETITORS_FILE"]
                stock_assistant.CACHE_DIR = old_paths["CACHE_DIR"]
                stock_assistant.RESULTS_FILE = old_paths["RESULTS_FILE"]
                stock_assistant.HTML_FILE = old_paths["HTML_FILE"]

            test_cfg = base / "tests" / "test_e2e" / "test_cache"
            results_file = test_cfg / "results.json"
            html_file = base / "tests" / "test_e2e" / "test_index.html"

            self.assertTrue(test_cfg.exists())
            self.assertTrue((test_cfg / "config.json").exists())
            self.assertTrue(results_file.exists())
            self.assertTrue(html_file.exists())

            payload = json.loads(results_file.read_text(encoding="utf-8"))
            self.assertIn("results", payload)
            self.assertEqual(payload["results"][0]["symbol"], "AAPL")

    def test_test_mode_cache_dir_is_under_test_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            old_paths = {
                "PORTFOLIO_FILE": stock_assistant.PORTFOLIO_FILE,
                "CONFIG_FILE": stock_assistant.CONFIG_FILE,
                "SYSTEM_PROMPT_FILE": stock_assistant.SYSTEM_PROMPT_FILE,
                "COMPANY_NAMES_FILE": stock_assistant.COMPANY_NAMES_FILE,
                "COMPETITORS_FILE": stock_assistant.COMPETITORS_FILE,
                "CACHE_DIR": stock_assistant.CACHE_DIR,
                "RESULTS_FILE": stock_assistant.RESULTS_FILE,
                "HTML_FILE": stock_assistant.HTML_FILE,
            }
            try:
                with patch.object(stock_assistant, "BASE_DIR", base):
                    stock_assistant.configure_test_mode()
                    cm = stock_assistant.CacheManager(
                        scope="holdings",
                        base_cache_dir=stock_assistant.CACHE_DIR,
                    )
                    cm.set("technical", "AAPL", {"ok": 1})
                    expected = (
                        base
                        / "tests"
                        / "test_e2e"
                        / "test_cache"
                        / stock_assistant.datetime.date.today().isoformat()
                        / "holdings"
                        / "technical"
                        / "AAPL.json"
                    )
                    self.assertTrue(expected.exists())
            finally:
                stock_assistant.PORTFOLIO_FILE = old_paths["PORTFOLIO_FILE"]
                stock_assistant.CONFIG_FILE = old_paths["CONFIG_FILE"]
                stock_assistant.SYSTEM_PROMPT_FILE = old_paths["SYSTEM_PROMPT_FILE"]
                stock_assistant.COMPANY_NAMES_FILE = old_paths["COMPANY_NAMES_FILE"]
                stock_assistant.COMPETITORS_FILE = old_paths["COMPETITORS_FILE"]
                stock_assistant.CACHE_DIR = old_paths["CACHE_DIR"]
                stock_assistant.RESULTS_FILE = old_paths["RESULTS_FILE"]
                stock_assistant.HTML_FILE = old_paths["HTML_FILE"]


if __name__ == "__main__":
    unittest.main()
