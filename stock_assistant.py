#!/usr/bin/env python3
"""
股票分析儀表板 (Stock Analysis Dashboard)

讀取持股 CSV → 抓取基本面/技術面/消息面 → Claude AI 分析 → 生成 HTML 儀表板

Usage:
    python stock_assistant.py              # 分析所有持股
    python stock_assistant.py AAPL TSLA    # 只分析指定 Ticker
    python stock_assistant.py --open       # 開啟上次生成的報告
    python stock_assistant.py --fresh      # 智慧重抓：清 news+technical，fundamental 依財報日期判斷
    python stock_assistant.py --html-only # 只重新生成 index.html，不重新檢查/抓取任何 cache
    python stock_assistant.py --skip-competitor-bootstrap | -sc  # 跳過競品自動補全與名稱補齊
    python stock_assistant.py --test      # 測試模式：讀取 tests/test_e2e/holdings.csv，輸出到 tests/test_e2e/test_cache/
"""

import sys
import json
import time
import datetime
import re
import webbrowser
from pathlib import Path

# ── 檢查相依套件 ─────────────────────────────────────────────
_REQUIRED = {
    "anthropic": "anthropic",
    "yfinance": "yfinance",
    "dotenv": "python-dotenv",
    "markdown": "markdown",
    "numpy": "numpy",
    "pydantic": "pydantic",
}
_missing = []
for _mod, _pkg in _REQUIRED.items():
    try:
        __import__(_mod)
    except ImportError:
        _missing.append(_pkg)
if _missing:
    print(f"\n[錯誤] 缺少以下套件: {', '.join(_missing)}")
    print(f"  請執行: pip install {' '.join(_missing)}")
    print(f"  或執行: pip install -r requirements.txt\n")
    sys.exit(1)


import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

from dashboard import generate_html, count_recommendations, rebuild_dashboard
from pre_run import StockPrerun
from market_data.fundamental import fetch_fundamental, extract_current_price
from market_data.technical import fetch_technical
from portfolio import calculate_allocation, enrich_option_market_data
from market_data.analysis_ai import analyze_with_claude


from market_data.information import fetch_news
from cache_manager import CacheManager


# ── 路徑設定 ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
RESULTS_FILE = OUTPUT_DIR / "results.json"
HTML_FILE = BASE_DIR / "index.html"
CONFIG_FILE = BASE_DIR / "config" / "config.json"
PORTFOLIO_FILE = BASE_DIR / "holdings.csv"
SYSTEM_PROMPT_FILE = BASE_DIR / "system_prompt.txt"
CACHE_DIR = BASE_DIR / "cache"
COMPANY_NAMES_FILE = BASE_DIR / "config" / "company_names.json"
COMPETITORS_FILE = BASE_DIR / "config" / "competitors.json"
CANDIDATES_FILE = BASE_DIR / "candidates.txt"


def configure_yfinance_cache():
    """Force yfinance sqlite cache into a writable project-local directory."""
    yf_cache_dir = CACHE_DIR / "_yfinance"
    yf_cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        from yfinance import cache as yf_cache
        yf_cache.set_cache_location(str(yf_cache_dir))
    except Exception as e:
        print(f"  [WARN] yfinance cache path 設定失敗: {e}")


def configure_default_mode():
    """重置為預設正式環境路徑。"""
    global PORTFOLIO_FILE, CONFIG_FILE, COMPANY_NAMES_FILE
    global COMPETITORS_FILE, CANDIDATES_FILE, CACHE_DIR, RESULTS_FILE, HTML_FILE

    def _can_reset(v):
        return isinstance(v, Path) and type(v).__module__ != "unittest.mock"

    # Keep test-time patched objects (e.g. MagicMock(spec=Path)) intact.
    if _can_reset(PORTFOLIO_FILE):
        PORTFOLIO_FILE = BASE_DIR / "holdings.csv"
    if _can_reset(CONFIG_FILE):
        CONFIG_FILE = BASE_DIR / "config" / "config.json"
    if _can_reset(COMPANY_NAMES_FILE):
        COMPANY_NAMES_FILE = BASE_DIR / "config" / "company_names.json"
    if _can_reset(COMPETITORS_FILE):
        COMPETITORS_FILE = BASE_DIR / "config" / "competitors.json"
    if _can_reset(CANDIDATES_FILE):
        CANDIDATES_FILE = BASE_DIR / "candidates.txt"
    if _can_reset(CACHE_DIR):
        CACHE_DIR = BASE_DIR / "cache"
    if _can_reset(RESULTS_FILE):
        RESULTS_FILE = OUTPUT_DIR / "results.json"
    if _can_reset(HTML_FILE):
        HTML_FILE = BASE_DIR / "index.html"


