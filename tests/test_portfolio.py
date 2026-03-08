import os
import sys
import unittest
from unittest.mock import mock_open, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from portfolio import PortfolioService, calculate_allocation
import portfolio


class TestPortfolioService(unittest.TestCase):
    def test_parse_option_call(self):
        r = PortfolioService.parse_option("SOFI(270115C00010000)")
        self.assertIsNotNone(r)
        self.assertEqual(r["underlying"], "SOFI")
        self.assertEqual(r["expiry"], "2027-01-15")
        self.assertEqual(r["type"], "Call")
        self.assertEqual(r["strike"], 10.0)

    def test_parse_option_invalid(self):
        self.assertIsNone(PortfolioService.parse_option("INVALID"))

    @patch("portfolio.csv.DictReader")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_portfolio(self, _mock_file, mock_csv_reader):
        class FakeRow:
            def __init__(self, symbol, shares, cost, category):
                self.values = [symbol, shares, cost, category]

            def get(self, _key, _default=None):
                return None

        mock_csv_reader.return_value = [
            FakeRow("AAPL", "10", "150.0", "Tech"),
            FakeRow("AAPL", "10", "160.0", "Tech"),
            FakeRow("cash", "1", "1000.0", ""),
            FakeRow("SOFI(270115C00010000)", "2", "1.5", "Speculative"),
        ]

        svc = PortfolioService("data/portfolio.csv")
        stocks, options, cash = svc.load_portfolio()

        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0]["symbol"], "AAPL")
        self.assertEqual(stocks[0]["shares"], 20.0)
        self.assertEqual(stocks[0]["cost_basis"], 155.0)
        self.assertEqual(cash, 1000.0)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["underlying"], "SOFI")
        self.assertEqual(options[0]["shares"], 2)

    @patch("portfolio.csv.DictReader")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_portfolio_dict_branch_price_fallback(self, _mock_file, mock_csv_reader):
        mock_csv_reader.return_value = [
            {"symbol": "AAPL", "shares": "1", "cost_basis": "", "price": "123", "category": "Tech"},
        ]
        svc = PortfolioService("data/portfolio.csv")
        stocks, options, cash = svc.load_portfolio()
        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0]["cost_basis"], 123.0)
        self.assertEqual(options, [])
        self.assertEqual(cash, 0.0)


class TestPortfolioAllocation(unittest.TestCase):
    def test_calculate_allocation(self):
        results = [
            {
                "stock_info": {"symbol": "AAPL", "shares": 10, "cost_basis": 100.0},
                "stock_data": {"fundamental": {"current_price": 110.0}},
            },
            {
                "stock_info": {"symbol": "MSFT", "shares": 5, "cost_basis": 200.0},
                "stock_data": {"fundamental": {"current_price": 190.0}},
            },
        ]
        alloc = calculate_allocation(results, cash=100.0, options=[{"total_cost": 50.0}])

        self.assertEqual(alloc["cash"], 100.0)
        self.assertEqual(alloc["options_value"], 50.0)
        self.assertGreater(alloc["total_value"], 0)
        self.assertEqual(len(alloc["positions"]), 2)

    def test_module_level_wrappers(self):
        self.assertIsNotNone(portfolio.parse_option("SOFI(270115C00010000)"))
        with patch("portfolio.PortfolioService.load_portfolio", return_value=([], [], 0.0)):
            self.assertEqual(portfolio.load_portfolio("x.csv"), ([], [], 0.0))
        with patch("portfolio.PortfolioService.enrich_option_market_data", return_value=[]):
            self.assertEqual(portfolio.enrich_option_market_data([]), [])

    @patch("portfolio.yf.Ticker")
    def test_enrich_option_market_data(self, mock_ticker):
        class _Mask:
            def __init__(self, base):
                self.base = base

            def __and__(self, other):
                return _Mask([a and b for a, b in zip(self.base, other.base)])

        class _Series:
            def __init__(self, values):
                self.values = values

            def __eq__(self, other):
                return _Mask([v == other for v in self.values])

            def __sub__(self, other):
                return _Series([v - other for v in self.values])

            def abs(self):
                return _Series([abs(v) for v in self.values])

            def __lt__(self, other):
                return _Mask([v < other for v in self.values])

        class _ILoc:
            def __init__(self, rows):
                self.rows = rows

            def __getitem__(self, idx):
                return self.rows[idx]

        class _DF:
            def __init__(self, rows):
                self.rows = rows
                self.columns = ["contractSymbol", "strike", "lastPrice", "bid", "ask"]
                self.empty = len(rows) == 0
                self.iloc = _ILoc(rows)

            def __getitem__(self, key):
                return _Series([r.get(key) for r in self.rows])

            @property
            def loc(self):
                parent = self

                class _Loc:
                    def __getitem__(self, mask):
                        rows = [r for r, keep in zip(parent.rows, mask.base) if keep]
                        return _DF(rows)

                return _Loc()

        chain = unittest.mock.MagicMock()
        chain.calls = _DF([{"contractSymbol": "SOFI270115C00010000", "strike": 10.0, "lastPrice": 2.5, "bid": 2.4, "ask": 2.6}])
        chain.puts = _DF([])
        mock_ticker.return_value.option_chain.return_value = chain

        options = [{
            "symbol": "SOFI(270115C00010000)",
            "underlying": "SOFI",
            "expiry": "2027-01-15",
            "type": "Call",
            "strike": 10.0,
            "shares": 2,
            "total_cost": 300.0,
            "cost_basis": 150.0,
        }]

        PortfolioService.enrich_option_market_data(options, print_fn=lambda *_a, **_k: None)
        self.assertEqual(options[0]["current_price"], 250.0)
        self.assertEqual(options[0]["market_value"], 500.0)
        self.assertEqual(options[0]["pnl"], 200.0)

    def test_calculate_allocation_with_option_market_value(self):
        alloc = calculate_allocation(
            results=[],
            cash=0.0,
            options=[{"total_cost": 100.0, "market_value": 140.0}],
        )
        self.assertEqual(alloc["options_value"], 140.0)
        self.assertEqual(alloc["options_pnl"], 40.0)
        self.assertEqual(alloc["total_pnl"], 40.0)


if __name__ == "__main__":
    unittest.main()
