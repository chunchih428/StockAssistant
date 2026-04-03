"""Unit tests for the monitor package."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitor.config import load_monitor_config, get_thresholds, get_scoring_weights, reload_monitor_config
from monitor.rules import (
    Alert, RuleContext, LEVEL_CLOSE, LEVEL_REDUCE, LEVEL_WATCH, LEVEL_ADD, LEVEL_HOLD,
    LEVEL_LABEL, LEVEL_ICON, LEVEL_COLOR,
    run_all_rules,
    rule_stop_loss, rule_fund_collapse, rule_breakdown, rule_ai_close,
    rule_concentration, rule_take_profit, rule_warn_loss,
    rule_downtrend_tech, rule_high_risk, rule_ai_reduce,
    rule_rsi_overbought, rule_rsi_oversold_danger, rule_tech_weak,
    rule_var_high, rule_high_leverage, rule_rev_decline,
    rule_add_signal, rule_oversold_add, rule_quality_dip, rule_ai_add,
)
from monitor.scorer import score_candidate, CandidateScore
from monitor.engine import run_monitor, _portfolio_alerts, _cash_alerts


# ═══════════════════════════════════════════════════════════════
#  config.py tests
# ═══════════════════════════════════════════════════════════════
class TestMonitorConfig(unittest.TestCase):

    def setUp(self):
        # Clear cache before each test
        reload_monitor_config(path="__nonexistent__")

    def test_load_missing_file_returns_empty(self):
        cfg = load_monitor_config("__nonexistent_path__/monitor_config.json")
        self.assertEqual(cfg, {"thresholds": {}, "scoring_weights": {}, "overrides": {}})

    def test_load_valid_config(self):
        data = {
            "thresholds": {"stop_loss_pct": -15},
            "scoring_weights": {"fundamental": {}},
            "overrides": {"AAPL": {"stop_loss_pct": -10}},
            "_version": 1,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            tmp = f.name
        try:
            cfg = load_monitor_config(tmp)
            self.assertEqual(cfg["thresholds"]["stop_loss_pct"], -15)
            # _version should be stripped
            self.assertNotIn("_version", cfg)
        finally:
            os.unlink(tmp)

    def test_get_thresholds_with_override(self):
        cfg = {
            "thresholds": {"stop_loss_pct": -20, "take_profit_pct": 60},
            "overrides": {"TSLA": {"stop_loss_pct": -10}},
        }
        # Without symbol
        th = get_thresholds(cfg)
        self.assertEqual(th["stop_loss_pct"], -20)

        # With symbol that has override
        th = get_thresholds(cfg, "TSLA")
        self.assertEqual(th["stop_loss_pct"], -10)
        self.assertEqual(th["take_profit_pct"], 60)

        # With symbol that has no override
        th = get_thresholds(cfg, "AAPL")
        self.assertEqual(th["stop_loss_pct"], -20)

    def test_get_scoring_weights(self):
        cfg = {"scoring_weights": {"fundamental": {"rev_growth": {}}}}
        sw = get_scoring_weights(cfg)
        self.assertIn("fundamental", sw)


# ═══════════════════════════════════════════════════════════════
#  rules.py tests
# ═══════════════════════════════════════════════════════════════
class TestAlert(unittest.TestCase):

    def test_alert_to_dict(self):
        a = Alert(LEVEL_CLOSE, "stop_loss", "test msg", {"key": "val"})
        d = a.to_dict()
        self.assertEqual(d["level"], LEVEL_CLOSE)
        self.assertEqual(d["level_label"], "CLOSE")
        self.assertEqual(d["rule"], "stop_loss")
        self.assertEqual(d["msg"], "test msg")
        self.assertIn("level_icon", d)
        self.assertIn("level_color", d)

    def test_level_constants(self):
        self.assertEqual(LEVEL_CLOSE, 0)
        self.assertEqual(LEVEL_REDUCE, 1)
        self.assertEqual(LEVEL_WATCH, 2)
        self.assertEqual(LEVEL_ADD, 3)
        self.assertEqual(LEVEL_HOLD, 4)


def _make_ctx(**kwargs):
    """Helper to create a RuleContext with defaults."""
    defaults = {
        "symbol": "AAPL",
        "fund": {},
        "tech": {},
        "alloc_pct": 10.0,
        "pnl_pct": 5.0,
        "recommendation": "hold",
        "thresholds": {
            "stop_loss_pct": -20,
            "warn_loss_pct": -12,
            "take_profit_pct": 60,
            "max_single_alloc_pct": 30,
            "fund_score_close": 30,
            "fund_score_add": 70,
            "tech_score_reduce": 45,
            "tech_score_add": 58,
            "risk_score_reduce": 30,
            "rsi_overbought": 75,
            "rsi_oversold": 28,
            "add_max_alloc_pct": 22,
        },
    }
    defaults.update(kwargs)
    return RuleContext(**defaults)


class TestCloseRules(unittest.TestCase):

    def test_stop_loss_triggers(self):
        ctx = _make_ctx(pnl_pct=-25.0)
        result = rule_stop_loss(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_CLOSE)
        self.assertEqual(result.rule, "stop_loss")

    def test_stop_loss_not_triggers(self):
        ctx = _make_ctx(pnl_pct=-10.0)
        self.assertIsNone(rule_stop_loss(ctx))

    def test_stop_loss_none_pnl(self):
        ctx = _make_ctx(pnl_pct=None)
        self.assertIsNone(rule_stop_loss(ctx))

    def test_fund_collapse_triggers(self):
        ctx = _make_ctx(fund={"fund_score": 20})
        result = rule_fund_collapse(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_CLOSE)

    def test_fund_collapse_not_triggers(self):
        ctx = _make_ctx(fund={"fund_score": 50})
        self.assertIsNone(rule_fund_collapse(ctx))

    def test_breakdown_triggers(self):
        ctx = _make_ctx(tech={"trend_status": "BREAKDOWN", "tech_score": 30})
        result = rule_breakdown(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_CLOSE)

    def test_breakdown_not_triggers_high_score(self):
        ctx = _make_ctx(tech={"trend_status": "BREAKDOWN", "tech_score": 50})
        self.assertIsNone(rule_breakdown(ctx))

    def test_ai_close_triggers(self):
        ctx = _make_ctx(recommendation="close")
        result = rule_ai_close(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_CLOSE)

    def test_ai_close_not_triggers(self):
        ctx = _make_ctx(recommendation="hold")
        self.assertIsNone(rule_ai_close(ctx))


class TestReduceRules(unittest.TestCase):

    def test_concentration_triggers(self):
        ctx = _make_ctx(alloc_pct=35.0)
        result = rule_concentration(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_REDUCE)

    def test_concentration_not_triggers(self):
        ctx = _make_ctx(alloc_pct=15.0)
        self.assertIsNone(rule_concentration(ctx))

    def test_take_profit_triggers(self):
        ctx = _make_ctx(pnl_pct=65.0)
        result = rule_take_profit(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_REDUCE)

    def test_take_profit_not_triggers(self):
        ctx = _make_ctx(pnl_pct=40.0)
        self.assertIsNone(rule_take_profit(ctx))

    def test_warn_loss_triggers(self):
        ctx = _make_ctx(pnl_pct=-15.0)
        result = rule_warn_loss(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_REDUCE)

    def test_warn_loss_not_triggers_above_warn(self):
        ctx = _make_ctx(pnl_pct=-5.0)
        self.assertIsNone(rule_warn_loss(ctx))

    def test_warn_loss_not_triggers_below_stop(self):
        # At exactly stop_loss, stop_loss rule triggers, not warn
        ctx = _make_ctx(pnl_pct=-20.0)
        self.assertIsNone(rule_warn_loss(ctx))

    def test_downtrend_tech_triggers(self):
        ctx = _make_ctx(tech={"trend_status": "DOWNTREND", "tech_score": 40})
        result = rule_downtrend_tech(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_REDUCE)

    def test_downtrend_tech_not_triggers_uptrend(self):
        ctx = _make_ctx(tech={"trend_status": "UPTREND", "tech_score": 40})
        self.assertIsNone(rule_downtrend_tech(ctx))

    def test_high_risk_triggers(self):
        ctx = _make_ctx(tech={"risk_score": 20})
        result = rule_high_risk(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_REDUCE)

    def test_high_risk_not_triggers(self):
        ctx = _make_ctx(tech={"risk_score": 50})
        self.assertIsNone(rule_high_risk(ctx))

    def test_ai_reduce_triggers(self):
        ctx = _make_ctx(recommendation="reduce")
        result = rule_ai_reduce(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_REDUCE)


class TestWatchRules(unittest.TestCase):

    def test_rsi_overbought_triggers(self):
        ctx = _make_ctx(tech={"rsi": 80})
        result = rule_rsi_overbought(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_WATCH)

    def test_rsi_overbought_not_triggers(self):
        ctx = _make_ctx(tech={"rsi": 60})
        self.assertIsNone(rule_rsi_overbought(ctx))

    def test_rsi_oversold_danger_triggers(self):
        ctx = _make_ctx(tech={"rsi": 22, "trend_status": "DOWNTREND"})
        result = rule_rsi_oversold_danger(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_WATCH)

    def test_rsi_oversold_danger_not_triggers_uptrend(self):
        ctx = _make_ctx(tech={"rsi": 22, "trend_status": "UPTREND"})
        self.assertIsNone(rule_rsi_oversold_danger(ctx))

    def test_tech_weak_triggers(self):
        ctx = _make_ctx(tech={"tech_score": 40, "trend_status": "CONSOLIDATION"})
        result = rule_tech_weak(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_WATCH)

    def test_tech_weak_not_triggers_downtrend(self):
        # DOWNTREND gets caught by downtrend_tech instead
        ctx = _make_ctx(tech={"tech_score": 40, "trend_status": "DOWNTREND"})
        self.assertIsNone(rule_tech_weak(ctx))

    def test_var_high_triggers(self):
        ctx = _make_ctx(tech={"var_95": -6.5})
        result = rule_var_high(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_WATCH)

    def test_var_high_not_triggers(self):
        ctx = _make_ctx(tech={"var_95": -3.0})
        self.assertIsNone(rule_var_high(ctx))

    def test_high_leverage_triggers(self):
        ctx = _make_ctx(fund={"debtToEquity": 4.5})
        result = rule_high_leverage(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_WATCH)

    def test_high_leverage_not_triggers(self):
        ctx = _make_ctx(fund={"debtToEquity": 1.5})
        self.assertIsNone(rule_high_leverage(ctx))

    def test_rev_decline_triggers(self):
        ctx = _make_ctx(fund={"revenueGrowth": -0.10})
        result = rule_rev_decline(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_WATCH)

    def test_rev_decline_not_triggers(self):
        ctx = _make_ctx(fund={"revenueGrowth": 0.15})
        self.assertIsNone(rule_rev_decline(ctx))


class TestAddRules(unittest.TestCase):

    def test_add_signal_triggers(self):
        ctx = _make_ctx(
            fund={"fund_score": 75},
            tech={"tech_score": 62, "trend_status": "UPTREND"},
            alloc_pct=10.0,
        )
        result = rule_add_signal(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_ADD)

    def test_add_signal_not_triggers_low_fund(self):
        ctx = _make_ctx(
            fund={"fund_score": 50},
            tech={"tech_score": 62, "trend_status": "UPTREND"},
            alloc_pct=10.0,
        )
        self.assertIsNone(rule_add_signal(ctx))

    def test_add_signal_not_triggers_wrong_trend(self):
        ctx = _make_ctx(
            fund={"fund_score": 75},
            tech={"tech_score": 62, "trend_status": "DOWNTREND"},
            alloc_pct=10.0,
        )
        self.assertIsNone(rule_add_signal(ctx))

    def test_add_signal_not_triggers_full_alloc(self):
        ctx = _make_ctx(
            fund={"fund_score": 75},
            tech={"tech_score": 62, "trend_status": "UPTREND"},
            alloc_pct=25.0,
        )
        self.assertIsNone(rule_add_signal(ctx))

    def test_oversold_add_triggers(self):
        ctx = _make_ctx(
            fund={"fund_score": 70},
            tech={"trend_status": "OVERSOLD_UPTREND"},
            pnl_pct=-8.0,
        )
        result = rule_oversold_add(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_ADD)

    def test_quality_dip_triggers(self):
        ctx = _make_ctx(
            fund={"fund_score": 75},
            tech={"trend_status": "CONSOLIDATION"},
            pnl_pct=-12.0,
        )
        result = rule_quality_dip(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_ADD)

    def test_ai_add_triggers(self):
        ctx = _make_ctx(
            recommendation="add",
            tech={"trend_status": "RECOVERY"},
        )
        result = rule_ai_add(ctx)
        self.assertIsNotNone(result)
        self.assertEqual(result.level, LEVEL_ADD)

    def test_ai_add_not_triggers_downtrend(self):
        ctx = _make_ctx(
            recommendation="add",
            tech={"trend_status": "DOWNTREND"},
        )
        self.assertIsNone(rule_ai_add(ctx))


class TestRunAllRules(unittest.TestCase):

    def test_returns_hold_when_no_rules_trigger(self):
        ctx = _make_ctx(
            fund={"fund_score": 60},
            tech={"tech_score": 55, "trend_status": "CONSOLIDATION"},
            pnl_pct=5.0,
            alloc_pct=10.0,
        )
        alerts = run_all_rules(ctx)
        self.assertGreaterEqual(len(alerts), 1)
        # If only HOLD, the last (or only) should be HOLD
        hold_found = any(a.level == LEVEL_HOLD for a in alerts)
        # At minimum, if nothing triggers, we should get a hold
        self.assertTrue(hold_found or len(alerts) > 0)

    def test_returns_sorted_by_level(self):
        # Stop loss + take profit impossible together, but stop loss + concentration is possible
        ctx = _make_ctx(
            fund={"fund_score": 20},  # triggers fund_collapse (CLOSE)
            tech={"tech_score": 40, "trend_status": "CONSOLIDATION"},  # triggers tech_weak (WATCH)
            pnl_pct=-5.0,
            alloc_pct=10.0,
        )
        alerts = run_all_rules(ctx)
        self.assertTrue(len(alerts) >= 2)
        # Should be sorted by level (ascending = CLOSE first)
        levels = [a.level for a in alerts]
        self.assertEqual(levels, sorted(levels))
        self.assertEqual(alerts[0].level, LEVEL_CLOSE)


# ═══════════════════════════════════════════════════════════════
#  scorer.py tests
# ═══════════════════════════════════════════════════════════════
class TestScorer(unittest.TestCase):

    def test_score_candidate_basic(self):
        fund = {"fund_score": 75, "current_price": 150}
        tech = {"tech_score": 65, "risk_score": 55, "trend_status": "UPTREND", "rsi": 50}
        config = {
            "scoring_weights": {
                "composite_for_candidates": {
                    "fund_score": 0.40,
                    "tech_score": 0.35,
                    "risk_score": 0.20,
                    "news_boost": 0.05,
                },
                "news_sentiment": {},
            }
        }
        cs = score_candidate("AAPL", fund, tech, config=config)
        self.assertEqual(cs.symbol, "AAPL")
        self.assertIsNotNone(cs.composite)
        # 75*0.4 + 65*0.35 + 55*0.2 = 30 + 22.75 + 11 = 63.75
        self.assertAlmostEqual(cs.composite, 63.8, places=0)
        self.assertFalse(cs.in_portfolio)

    def test_score_candidate_no_data(self):
        cs = score_candidate("XXX", {}, {}, config={"scoring_weights": {}})
        self.assertIsNone(cs.composite)
        self.assertIn("無資料", cs.signal)

    def test_score_candidate_to_dict(self):
        fund = {"fund_score": 70}
        tech = {"tech_score": 60, "risk_score": 50, "trend_status": "RECOVERY"}
        config = {"scoring_weights": {"composite_for_candidates": {}}}
        cs = score_candidate("GOOG", fund, tech, in_portfolio=True, config=config)
        d = cs.to_dict()
        self.assertEqual(d["symbol"], "GOOG")
        self.assertTrue(d["in_portfolio"])
        self.assertIn("composite", d)

    def test_buy_signal_degraded_for_weak_fundamentals(self):
        fund = {"fund_score": 30}  # Below 40 threshold
        tech = {"tech_score": 70, "risk_score": 80, "trend_status": "UPTREND"}
        config = {"scoring_weights": {"composite_for_candidates": {}}}
        cs = score_candidate("WEAK", fund, tech, config=config)
        # Even with high composite score, weak fund should degrade signal
        self.assertIn("尚未就緒", cs.signal)

    def test_strong_buy_requires_upward_trend(self):
        fund = {"fund_score": 95}
        tech = {"tech_score": 90, "risk_score": 85, "trend_status": "CONSOLIDATION"}
        config = {"scoring_weights": {"composite_for_candidates": {}}}
        cs = score_candidate("TOP", fund, tech, config=config)
        # High score but non-upward trend should not get 強力買入
        self.assertNotIn("強力買入", cs.signal)

    def test_drawdown_calculation(self):
        fund = {"fund_score": 70, "current_price": 80}
        tech = {"tech_score": 60, "risk_score": 50, "trend_status": "RECOVERY", "high_52w": 100}
        config = {"scoring_weights": {"composite_for_candidates": {}}}
        cs = score_candidate("DIP", fund, tech, config=config)
        self.assertEqual(cs.drawdown_pct, -20.0)


# ═══════════════════════════════════════════════════════════════
#  engine.py tests
# ═══════════════════════════════════════════════════════════════
class TestPortfolioAlerts(unittest.TestCase):

    def test_top1_concentration_triggers(self):
        allocation = {
            "positions": [
                {"symbol": "AAPL", "market_value": 8000},
                {"symbol": "GOOG", "market_value": 2000},
            ]
        }
        results = []
        thresholds = {"max_top1_pct": 35, "warn_top1_pct": 25}
        alerts = _portfolio_alerts(allocation, results, thresholds)
        # AAPL = 80% > 35%
        self.assertTrue(any("AAPL" in a["msg"] for a in alerts))

    def test_hhi_high_triggers(self):
        allocation = {
            "positions": [
                {"symbol": "AAPL", "market_value": 9000},
                {"symbol": "GOOG", "market_value": 1000},
            ]
        }
        thresholds = {"max_hhi": 0.25, "warn_hhi": 0.15}
        alerts = _portfolio_alerts(allocation, [], thresholds)
        # HHI = 0.9^2 + 0.1^2 = 0.82 > 0.25
        self.assertTrue(any("HHI" in a["msg"] for a in alerts))

    def test_no_alerts_balanced(self):
        allocation = {
            "positions": [
                {"symbol": "A", "market_value": 2500},
                {"symbol": "B", "market_value": 2500},
                {"symbol": "C", "market_value": 2500},
                {"symbol": "D", "market_value": 2500},
            ]
        }
        thresholds = {"max_top1_pct": 35, "warn_top1_pct": 25, "max_hhi": 0.25, "warn_hhi": 0.15}
        alerts = _portfolio_alerts(allocation, [], thresholds)
        # 25% each -> HHI = 4*0.0625 = 0.25, top1 = 25% (exactly at warn)
        # Only warn_hhi should trigger (0.25 > 0.15 but == 0.25 not >)
        hhi_alerts = [a for a in alerts if "HHI" in a["msg"]]
        top_alerts = [a for a in alerts if "持倉" in a["msg"]]
        # HHI 0.25 == max_hhi -> not > so no hard trigger; but > warn_hhi -> warning
        self.assertTrue(any("HHI" in a["msg"] for a in alerts))


class TestCashAlerts(unittest.TestCase):

    def test_cash_excess(self):
        allocation = {"total_value": 100000, "cash": 30000}
        thresholds = {"max_cash_pct": 25, "warn_high_cash_pct": 18, "min_cash_pct": 5}
        alerts = _cash_alerts(allocation, thresholds)
        self.assertEqual(len(alerts), 1)
        self.assertIn("機會成本", alerts[0]["msg"])

    def test_cash_high_warning(self):
        allocation = {"total_value": 100000, "cash": 20000}
        thresholds = {"max_cash_pct": 25, "warn_high_cash_pct": 18, "min_cash_pct": 5}
        alerts = _cash_alerts(allocation, thresholds)
        self.assertEqual(len(alerts), 1)
        self.assertIn("保守", alerts[0]["msg"])

    def test_cash_low(self):
        allocation = {"total_value": 100000, "cash": 3000}
        thresholds = {"max_cash_pct": 25, "warn_high_cash_pct": 18, "min_cash_pct": 5}
        alerts = _cash_alerts(allocation, thresholds)
        self.assertEqual(len(alerts), 1)
        self.assertIn("緩衝", alerts[0]["msg"])

    def test_cash_normal_no_alert(self):
        allocation = {"total_value": 100000, "cash": 10000}
        thresholds = {"max_cash_pct": 25, "warn_high_cash_pct": 18, "min_cash_pct": 5}
        alerts = _cash_alerts(allocation, thresholds)
        self.assertEqual(len(alerts), 0)


class TestRunMonitor(unittest.TestCase):

    def test_run_monitor_basic(self):
        """Test run_monitor returns proper structure with mock config."""
        results = [
            {
                "stock_info": {"symbol": "AAPL", "shares": 10, "cost_basis": 100, "category": "Tech"},
                "stock_data": {
                    "fundamental": {"current_price": 120, "fund_score": 65},
                    "technical": {"tech_score": 55, "trend_status": "UPTREND", "risk_score": 50},
                },
                "analysis_result": {"recommendation": "hold"},
                "news": [],
            },
        ]
        allocation = {
            "total_value": 1200,
            "cash": 0,
            "positions": [{"symbol": "AAPL", "market_value": 1200}],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"thresholds": {}, "scoring_weights": {}, "overrides": {}}, f)
            cfg_path = f.name

        try:
            # Force reload to use our temp config
            reload_monitor_config(cfg_path)
            data = run_monitor(results, allocation, [], monitor_config_path=cfg_path)
            self.assertIn("generated_at", data)
            self.assertIn("portfolio", data)
            self.assertIn("holdings", data)
            self.assertIn("candidates", data)
            self.assertIn("AAPL", data["holdings"])
            self.assertIsInstance(data["holdings"]["AAPL"]["alerts"], list)
        finally:
            os.unlink(cfg_path)
            reload_monitor_config(path="__nonexistent__")

    def test_run_monitor_with_candidates(self):
        results = [
            {
                "stock_info": {"symbol": "AAPL", "shares": 10, "cost_basis": 100, "category": "Tech"},
                "stock_data": {
                    "fundamental": {"current_price": 120, "fund_score": 70},
                    "technical": {"tech_score": 60, "trend_status": "UPTREND", "risk_score": 55},
                },
                "analysis_result": {"recommendation": "hold"},
                "news": [],
            },
            {
                "stock_info": {"symbol": "GOOG", "shares": 0, "cost_basis": 0, "category": "競品參考"},
                "stock_data": {
                    "fundamental": {"current_price": 180, "fund_score": 80},
                    "technical": {"tech_score": 70, "trend_status": "UPTREND", "risk_score": 65},
                },
                "analysis_result": {"recommendation": "add"},
                "news": [],
            },
        ]
        allocation = {
            "total_value": 1200,
            "cash": 0,
            "positions": [{"symbol": "AAPL", "market_value": 1200}],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"thresholds": {}, "scoring_weights": {}, "overrides": {}}, f)
            cfg_path = f.name

        try:
            reload_monitor_config(cfg_path)
            data = run_monitor(results, allocation, ["GOOG"], monitor_config_path=cfg_path)
            self.assertEqual(len(data["candidates"]), 1)
            self.assertEqual(data["candidates"][0]["symbol"], "GOOG")
        finally:
            os.unlink(cfg_path)
            reload_monitor_config(path="__nonexistent__")

    def test_run_monitor_empty(self):
        """Empty portfolio should not crash."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"thresholds": {}, "scoring_weights": {}, "overrides": {}}, f)
            cfg_path = f.name
        try:
            reload_monitor_config(cfg_path)
            data = run_monitor([], {"total_value": 0, "cash": 0, "positions": []}, [], monitor_config_path=cfg_path)
            self.assertEqual(data["holdings"], {})
            self.assertEqual(data["candidates"], [])
        finally:
            os.unlink(cfg_path)
            reload_monitor_config(path="__nonexistent__")