def configure_test_mode():
    """切換到測試模式路徑（--test）。"""
    global PORTFOLIO_FILE, CONFIG_FILE, COMPANY_NAMES_FILE
    global COMPETITORS_FILE, CANDIDATES_FILE, CACHE_DIR, RESULTS_FILE, HTML_FILE

    test_e2e_dir = BASE_DIR / "tests" / "test_e2e"
    test_e2e_dir.mkdir(parents=True, exist_ok=True)
    test_cache_dir = test_e2e_dir / "test_cache"
    test_cache_dir.mkdir(parents=True, exist_ok=True)

    PORTFOLIO_FILE = test_e2e_dir / "holdings.csv"
    CONFIG_FILE = test_cache_dir / "config.json"
    COMPANY_NAMES_FILE = test_cache_dir / "company_names.json"
    COMPETITORS_FILE = test_e2e_dir / "competitors.json"
    CANDIDATES_FILE = test_e2e_dir / "candidates.txt"
    CACHE_DIR = test_cache_dir
    RESULTS_FILE = test_cache_dir / "results.json"
    HTML_FILE = test_e2e_dir / "test_index.html"


# ═══════════════════════════════════════════════════════════════
#  Section 1: Setup & Config
# ═══════════════════════════════════════════════════════════════

# Logic moved to pre_run.StockPrerun


# ══════════════════════════════════════════════════════════════
#  Section 2: Portfolio
# ═══════════════════════════════════════════════════════════════

# Logic moved to pre_run.StockPrerun


# Logic moved to pre_run.StockPrerun


# ═══════════════════════════════════════════════════════════════
#  Section 3: Data Fetching
# ═══════════════════════════════════════════════════════════════


def fetch_stock_data(symbol, cache_mgr=None):
    """從 Yahoo Finance 抓取基本面 + 技術面數據，支援快取。"""
    # 嘗試從快取讀取
    cached_fund = cache_mgr.get('fundamental', symbol) if cache_mgr else None
    cached_tech = cache_mgr.get('technical', symbol) if cache_mgr else None

    # Fundamental already checked in cache_mgr.get() above.
    # We no longer need secondary check here as expiration is strictly earnings-based.

    if cached_fund and cached_tech:
        print(f"    [Cache HIT] {symbol} 基本面+技術面")
        # 即使快取命中，也抓最新價格
        try:
            stock = yf.Ticker(symbol)
            info = stock.info or {}
            live_price = extract_current_price(info)
            if live_price:
                cached_fund['current_price'] = live_price
        except Exception:
            pass  # 價格抓取失敗，沿用快取中的價格
        return {
            'symbol': symbol,
            'fundamental': cached_fund,
            'technical': cached_tech,
            'fetch_time': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        }

    print(f"    [Data] {symbol} ...")
    try:
        stock = yf.Ticker(symbol)
        info = stock.info or {}

        tech, tech_from_cache = fetch_technical(
            symbol=symbol,
            stock=stock,
            cached_tech=cached_tech,
            cache_mgr=cache_mgr,
        )
        if tech_from_cache:
            print(f"    [Cache HIT] {symbol} 技術面")
        elif cache_mgr:
            print(f"    [Cache SAVE] {symbol} 技術面")

        if cached_fund is None and info.get('longBusinessSummary'):
            print(f"    [Gemini] 正在翻譯 {symbol} 的公司概況...")

        fundamental, _, fund_from_cache = fetch_fundamental(
            symbol=symbol,
            cache_mgr=cache_mgr
        )
        if fund_from_cache:
            print(f"    [Cache HIT] {symbol} 基本面")
        elif cache_mgr:
            print(f"    [Cache SAVE] {symbol} 基本面")

        return {
            'symbol': symbol,
            'fundamental': fundamental,
            'technical': tech,
            'fetch_time': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        }
    except Exception as e:
        print(f"    [WARN] {symbol} 資料擷取失敗: {e}")
        return {
            'symbol': symbol,
            'error': str(e),
            'fundamental': {},
            'technical': {},
            'fetch_time': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        }


