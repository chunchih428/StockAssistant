#!/usr/bin/env python3
import csv
import re
from pathlib import Path
from collections import defaultdict

import yfinance as yf


class PortfolioService:
    def __init__(self, portfolio_file):
        self.portfolio_file = Path(portfolio_file)

    @staticmethod
    def parse_option(symbol):
        m = re.fullmatch(r"([A-Z]+)\((\d{2})(\d{2})(\d{2})([CP])(\d{8})\)", symbol.strip().upper())
        if not m:
            return None
        underlying, yy, mm, dd, cp, strike_raw = m.groups()
        expiry = f"20{yy}-{mm}-{dd}"
        return {
            "underlying": underlying,
            "expiry": expiry,
            "type": "Call" if cp == "C" else "Put",
            "strike": int(strike_raw) / 1000.0,
        }

    def load_portfolio(self, csv_reader_cls=None, open_fn=None):
        stocks_map = {}
        options = []
        cash = 0.0

        if csv_reader_cls is None:
            csv_reader_cls = csv.DictReader
        if open_fn is None:
            open_fn = open

        print(f"  [Portfolio] 載入持股: {self.portfolio_file}")
        with open_fn(self.portfolio_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv_reader_cls(f)
            for row in reader:
                if isinstance(getattr(row, "values", None), list) and len(row.values) >= 4:
                    symbol_raw, shares_raw, cost_raw, category_raw = row.values[:4]
                else:
                    symbol_raw = (
                        row.get("symbol")
                        or row.get("ticker")
                        or row.get("代號")
                        or row.get("股名")
                        or ""
                    )
                    shares_raw = row.get("shares")
                    if shares_raw in (None, ""):
                        shares_raw = row.get("股數", 0)
                    cost_raw = row.get("cost_basis")
                    if cost_raw in (None, ""):
                        cost_raw = row.get("成本")
                    if cost_raw in (None, ""):
                        cost_raw = row.get("買價")
                    if cost_raw in (None, ""):
                        cost_raw = row.get("買入價")
                    if cost_raw in (None, ""):
                        cost_raw = row.get("price", 0)
                    category_raw = row.get("category")
                    if category_raw in (None, ""):
                        category_raw = row.get("類別", "")

                symbol = str(symbol_raw).strip().upper()
                if not symbol:
                    continue

                try:
                    shares = float(shares_raw or 0)
                    cost = float(cost_raw or 0)
                except Exception:
                    continue
                category = str(category_raw or "").strip()

                if symbol == "CASH":
                    cash += shares * cost if shares else cost
                    continue

                option_info = self.parse_option(symbol)
                if option_info:
                    option_info.update(
                        {
                            "symbol": symbol,
                            "shares": int(shares) if float(shares).is_integer() else shares,
                            "cost_basis": cost,
                            "total_cost": shares * cost,
                            "category": category,
                        }
                    )
                    options.append(option_info)
                    continue

                cur = stocks_map.get(
                    symbol,
                    {"symbol": symbol, "shares": 0.0, "cost_basis": 0.0, "category": ""},
                )
                prev_shares = cur["shares"]
                prev_cost = cur["cost_basis"]
                total_shares = prev_shares + shares
                if total_shares == 0:
                    weighted_cost = cost
                else:
                    weighted_cost = (prev_shares * prev_cost + shares * cost) / total_shares

                cur["shares"] = total_shares
                cur["cost_basis"] = weighted_cost
                if category:
                    cur["category"] = category
                stocks_map[symbol] = cur

        stocks = list(stocks_map.values())
        print(f"  [Portfolio] 股票 {len(stocks)} 檔 | 選擇權 {len(options)} 筆 | 現金 ${cash:,.2f}")
        return stocks, options, cash

    @staticmethod
    def _safe_float(value, default=None):
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _to_yf_contract_symbol(option):
        symbol = str(option.get("symbol", "")).strip().upper()
        if not symbol:
            return ""
        return symbol.replace("(", "").replace(")", "")

    @staticmethod
    def _pick_option_quote(row):
        last_price = PortfolioService._safe_float(row.get("lastPrice"), None)
        if last_price and last_price > 0:
            return last_price
        bid = PortfolioService._safe_float(row.get("bid"), None)
        ask = PortfolioService._safe_float(row.get("ask"), None)
        if bid is not None and ask is not None and bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        return None

    @staticmethod
    def enrich_option_market_data(options, ticker_cls=None, print_fn=print):
        if ticker_cls is None:
            ticker_cls = yf.Ticker
        if not options:
            return options

        grouped = defaultdict(list)
        for option in options:
            underlying = str(option.get("underlying", "")).strip().upper()
            expiry = str(option.get("expiry", "")).strip()
            if underlying and expiry:
                grouped[(underlying, expiry)].append(option)

        for (underlying, expiry), group in grouped.items():
            try:
                chain = ticker_cls(underlying).option_chain(expiry)
            except Exception as exc:
                print_fn(f"    [Options] {underlying} {expiry} 報價失敗: {exc}")
                continue

            for option in group:
                option_type = option.get("type")
                quotes_df = chain.calls if option_type == "Call" else chain.puts
                if quotes_df is None or getattr(quotes_df, "empty", True):
                    continue

                row = None
                yf_contract_symbol = PortfolioService._to_yf_contract_symbol(option)
                if yf_contract_symbol and "contractSymbol" in quotes_df.columns:
                    hit = quotes_df.loc[quotes_df["contractSymbol"] == yf_contract_symbol]
                    if not hit.empty:
                        row = hit.iloc[0]

                if row is None and "strike" in quotes_df.columns:
                    strike = PortfolioService._safe_float(option.get("strike"), None)
                    if strike is not None:
                        hit = quotes_df.loc[(quotes_df["strike"] - strike).abs() < 0.01]
                        if not hit.empty:
                            row = hit.iloc[0]

                if row is None:
                    continue

                premium = PortfolioService._pick_option_quote(row)
                if premium is None:
                    continue

                current_price = premium * 100.0
                shares = PortfolioService._safe_float(option.get("shares"), 0.0) or 0.0
                total_cost = PortfolioService._safe_float(option.get("total_cost"), 0.0) or 0.0
                market_value = current_price * shares
                pnl = market_value - total_cost
                pnl_pct = (pnl / total_cost * 100.0) if total_cost else 0.0

                option["current_price"] = current_price
                option["market_value"] = market_value
                option["pnl"] = pnl
                option["pnl_pct"] = pnl_pct

            print_fn(f"    [Options] {underlying} {expiry} 已更新 {len(group)} 筆報價")
        return options

    @staticmethod
    def calculate_allocation(results, cash, options):
        positions = []
        total_value = cash

        for r in results:
            price = r.get("stock_data", {}).get("fundamental", {}).get("current_price")
            shares = r["stock_info"]["shares"]
            cost_total = r["stock_info"]["cost_basis"] * shares
            market_value = (price or 0) * shares
            total_value += market_value
            pnl = market_value - cost_total if price else 0
            pnl_pct = ((price - r["stock_info"]["cost_basis"]) / r["stock_info"]["cost_basis"] * 100) if price and r["stock_info"]["cost_basis"] else 0

            positions.append(
                {
                    "symbol": r["stock_info"]["symbol"],
                    "shares": shares,
                    "cost_basis": r["stock_info"]["cost_basis"],
                    "cost_total": cost_total,
                    "market_value": market_value,
                    "current_price": price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "category": r["stock_info"].get("category", ""),
                }
            )

        options_cost = 0.0
        options_value = 0.0
        options_pnl = 0.0
        for option in options:
            total_cost = PortfolioService._safe_float(option.get("total_cost"), 0.0) or 0.0
            market_value = PortfolioService._safe_float(option.get("market_value"), None)
            if market_value is None:
                market_value = total_cost
            option_pnl = market_value - total_cost
            option_pnl_pct = (option_pnl / total_cost * 100.0) if total_cost else 0.0

            option["market_value"] = market_value
            option["pnl"] = option_pnl
            option["pnl_pct"] = option_pnl_pct

            options_cost += total_cost
            options_value += market_value
            options_pnl += option_pnl

        total_value += options_value

        for p in positions:
            p["alloc_pct"] = (p["market_value"] / total_value * 100) if total_value > 0 else 0

        positions.sort(key=lambda x: x["market_value"], reverse=True)

        return {
            "total_value": total_value,
            "total_cost": sum(p["cost_total"] for p in positions) + options_cost + cash,
            "total_pnl": sum(p["pnl"] for p in positions) + options_pnl,
            "cash": cash,
            "cash_pct": (cash / total_value * 100) if total_value > 0 else 0,
            "options_value": options_value,
            "options_cost": options_cost,
            "options_pnl": options_pnl,
            "options_pct": (options_value / total_value * 100) if total_value > 0 else 0,
            "positions": positions,
        }


def parse_option(symbol):
    return PortfolioService.parse_option(symbol)


def load_portfolio(portfolio_file):
    return PortfolioService(portfolio_file).load_portfolio()


def calculate_allocation(results, cash, options):
    return PortfolioService.calculate_allocation(results, cash, options)


def enrich_option_market_data(options, ticker_cls=None, print_fn=print):
    return PortfolioService.enrich_option_market_data(options, ticker_cls=ticker_cls, print_fn=print_fn)
