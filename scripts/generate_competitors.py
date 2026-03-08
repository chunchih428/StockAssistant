#!/usr/bin/env python3
"""
自动生成竞品配置文件
基于 sector/industry 匹配同领域的公司
"""

import json
from pathlib import Path
from collections import defaultdict


def load_portfolio():
    """读取holdings.csv"""
    import csv

    port_path = Path(__file__).parent.parent / 'holdings.csv'
    if not port_path.exists():
        print("❌ 找不到 holdings.csv")
        return []

    stocks = []
    with open(port_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get('股名', '').strip()
            if symbol and not symbol.startswith('#'):
                stocks.append({'symbol': symbol})

    return stocks


def load_fundamental_data():
    """读取所有股票的基本面数据，提取 sector/industry"""
    cache_base = Path(__file__).parent.parent / 'cache' / 'fundamental'
    if not cache_base.exists():
        return {}

    # 找最新的日期目录
    date_dirs = sorted(
        [d for d in cache_base.iterdir() if d.is_dir() and len(d.name) == 10],
        key=lambda d: d.name,
        reverse=True
    )

    if not date_dirs:
        return {}

    latest_dir = date_dirs[0]
    print(f"📂 使用 {latest_dir.name} 的基本面數據")

    fundamentals = {}
    for json_file in latest_dir.glob('*.json'):
        symbol = json_file.stem
        try:
            with open(json_file) as f:
                data = json.load(f)

            fundamentals[symbol] = {
                'sector': data.get('sector', 'Unknown'),
                'industry': data.get('industry', 'Unknown'),
                'marketCap': data.get('marketCap', 0)
            }
        except Exception as e:
            print(f"  ⚠️  讀取 {symbol} 失敗: {e}")

    return fundamentals


def generate_competitors(portfolio, fundamentals, max_competitors=3):
    """為每個股票生成競品列表"""

    # 按 sector + industry 分組
    sector_groups = defaultdict(list)

    for stock in portfolio:
        symbol = stock['symbol']
        if symbol not in fundamentals:
            continue

        fund = fundamentals[symbol]
        sector = fund['sector']
        industry = fund['industry']

        # 使用 sector + industry 作為分組 key
        group_key = f"{sector}|{industry}"
        sector_groups[group_key].append({
            'symbol': symbol,
            'marketCap': fund['marketCap']
        })

    # 為每個股票找競品
    competitors_map = {}

    for stock in portfolio:
        symbol = stock['symbol']
        if symbol not in fundamentals:
            competitors_map[symbol] = []
            continue

        fund = fundamentals[symbol]
        sector = fund['sector']
        industry = fund['industry']
        group_key = f"{sector}|{industry}"

        # 找同組的其他公司
        candidates = [
            s for s in sector_groups[group_key]
            if s['symbol'] != symbol
        ]

        if sector is None or industry is None:
            competitors_map[symbol] = []
            print(f"  {symbol:6s} -> (無 sector/industry 資訊)")
            continue

        # 如果同組太少，擴展到同 sector
        if len(candidates) < max_competitors:
            for key, stocks in sector_groups.items():
                if key.startswith(sector) and key != group_key:
                    for s in stocks:
                        if s['symbol'] != symbol and s['symbol'] not in [c['symbol'] for c in candidates]:
                            candidates.append(s)

        # 按市值排序，選擇最大的幾個（通常是主要競爭對手）
        candidates.sort(key=lambda x: x['marketCap'] or 0, reverse=True)

        # 取前 N 個
        competitors = [c['symbol'] for c in candidates[:max_competitors]]
        competitors_map[symbol] = competitors

        print(f"  {symbol:6s} -> {', '.join(competitors) if competitors else '(無競品)'}")

    return competitors_map


def main():
    print("\n🔍 自動生成競品配置...\n")

    # 1. 讀取 portfolio
    portfolio = load_portfolio()
    if not portfolio:
        return

    print(f"📊 共 {len(portfolio)} 檔股票\n")

    # 2. 讀取基本面數據
    fundamentals = load_fundamental_data()
    if not fundamentals:
        print("❌ 找不到基本面數據")
        return

    print(f"💾 已載入 {len(fundamentals)} 檔基本面數據\n")

    # 3. 生成競品映射
    print("🔗 生成競品關係:\n")
    competitors_map = generate_competitors(portfolio, fundamentals, max_competitors=5)

    # 4. 寫入文件
    output_path = Path(__file__).parent.parent / 'config' / 'competitors.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(competitors_map, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 已生成 {output_path}")
    print(f"   共 {len(competitors_map)} 檔股票的競品配置")


if __name__ == '__main__':
    main()