def fetch_holdings_data(
    stocks,
    cache_mgr,
    company_names,
    config=None,
    *,
    has_api_key=False,
    system_prompt='',
    sleep_seconds=1.0,
    progress_prefix='',
):
    """Fetch stock/news data and optional AI analysis for a stock list."""
    results = []
    total = len(stocks)
    news_count = (config or {}).get('news_count', 1000)

    for i, stock_info in enumerate(stocks, 1):
        symbol = stock_info['symbol']
        print(f"  [{i}/{total}] {progress_prefix}{symbol}")

        stock_data = fetch_stock_data(symbol, cache_mgr=cache_mgr)

        fund = stock_data.get('fundamental', {})
        if symbol in company_names:
            fund['company_name'] = company_names[symbol]
        elif fund.get('company_name') and fund['company_name'] != symbol:
            company_names[symbol] = fund['company_name']

        company_name = fund.get('company_name', '')
        news = fetch_news(
            symbol,
            news_count,
            cache_mgr=cache_mgr,
            company_name=company_name,
        )

        analysis_result = {'recommendation': 'unknown', 'scores': {}, 'analysis': ''}
        if has_api_key and 'error' not in stock_data:
            analysis_result = analyze_with_claude(
                stock_info, stock_data, news, system_prompt, config or {}
            )
        elif has_api_key:
            print("    [SKIP] 資料擷取失敗，跳過 AI 分析")

        if not analysis_result.get('scores') and fund and stock_data.get('technical'):
            f_score, t_score, r_score = 3, 3, 3
            roe = fund.get('returnOnEquity', 0)
            if roe:
                if roe > 0.15:
                    f_score += 1
                if roe < 0:
                    f_score -= 1
            tech = stock_data.get('technical', {})
            ma50 = tech.get('ma50')
            ma200 = tech.get('ma200')
            price = fund.get('current_price')
            if price and ma50:
                if price > ma50:
                    t_score += 1
                else:
                    t_score -= 1
            if ma50 and ma200 and ma50 > ma200:
                t_score += 1

            f_score = max(1, min(5, f_score))
            t_score = max(1, min(5, t_score))
            analysis_result['scores'] = {'fundamental': f_score, 'technical': t_score, 'risk': r_score}

        results.append({
            'stock_info': stock_info,
            'stock_data': stock_data,
            'news': news,
            'analysis_result': analysis_result,
        })

        if i < total and sleep_seconds and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return results


def fetch_competitor_data(stocks, cache_mgr, company_names, config=None):
    """獲取競品的基本面數據與消息面（不在持股列表中的競品）。

    Args:
        stocks: 持股列表
        cache_mgr: 競品專用快取管理器
        company_names: 公司名稱映射
        config: 配置檔（控制 news_count 等）

    Returns:
        競品的 results 列表
    """
    # 讀取競品配置
    comp_path = COMPETITORS_FILE
    if not comp_path.exists():
        return []

    try:
        _comp_raw = json.loads(comp_path.read_text(encoding='utf-8'))
        if 'holdings' in _comp_raw or 'competitors' in _comp_raw or 'candidates' in _comp_raw:
            competitors_map = {}
            competitors_map.update(_comp_raw.get('holdings', {}))
            competitors_map.update(_comp_raw.get('candidates', {}))
            competitors_map.update(_comp_raw.get('competitors', {}))
        else:
            competitors_map = _comp_raw
    except Exception:
        print(f"  [WARN] 競品配置讀取失敗，請檢查 {comp_path}")
        return []

    # 收集所有持股的 symbols
    portfolio_symbols = {s['symbol'] for s in stocks}
    is_us_ticker = lambda sym: isinstance(sym, str) and re.fullmatch(r"[A-Z]{1,5}", sym) and "." not in sym

    candidate_symbols = set()
    candidate_paths = [CANDIDATES_FILE]
    legacy_candidates_path = BASE_DIR / "config" / "candidates.txt"
    if legacy_candidates_path not in candidate_paths:
        candidate_paths.append(legacy_candidates_path)
    for cp in candidate_paths:
        if not cp.exists():
            continue
        try:
            for raw in cp.read_text(encoding='utf-8').splitlines():
                line = raw.split('#', 1)[0].strip().upper()
                if line and is_us_ticker(line) and line not in portfolio_symbols:
                    candidate_symbols.add(line)
        except Exception:
            print(f"  [WARN] candidates 讀取失敗，略過: {cp}")

    # 收集所有競品 symbols（持股/候選的直接競品 + candidates）
    competitor_symbols = set()
    root_symbols = portfolio_symbols | candidate_symbols
    for symbol, comps in competitors_map.items():
        if symbol in root_symbols:
            for comp in comps:
                if comp and is_us_ticker(comp) and comp not in portfolio_symbols:
                    competitor_symbols.add(comp)
    competitor_symbols.update(candidate_symbols)

    if not competitor_symbols:
        return []

    news_count = (config or {}).get('news_count', 1000)

    competitor_stocks = [
        {
            'symbol': comp_symbol,
            'shares': 0,
            'cost_basis': 0,
            'category': '競品參考',
        }
        for comp_symbol in sorted(competitor_symbols)
    ]
    return fetch_holdings_data(
        competitor_stocks,
        cache_mgr,
        company_names,
        {'news_count': news_count},
        has_api_key=False,
        sleep_seconds=0.5,
        progress_prefix='[競品] ',
    )