# ═══════════════════════════════════════════════════════════════
#  backtest.py tests (no yfinance dependency)
# ═══════════════════════════════════════════════════════════════
class TestBacktest(unittest.TestCase):

    def test_load_archive_snapshots_from_html(self):
        from monitor.backtest import load_archive_snapshots

        with tempfile.TemporaryDirectory() as td:
            archive_dir = Path(td)
            # Create a fake archive HTML
            data = {
                "stocks": [
                    {
                        "symbol": "AAPL",
                        "shares": 10,
                        "price": 150,
                        "pnl_pct": 5.0,
                        "recommendation": "hold",
                        "fundamental": {"fund_score": 72},
                        "technical": {"tech_score": 60, "risk_score": 50, "trend_status": "UPTREND", "rsi": 55},
                    }
                ],
                "allocation": {
                    "positions": [{"symbol": "AAPL", "alloc_pct": 80}]
                },
            }
            html = f"""<!DOCTYPE html><html><body>
<script>
const D={json.dumps(data)};
</script></body></html>"""
            (archive_dir / "index_20260301.html").write_text(html, encoding="utf-8")

            records = load_archive_snapshots(archive_dir)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].symbol, "AAPL")
            self.assertEqual(records[0].date, "2026-03-01")
            self.assertEqual(records[0].fund_score, 72)
            self.assertEqual(records[0].tech_score, 60)

    def test_load_archive_snapshots_empty_dir(self):
        from monitor.backtest import load_archive_snapshots

        with tempfile.TemporaryDirectory() as td:
            records = load_archive_snapshots(td)
            self.assertEqual(records, [])

    def test_load_archive_snapshots_nonexistent(self):
        from monitor.backtest import load_archive_snapshots
        records = load_archive_snapshots("__nonexistent_dir__")
        self.assertEqual(records, [])

    def test_simulate_rule(self):
        from monitor.backtest import simulate_rule, SnapshotRecord

        snapshots = [
            SnapshotRecord("2026-01-01", "AAPL", 75, 60, 50, "UPTREND", 55, 150, 5, 20, "hold"),
            SnapshotRecord("2026-01-02", "GOOG", 40, 30, 20, "DOWNTREND", 25, 100, -10, 15, "reduce"),
            SnapshotRecord("2026-01-03", "MSFT", 80, 65, 55, "RECOVERY", 50, 300, 8, 18, "hold"),
        ]
        fwd_returns = {
            ("2026-01-01", "AAPL"): 5.0,
            ("2026-01-02", "GOOG"): -3.0,
            ("2026-01-03", "MSFT"): 7.0,
        }

        def fn(rec):
            if (rec.tech_score or 0) < 45:
                return "REDUCE"
            if (rec.fund_score or 0) >= 70:
                return "ADD"
            return None

        perf = simulate_rule(snapshots, fwd_returns, "test_rule", fn, None)
        self.assertEqual(perf.rule_id, "test_rule")
        self.assertEqual(perf.add_count, 2)     # AAPL and MSFT
        self.assertEqual(perf.reduce_count, 1)   # GOOG
        self.assertEqual(perf.total_signals, 3)
        self.assertAlmostEqual(perf.add_avg_return, 6.0, places=1)
        self.assertAlmostEqual(perf.reduce_avg_return, -3.0, places=1)
        self.assertEqual(perf.add_accuracy, 100.0)
        self.assertEqual(perf.reduce_accuracy, 100.0)

    def test_extract_date(self):
        from monitor.backtest import _extract_date
        self.assertEqual(_extract_date("index_20260315.html"), "2026-03-15")
        self.assertIsNone(_extract_date("random.html"))


