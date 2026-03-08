import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dashboard import render


class TestDashboardRender(unittest.TestCase):
    def test_render_md_header_and_table(self):
        src = "x\n# T\n\n|A|B|\n|---|---|\n|1|2|"
        out = render.render_md(src)
        self.assertIn("<h1>", out)
        self.assertIn("A|B", out)

    @patch("dashboard.render.find_latest_news_analysis_file")
    def test_generate_html_with_news_analysis(self, mock_find):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "AAPL_analysis.json"
            p.write_text(
                json.dumps(
                    {
                        "summary": {"overall_sentiment": "bullish", "total_articles": 3},
                        "bullish": [{"title": "b"}],
                        "bearish": [],
                        "neutral": [],
                    }
                ),
                encoding="utf-8",
            )
            mock_find.return_value = p
            html = render.generate_html(
                results=[
                    {
                        "stock_info": {"symbol": "AAPL", "cost_basis": 100, "shares": 2, "category": "Tech"},
                        "stock_data": {"fundamental": {"current_price": 120, "company_name": "Apple"}, "technical": {}},
                        "analysis_result": {"analysis": "# Good", "recommendation": "add", "scores": {}},
                        "news": [{"title": "n1", "publisher": "x", "date": "", "link": "u"}],
                    }
                ],
                allocation={
                    "total_value": 1,
                    "total_pnl": 0,
                    "cash": 0,
                    "cash_pct": 0,
                    "positions": [],
                    "total_cost": 0,
                    "options_value": 0,
                    "options_pct": 0,
                },
                options=[],
                generated_at="2026-03-08 00:00:00",
            )
            self.assertIn("AAPL", html)
            self.assertIn("overall_sentiment", html)

    @patch("dashboard.render.find_latest_news_analysis_file")
    @patch("dashboard.render.json.loads")
    def test_generate_html_with_competitors_old_format_and_bad_analysis(self, mock_json_loads, mock_find):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "MSFT_analysis.json"
            p.write_text("{bad-json", encoding="utf-8")
            mock_find.return_value = p

            state = {"n": 0}

            def _loads(_text, **_kwargs):
                state["n"] += 1
                if state["n"] == 1:
                    return {"AAPL": ["MSFT"]}
                raise ValueError("bad analysis")

            mock_json_loads.side_effect = _loads

            html = render.generate_html(
                results=[
                    {
                        "stock_info": {"symbol": "AAPL", "cost_basis": 10, "shares": 1, "category": ""},
                        "stock_data": {"fundamental": {"current_price": 9}, "technical": {}},
                        "analysis_result": {"analysis": "", "recommendation": "hold", "scores": {}},
                        "news": [],
                    }
                ],
                allocation={"total_value": 0, "total_pnl": 0, "cash": 0, "cash_pct": 0, "positions": [], "total_cost": 0, "options_value": 0, "options_pct": 0},
                options=[],
                generated_at="2026-03-08 00:00:00",
            )
            self.assertIn("AAPL", html)

    @patch("dashboard.render.json.loads")
    @patch("dashboard.render.find_latest_news_analysis_file")
    def test_generate_html_competitor_map_read_error(self, mock_find, mock_json_loads):
        mock_find.return_value = None
        mock_json_loads.side_effect = ValueError("bad")
        html = render.generate_html(
            results=[
                {
                    "stock_info": {"symbol": "MSFT", "cost_basis": 0, "shares": 0, "category": "競品參考"},
                    "stock_data": {"fundamental": {}, "technical": {}, "error": "e"},
                    "analysis_result": {"analysis": "", "recommendation": "unknown", "scores": {}},
                    "news": [],
                }
            ],
            allocation={"total_value": 0, "total_pnl": 0, "cash": 0, "cash_pct": 0, "positions": [], "total_cost": 0, "options_value": 0, "options_pct": 0},
            options=[{"underlying": "AAPL", "type": "Call", "strike": 1, "expiry": "2026-01-01", "shares": 1, "cost_basis": 1, "total_cost": 1, "category": "x"}],
            generated_at="2026-03-08 00:00:00",
        )
        self.assertIn("MSFT", html)

    def test_count_recommendations(self):
        out = render.count_recommendations(
            [
                {"analysis_result": {"recommendation": "add"}},
                {"analysis_result": {"recommendation": "hold"}},
                {"analysis_result": {}},
            ]
        )
        self.assertEqual(out["add"], 1)
        self.assertEqual(out["hold"], 1)
        self.assertEqual(out["unknown"], 1)


if __name__ == "__main__":
    unittest.main()
