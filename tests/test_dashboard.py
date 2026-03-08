import json
import datetime
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dashboard


class TestRebuildDashboard(unittest.TestCase):
    def test_is_results_fresh_today(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(dashboard.rebuild._is_results_fresh_today({"generated_at": today}))
        self.assertFalse(dashboard.rebuild._is_results_fresh_today({"generated_at": "2000-01-01 00:00:00"}))
        self.assertFalse(dashboard.rebuild._is_results_fresh_today({}))

    @patch("dashboard.rebuild.load_latest_cache_json")
    def test_rebuild_dashboard(self, mock_load_cache):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = (
            [{"symbol": "AAPL", "shares": 10, "cost_basis": 150, "category": "Tech"}],
            [],
            0.0,
        )
        mock_prerun.load_company_names.return_value = {"AAPL": "Apple"}
        stock_prerun_cls = MagicMock(return_value=mock_prerun)

        def cache_side(cache_dir, scope, cat, sym):
            if cat == "fundamental":
                return {"current_price": 160.0, "company_name": "Apple"}
            if cat == "technical":
                return {"signal": "buy"}
            if cat == "news":
                return {"articles": []}
            return {}

        mock_load_cache.side_effect = cache_side

        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = True
        results_file.read_text.return_value = json.dumps(
            {"results": [{"symbol": "AAPL", "current_price": 160.0}]}
        )
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = False
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        gen_html = MagicMock(return_value="<html>ok</html>")
        calc_alloc = MagicMock(
            return_value={"total_value": 1600.0, "total_pnl": 100.0, "cash": 0, "positions": []}
        )

        dashboard.rebuild_dashboard(
            portfolio_file=Path("holdings.csv"),
            config_file=Path("config.json"),
            system_prompt_file=Path("system_prompt.txt"),
            company_names_file=Path("company_names.json"),
            competitors_file=competitors_file,
            results_file=results_file,
            html_file=html_file,
            cache_dir=Path("cache"),
            stock_prerun_cls=stock_prerun_cls,
            calculate_allocation_fn=calc_alloc,
            generate_html_fn=gen_html,
            print_fn=lambda *_args, **_kwargs: None,
        )

        gen_html.assert_called_once()
        rendered_results = gen_html.call_args[0][0]
        self.assertEqual(rendered_results[0]["stock_info"]["symbol"], "AAPL")
        html_file.write_text.assert_called_once()

    @patch("dashboard.rebuild.load_latest_cache_json")
    def test_rebuild_dashboard_with_competitors(self, mock_load_cache):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = (
            [{"symbol": "AAPL", "shares": 1, "cost_basis": 1, "category": "Tech"}],
            [],
            0.0,
        )
        mock_prerun.load_company_names.return_value = {"AAPL": "Apple", "MSFT": "Microsoft"}
        stock_prerun_cls = MagicMock(return_value=mock_prerun)

        def cache_side(cache_dir, scope, cat, sym):
            if scope == "holdings" and cat == "fundamental":
                return {"returnOnEquity": 0.2}
            if scope == "holdings" and cat == "technical":
                return {"ma50": 100, "ma200": 90}
            if scope == "holdings" and cat == "news":
                return {"articles": []}
            if scope == "competitors" and cat == "fundamental":
                return {"returnOnEquity": -0.1}
            if scope == "competitors" and cat == "technical":
                return {"ma50": 50, "ma200": 60}
            if scope == "competitors" and cat == "news":
                return {"articles": []}
            return {}

        mock_load_cache.side_effect = cache_side

        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = True
        results_file.read_text.return_value = json.dumps(
            {"results": [{"symbol": "AAPL", "recommendation": "unknown", "scores": {}, "analysis": "", "current_price": 110.0}]}
        )
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = True
        competitors_file.read_text.return_value = json.dumps(
            {"holdings": {"AAPL": ["MSFT"]}, "competitors": {}}
        )
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        gen_html = MagicMock(return_value="<html>ok</html>")
        calc_alloc = MagicMock(return_value={"total_value": 1, "total_pnl": 0, "cash": 0, "positions": []})

        dashboard.rebuild_dashboard(
            portfolio_file=Path("holdings.csv"),
            config_file=Path("config.json"),
            system_prompt_file=Path("system_prompt.txt"),
            company_names_file=Path("company_names.json"),
            competitors_file=competitors_file,
            results_file=results_file,
            html_file=html_file,
            cache_dir=Path("cache"),
            stock_prerun_cls=stock_prerun_cls,
            calculate_allocation_fn=calc_alloc,
            generate_html_fn=gen_html,
            print_fn=lambda *_args, **_kwargs: None,
        )

        rendered_results = gen_html.call_args[0][0]
        symbols = [r["stock_info"]["symbol"] for r in rendered_results]
        self.assertIn("AAPL", symbols)
        self.assertIn("MSFT", symbols)

    @patch("dashboard.rebuild.load_latest_cache_json")
    def test_rebuild_dashboard_results_error_still_writes_html(self, mock_load_cache):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = (
            [{"symbol": "AAPL", "shares": 1, "cost_basis": 1, "category": "Tech"}],
            [],
            0.0,
        )
        mock_prerun.load_company_names.return_value = {}
        stock_prerun_cls = MagicMock(return_value=mock_prerun)

        def cache_side(cache_dir, scope, cat, sym):
            if scope == "competitors":
                raise RuntimeError("cache fail")
            return {}

        mock_load_cache.side_effect = cache_side

        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = True
        results_file.read_text.side_effect = RuntimeError("bad results")
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = True
        competitors_file.read_text.return_value = json.dumps({"holdings": {"AAPL": ["MSFT"]}})
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        gen_html = MagicMock(return_value="<html>ok</html>")
        calc_alloc = MagicMock(return_value={"total_value": 0, "total_pnl": 0, "cash": 0, "positions": []})

        dashboard.rebuild_dashboard(
            portfolio_file=Path("holdings.csv"),
            config_file=Path("config.json"),
            system_prompt_file=Path("system_prompt.txt"),
            company_names_file=Path("company_names.json"),
            competitors_file=competitors_file,
            results_file=results_file,
            html_file=html_file,
            cache_dir=Path("cache"),
            stock_prerun_cls=stock_prerun_cls,
            calculate_allocation_fn=calc_alloc,
            generate_html_fn=gen_html,
            print_fn=lambda *_args, **_kwargs: None,
        )

        html_file.write_text.assert_called_once()

    def test_rebuild_dashboard_default_import_paths(self):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = ([{"symbol": "AAPL", "shares": 1, "cost_basis": 10, "category": "Tech"}], [], 0.0)
        mock_prerun.load_company_names.return_value = {}
        fake_pre_run = SimpleNamespace(StockPrerun=MagicMock(return_value=mock_prerun))
        fake_portfolio = SimpleNamespace(calculate_allocation=lambda results, cash, options: {
            "total_value": 1, "total_pnl": 0, "cash": 0, "cash_pct": 0, "positions": [], "total_cost": 0, "options_value": 0, "options_pct": 0
        })

        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = False
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = False
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        with patch.dict("sys.modules", {"pre_run": fake_pre_run, "portfolio": fake_portfolio}), \
             patch("dashboard.rebuild.load_latest_cache_json", return_value={}):
            dashboard.rebuild_dashboard(
                portfolio_file=Path("holdings.csv"),
                config_file=Path("config.json"),
                system_prompt_file=Path("system_prompt.txt"),
                company_names_file=Path("company_names.json"),
                competitors_file=competitors_file,
                results_file=results_file,
                html_file=html_file,
                cache_dir=Path("cache"),
                stock_prerun_cls=None,
                calculate_allocation_fn=None,
                generate_html_fn=None,
                print_fn=lambda *_args, **_kwargs: None,
            )
        html_file.write_text.assert_called_once()

    @patch("dashboard.rebuild.load_latest_cache_json")
    def test_rebuild_dashboard_scoring_negative_branches(self, mock_load_cache):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = ([{"symbol": "AAPL", "shares": 1, "cost_basis": 1, "category": "Tech"}], [], 0.0)
        mock_prerun.load_company_names.return_value = {}
        stock_prerun_cls = MagicMock(return_value=mock_prerun)
        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = True
        results_file.read_text.return_value = json.dumps({"results": [{"symbol": "AAPL", "scores": {}}]})
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = True
        competitors_file.read_text.return_value = json.dumps({"AAPL": ["MSFT"]})
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        def side(_cache_dir, scope, cat, sym):
            if cat == "fundamental":
                return {"returnOnEquity": -0.2, "current_price": 90}
            if cat == "technical":
                return {"ma50": 100, "ma200": 110}
            return {"articles": []}

        mock_load_cache.side_effect = side
        dashboard.rebuild_dashboard(
            portfolio_file=Path("holdings.csv"),
            config_file=Path("config.json"),
            system_prompt_file=Path("system_prompt.txt"),
            company_names_file=Path("company_names.json"),
            competitors_file=competitors_file,
            results_file=results_file,
            html_file=html_file,
            cache_dir=Path("cache"),
            stock_prerun_cls=stock_prerun_cls,
            calculate_allocation_fn=lambda *_a, **_k: {"total_value": 1, "total_pnl": 0, "cash": 0, "cash_pct": 0, "positions": [], "total_cost": 0, "options_value": 0, "options_pct": 0},
            generate_html_fn=lambda *_a, **_k: "<html/>",
            print_fn=lambda *_args, **_kwargs: None,
        )
        html_file.write_text.assert_called_once()

    @patch("dashboard.rebuild.load_latest_cache_json")
    def test_rebuild_dashboard_competitor_positive_scoring_and_price_map(self, mock_load_cache):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = ([{"symbol": "AAPL", "shares": 1, "cost_basis": 1, "category": "Tech"}], [], 0.0)
        mock_prerun.load_company_names.return_value = {"MSFT": "Microsoft"}
        stock_prerun_cls = MagicMock(return_value=mock_prerun)
        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = True
        results_file.read_text.return_value = json.dumps({"results": [{"symbol": "MSFT", "current_price": 150.0, "scores": {}}]})
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = True
        competitors_file.read_text.return_value = json.dumps({"holdings": {"AAPL": ["MSFT"]}, "competitors": {}})
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        def side(_cache_dir, scope, cat, _sym):
            if cat == "fundamental":
                return {"returnOnEquity": 0.3, "current_price": 120}
            if cat == "technical":
                return {"ma50": 100, "ma200": 90}
            return {"articles": []}

        mock_load_cache.side_effect = side
        dashboard.rebuild_dashboard(
            portfolio_file=Path("holdings.csv"),
            config_file=Path("config.json"),
            system_prompt_file=Path("system_prompt.txt"),
            company_names_file=Path("company_names.json"),
            competitors_file=competitors_file,
            results_file=results_file,
            html_file=html_file,
            cache_dir=Path("cache"),
            stock_prerun_cls=stock_prerun_cls,
            calculate_allocation_fn=lambda *_a, **_k: {"total_value": 1, "total_pnl": 0, "cash": 0, "cash_pct": 0, "positions": [], "total_cost": 0, "options_value": 0, "options_pct": 0},
            generate_html_fn=lambda *_a, **_k: "<html/>",
            print_fn=lambda *_args, **_kwargs: None,
        )
        html_file.write_text.assert_called_once()

    @patch("dashboard.rebuild.load_latest_cache_json")
    def test_rebuild_dashboard_ignores_stale_results_price_map(self, mock_load_cache):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = ([{"symbol": "AAPL", "shares": 1, "cost_basis": 1, "category": "Tech"}], [], 0.0)
        mock_prerun.load_company_names.return_value = {}
        stock_prerun_cls = MagicMock(return_value=mock_prerun)

        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = True
        results_file.read_text.return_value = json.dumps(
            {
                "generated_at": "2000-01-01 00:00:00",
                "results": [{"symbol": "AAPL", "current_price": 999.0, "recommendation": "add"}],
            }
        )
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = False
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        def side(_cache_dir, _scope, cat, _sym):
            if cat == "fundamental":
                return {"current_price": 100.0}
            if cat == "technical":
                return {"ma50": 90, "ma200": 80}
            return {"articles": []}

        mock_load_cache.side_effect = side
        captured = {}

        def fake_html(results, *_args, **_kwargs):
            captured["price"] = results[0]["stock_data"]["fundamental"].get("current_price")
            return "<html/>"

        dashboard.rebuild_dashboard(
            portfolio_file=Path("holdings.csv"),
            config_file=Path("config.json"),
            system_prompt_file=Path("system_prompt.txt"),
            company_names_file=Path("company_names.json"),
            competitors_file=competitors_file,
            results_file=results_file,
            html_file=html_file,
            cache_dir=Path("cache"),
            stock_prerun_cls=stock_prerun_cls,
            calculate_allocation_fn=lambda *_a, **_k: {"total_value": 1, "total_pnl": 0, "cash": 0, "cash_pct": 0, "positions": [], "total_cost": 0, "options_value": 0, "options_pct": 0},
            generate_html_fn=fake_html,
            print_fn=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(captured["price"], 100.0)

    @patch("dashboard.rebuild.load_latest_cache_json")
    def test_rebuild_dashboard_prefers_technical_current_price(self, mock_load_cache):
        mock_prerun = MagicMock()
        mock_prerun.load_config.return_value = {}
        mock_prerun.load_portfolio.return_value = ([{"symbol": "AAPL", "shares": 1, "cost_basis": 1, "category": "Tech"}], [], 0.0)
        mock_prerun.load_company_names.return_value = {}
        stock_prerun_cls = MagicMock(return_value=mock_prerun)

        results_file = MagicMock(spec=Path)
        results_file.exists.return_value = True
        results_file.read_text.return_value = json.dumps(
            {
                "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "results": [{"symbol": "AAPL", "current_price": 999.0}],
            }
        )
        competitors_file = MagicMock(spec=Path)
        competitors_file.exists.return_value = False
        html_file = MagicMock(spec=Path)
        html_file.absolute.return_value = Path("index.html")

        def side(_cache_dir, _scope, cat, _sym):
            if cat == "fundamental":
                return {"current_price": 100.0}
            if cat == "technical":
                return {"current_price": 110.0, "ma50": 90, "ma200": 80}
            return {"articles": []}

        mock_load_cache.side_effect = side
        captured = {}

        def fake_html(results, *_args, **_kwargs):
            captured["price"] = results[0]["stock_data"]["fundamental"].get("current_price")
            return "<html/>"

        dashboard.rebuild_dashboard(
            portfolio_file=Path("holdings.csv"),
            config_file=Path("config.json"),
            system_prompt_file=Path("system_prompt.txt"),
            company_names_file=Path("company_names.json"),
            competitors_file=competitors_file,
            results_file=results_file,
            html_file=html_file,
            cache_dir=Path("cache"),
            stock_prerun_cls=stock_prerun_cls,
            calculate_allocation_fn=lambda *_a, **_k: {"total_value": 1, "total_pnl": 0, "cash": 0, "cash_pct": 0, "positions": [], "total_cost": 0, "options_value": 0, "options_pct": 0},
            generate_html_fn=fake_html,
            print_fn=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(captured["price"], 110.0)


if __name__ == "__main__":
    unittest.main()