# ═══════════════════════════════════════════════════════════════
#  Section 4: Claude Analysis
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
#  Section 5: Portfolio Allocation
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
#  Section 7: Main
# ═══════════════════════════════════════════════════════════════

def main():
    # 避免同一個 interpreter 曾切到 --test 後污染全域路徑
    configure_default_mode()

    if '--test' in sys.argv:
        configure_test_mode()
        print("  [測試模式] 使用 tests/test_e2e/holdings.csv，快取寫入 tests/test_e2e/test_cache/")

    configure_yfinance_cache()

    # Handle --open flag
    if '--open' in sys.argv:
        if HTML_FILE.exists():
            webbrowser.open(str(HTML_FILE.absolute()))
            print(f"已開啟: {HTML_FILE}")
        else:
            print("尚未生成報告，請先執行: python stock_assistant.py")
        return

    # Handle --html-only flag
    if '--html-only' in sys.argv:
        rebuild_dashboard(
            portfolio_file=PORTFOLIO_FILE,
            config_file=CONFIG_FILE,
            system_prompt_file=SYSTEM_PROMPT_FILE,
            company_names_file=COMPANY_NAMES_FILE,
            competitors_file=COMPETITORS_FILE,
            results_file=RESULTS_FILE,
            html_file=HTML_FILE,
            cache_dir=CACHE_DIR,
            stock_prerun_cls=StockPrerun,
            calculate_allocation_fn=calculate_allocation,
            generate_html_fn=generate_html,
            print_fn=print,
        )
        return

    print()
    print("=" * 56)
    print("  Stock Analysis Dashboard")
    print("  Powered by Claude AI")
    print("=" * 56)

    # Setup
    # Initialize prerun first, then wire cache managers after config is loaded.
    prerun = StockPrerun(
        PORTFOLIO_FILE,
        CONFIG_FILE,
        SYSTEM_PROMPT_FILE,
        COMPANY_NAMES_FILE,
        competitors_file=COMPETITORS_FILE,
    )

    has_api_key = prerun.check_setup()
    config = prerun.load_config()
    cache_mgr = CacheManager(config=config, scope='holdings', base_cache_dir=CACHE_DIR)
    comp_cache_mgr = CacheManager(config=config, scope='competitors', base_cache_dir=CACHE_DIR)
    prerun.cache_mgr = cache_mgr
    prerun.comp_cache_mgr = comp_cache_mgr
    system_prompt = prerun.load_system_prompt() if has_api_key else ''

    # Handle cache
    prerun.process_cache()

    # Load portfolio & company names
    stocks, options, cash = prerun.load_portfolio()
    portfolio_symbols = {s['symbol'] for s in stocks}
    company_names = prerun.load_company_names()
    skip_comp_bootstrap = ('--skip-competitor-bootstrap' in sys.argv) or ('-sc' in sys.argv)
    if skip_comp_bootstrap:
        print("  [競品] 跳過 bootstrap（--skip-competitor-bootstrap）")
    else:
        prerun.auto_populate_competitors(portfolio_symbols)
        prerun.ensure_competitor_names(company_names, portfolio_symbols)
    print(f"\n  持股: {len(stocks)} 檔 | 選擇權: {len(options)} 筆 | 現金: ${cash:,.2f}")
    print(f"  競品檔案: {COMPETITORS_FILE}")

    # Filter tickers if specified via CLI or config
    cli_tickers = [t.upper() for t in sys.argv[1:] if not t.startswith('-')]
    only = config.get('only_tickers', [])
    skip = config.get('skip_tickers', [])

    if cli_tickers:
        stocks = [s for s in stocks if s['symbol'] in cli_tickers]
        print(f"  (指定分析: {', '.join(cli_tickers)})")
    elif only:
        stocks = [s for s in stocks if s['symbol'] in only]
        print(f"  (config 限定: {', '.join(only)})")

    if skip:
        stocks = [s for s in stocks if s['symbol'] not in skip]
        print(f"  (config 排除: {', '.join(skip)})")

    if not stocks:
        print("\n  沒有要分析的股票！請檢查設定。")
        return

    print(f"\n  即將分析: {', '.join(s['symbol'] for s in stocks)}")
    if has_api_key:
        print(f"  模型: {config.get('model', 'claude-sonnet-4-6')}")
    else:
        print(f"  模式: 純數據（無 AI 分析）")

    results = fetch_holdings_data(
        stocks,
        cache_mgr,
        company_names,
        config,
        has_api_key=has_api_key,
        system_prompt=system_prompt,
        sleep_seconds=1.0,  # 最小間隔避免 yfinance 被擋
    )

    # Save company names mapping (auto-populate new symbols)
    prerun.save_company_names(company_names, portfolio_symbols)

    # Fetch competitor data
    print("\n  📊 獲取競品數據...")
    competitor_results = fetch_competitor_data(stocks, comp_cache_mgr, company_names, config)
    if competitor_results:
        print(f"  ✅ 已獲取 {len(competitor_results)} 檔競品數據")
        results.extend(competitor_results)
        # 儲存可能新增的競品公司名稱
        prerun.save_company_names(company_names, portfolio_symbols)
    else:
        print("  ℹ️  無競品數據需要獲取")

    # Calculate allocation
    enrich_option_market_data(options, print_fn=print)
    allocation = calculate_allocation(results, cash, options)

    # Save results JSON
    generated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_data = {
        'generated_at': generated_at,
        'allocation': {
            'total_value': allocation['total_value'],
            'total_pnl': allocation['total_pnl'],
            'cash': allocation['cash'],
        },
        'results': [
            {
                'symbol': r['stock_info']['symbol'],
                'recommendation': r['analysis_result'].get('recommendation'),
                'confidence': r['analysis_result'].get('confidence'),
                'scores': r['analysis_result'].get('scores', {}),
                'current_price': r['stock_data'].get('fundamental', {}).get('current_price'),
                'analysis': r['analysis_result'].get('analysis', ''),
                'news_count': len(r.get('news', [])),
            }
            for r in results
        ],
    }
    RESULTS_FILE.write_text(
        json.dumps(save_data, indent=2, ensure_ascii=False, default=str),
        encoding='utf-8',
    )
    print(f"\n  結果已儲存: {RESULTS_FILE}")

    # Generate HTML dashboard
    html_content = generate_html(results, allocation, options, generated_at)
    HTML_FILE.write_text(html_content, encoding='utf-8')
    print(f"  儀表板已生成: {HTML_FILE}")

    # Cache stats
    print("\n  [Cache 持倉]")
    cache_mgr.print_stats()
    print("  [Cache 競品]")
    comp_cache_mgr.print_stats()

    # Summary
    print(f"\n{'=' * 56}")
    print(f"  分析完成！")
    print(f"  投資組合總值: ${allocation['total_value']:,.0f}")
    print(f"  未實現損益:   ${allocation['total_pnl']:+,.0f}")
    rec_counts = count_recommendations(results)
    print(f"  加倉建議: {rec_counts.get('add', 0)} 檔")
    print(f"  減倉建議: {rec_counts.get('reduce', 0)} 檔")
    print(f"  平倉建議: {rec_counts.get('close', 0)} 檔")
    print(f"{'=' * 56}")
    print(f"\n  開啟儀表板:")
    print(f"    python stock_assistant.py --open")
    print(f"    或直接用瀏覽器開啟: {HTML_FILE.absolute()}")
    print()


if __name__ == '__main__':
    main()


