#!/usr/bin/env python3
"""
Validate competitors.json format and consistency.
Usage: python validate_competitors.py [path_to_competitors.json] [path_to_holdings.csv]
"""

import json
import csv
import sys
from pathlib import Path


import re

def load_portfolio(csv_path: str) -> list[str]:
    """Read unique tickers from holdings.csv"""
    tickers = set()
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get('股名', '').strip()
            if symbol:
                m = re.match(r'^(\w+)\(', symbol)
                if m:
                    tickers.add(m.group(1))
                else:
                    tickers.add(symbol)
    return sorted(tickers)


def validate(competitors_path: str, csv_path: str) -> list[str]:
    errors = []
    warnings = []

    # Load competitors.json
    try:
        with open(competitors_path, encoding='utf-8') as f:
            _raw_data = json.load(f)

        data = {}
        if 'holdings' in _raw_data or 'competitors' in _raw_data:
            data.update(_raw_data.get('holdings', {}))
            data.update(_raw_data.get('competitors', {}))
        else:
            data = _raw_data
    except Exception as e:
        return [f"❌ Cannot parse JSON: {e}"], []

    if not isinstance(data, dict):
        return [f"❌ Root must be an object, got {type(data).__name__}"], []

    # Load portfolio
    portfolio_tickers = load_portfolio(csv_path)

    # Check: every portfolio ticker should be a key
    for t in portfolio_tickers:
        if t not in data:
            errors.append(f"❌ Missing portfolio ticker: {t}")

    # Check: no extra keys beyond portfolio
    for key in data:
        if key not in portfolio_tickers:
            warnings.append(f"⚠️  Extra key not in portfolio: {key}")

    # Check each entry
    skip_types = {'cash'}
    etf_like = {'QQQ', 'VOO', 'IBIT', 'AMZU', 'GGLL'}

    for ticker, competitors in data.items():
        if not isinstance(competitors, list):
            errors.append(f"❌ {ticker}: value must be array, got {type(competitors).__name__}")
            continue

        # ETFs/options/cash should have empty array
        is_special = (
            ticker.lower() in skip_types
            or ticker in etf_like
            or '(' in ticker
        )
        if is_special and len(competitors) > 0:
            warnings.append(f"⚠️  {ticker}: ETF/option/cash should have empty competitors, got {len(competitors)}")

        # Real stocks should have at least 1 competitor
        if not is_special and len(competitors) == 0:
            warnings.append(f"⚠️  {ticker}: real stock has no competitors")

        # Check for duplicates
        if len(competitors) != len(set(competitors)):
            errors.append(f"❌ {ticker}: duplicate competitors found")

        # Check all values are strings
        for c in competitors:
            if not isinstance(c, str):
                errors.append(f"❌ {ticker}: competitor must be string, got {type(c).__name__}")

    return errors, warnings


def main():
    base = Path(__file__).resolve().parent.parent.parent
    competitors_path = sys.argv[1] if len(sys.argv) > 1 else str(base / 'competitors.json')
    if len(sys.argv) > 2:
        csv_path = sys.argv[2]
    else:
        primary = base / 'config' / 'holdings.csv'
        legacy = base / 'holdings.csv'
        csv_path = str(primary if primary.exists() else legacy)

    print(f"\n🔍 Validating {competitors_path}")
    print(f"   Portfolio: {csv_path}\n")

    errors, warnings = validate(competitors_path, csv_path)

    for w in warnings:
        print(f"  {w}")
    for e in errors:
        print(f"  {e}")

    if not errors and not warnings:
        print("  ✅ All checks passed!")
    elif not errors:
        print(f"\n  ✅ No errors, {len(warnings)} warning(s)")
    else:
        print(f"\n  ❌ {len(errors)} error(s), {len(warnings)} warning(s)")
        sys.exit(1)


if __name__ == '__main__':
    main()