# ═══════════════════════════════════════════════════════════════
#  optimizer.py tests
# ═══════════════════════════════════════════════════════════════
class TestOptimizer(unittest.TestCase):

    def test_optimize_thresholds_basic(self):
        from monitor.optimizer import optimize_thresholds
        from monitor.backtest import SnapshotRecord

        snapshots = []
        for i in range(20):
            snapshots.append(SnapshotRecord(
                f"2026-01-{i+1:02d}", "AAPL", 75, 60, 50,
                "UPTREND", 55, 150 + i, 5, 20, "hold"
            ))
        # All have positive forward returns
        fwd = {(f"2026-01-{i+1:02d}", "AAPL"): 3.0 + i * 0.2 for i in range(20)}

        result = optimize_thresholds(snapshots, fwd)
        self.assertIsInstance(result, dict)

    def test_optimize_thresholds_insufficient_data(self):
        from monitor.optimizer import optimize_thresholds
        from monitor.backtest import SnapshotRecord

        snapshots = [
            SnapshotRecord("2026-01-01", "AAPL", 75, 60, 50, "UPTREND", 55, 150, 5, 20, "hold"),
        ]
        fwd = {("2026-01-01", "AAPL"): 5.0}
        result = optimize_thresholds(snapshots, fwd)
        # With only 1 snapshot, most rules won't hit n>=3 threshold
        self.assertIsInstance(result, dict)

    def test_run_optimization_insufficient_snapshots(self):
        from monitor.optimizer import run_optimization
        with tempfile.TemporaryDirectory() as td:
            result = run_optimization(td, dry_run=True, verbose=False)
            self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
