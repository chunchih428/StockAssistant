"""Dashboard rebuild workflow."""
import datetime
import json

from cache_manager import load_latest_cache_json

from .render import generate_html


def _is_results_fresh_today(saved):
    generated_at = saved.get("generated_at")
    if not generated_at:
        return False
    text = str(generated_at).strip()
    if not text:
        return False
    date_part = text.split(" ", 1)[0]
    return date_part == datetime.date.today().isoformat()


def rebuild_dashboard(
    *,
    portfolio_file,
    config_file,
    system_prompt_file,
    company_names_file,
    competitors_file,
    results_file,
    html_file,
    cache_dir,
    stock_prerun_cls=None,
    calculate_allocation_fn=None,
    generate_html_fn=None,
    print_fn=print,
):
    """只重新生成 index.html，不重新抓取或檢查任何 cache。"""
    if stock_prerun_cls is None:
        from pre_run import StockPrerun as stock_prerun_cls
    if calculate_allocation_fn is None:
        from portfolio import calculate_allocation as calculate_allocation_fn
    try:
        from portfolio import enrich_option_market_data
    except Exception:
        enrich_option_market_data = lambda _options, **_kwargs: _options
    if generate_html_fn is None:
        generate_html_fn = generate_html

    print_fn("\n" + "=" * 56)
    print_fn("  Stock Analysis Dashboard — Index Only")
    print_fn("=" * 56)
    print_fn("\n  [html-only] 從現有 cache 重建 index.html ...")

    prerun = stock_prerun_cls(
        portfolio_file,
        config_file,
        system_prompt_file,
        company_names_file,
        competitors_file=competitors_file,
    )
    prerun.load_config()
    stocks, options, cash = prerun.load_portfolio()
    portfolio_symbols = {s['symbol'] for s in stocks}
    company_names = prerun.load_company_names()

    analysis_map = {}
    price_map = {}
    if results_file.exists():
        try:
            saved = json.loads(results_file.read_text(encoding='utf-8'))
            if _is_results_fresh_today(saved):
                for r in saved.get('results', []):
                    analysis_map[r['symbol']] = {
                        'recommendation': r.get('recommendation', 'unknown'),
                        'confidence': r.get('confidence'),
                        'scores': r.get('scores', {}),
                        'analysis': r.get('analysis', ''),
                    }
                    if r.get('current_price') is not None:
                        price_map[r['symbol']] = r['current_price']
            else:
                print_fn("  [html-only] results.json 非今日資料，僅使用 cache 重建")
        except Exception as e:
            print_fn(f"  ⚠️  讀取 results.json 失敗: {e}")

    results = []
    for stock_info in stocks:
        symbol = stock_info['symbol']
        fund = load_latest_cache_json(cache_dir, 'holdings', 'fundamental', symbol)
        tech = load_latest_cache_json(cache_dir, 'holdings', 'technical', symbol)
        stock_data = {'fundamental': fund, 'technical': tech}

        if tech.get('current_price') is not None:
            fund['current_price'] = tech.get('current_price')
        if symbol in price_map and fund.get('current_price') is None:
            fund['current_price'] = price_map[symbol]
        if symbol in company_names:
            fund['company_name'] = company_names[symbol]

        news_cache = load_latest_cache_json(cache_dir, 'holdings', 'news', symbol)
        news = news_cache.get('articles', [])

        analysis_result = analysis_map.get(symbol, {
            'recommendation': 'unknown', 'scores': {}, 'analysis': ''
        })

        if not analysis_result.get('scores') and fund and tech:
            f_score, t_score, r_score = 3, 3, 3
            roe = fund.get('returnOnEquity', 0)
            if roe:
                if roe > 0.15:
                    f_score += 1
                if roe < 0:
                    f_score -= 1
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
        print_fn(f"    ✅ {symbol}")

    if competitors_file.exists():
        try:
            _comp_raw = json.loads(competitors_file.read_text(encoding='utf-8'))
            if 'holdings' in _comp_raw or 'competitors' in _comp_raw or 'candidates' in _comp_raw:
                competitors_map = {}
                competitors_map.update(_comp_raw.get('holdings', {}))
                competitors_map.update(_comp_raw.get('candidates', {}))
                competitors_map.update(_comp_raw.get('competitors', {}))
            else:
                competitors_map = _comp_raw

            competitor_symbols = set()
            for sym, comps in competitors_map.items():
                if sym in portfolio_symbols:
                    for comp in comps:
                        if comp and comp not in portfolio_symbols:
                            competitor_symbols.add(comp)

            for comp_symbol in sorted(competitor_symbols):
                fund = load_latest_cache_json(cache_dir, 'competitors', 'fundamental', comp_symbol)
                tech = load_latest_cache_json(cache_dir, 'competitors', 'technical', comp_symbol)
                stock_data = {'fundamental': fund, 'technical': tech}
                if tech.get('current_price') is not None:
                    fund['current_price'] = tech.get('current_price')
                if comp_symbol in price_map and fund.get('current_price') is None:
                    fund['current_price'] = price_map[comp_symbol]
                if comp_symbol in company_names:
                    fund['company_name'] = company_names[comp_symbol]
                news_cache = load_latest_cache_json(cache_dir, 'competitors', 'news', comp_symbol)
                news = news_cache.get('articles', [])
                analysis_result = analysis_map.get(comp_symbol, {
                    'recommendation': 'unknown', 'scores': {}, 'analysis': ''
                })

                if not analysis_result.get('scores') and fund and tech:
                    f_score, t_score, r_score = 3, 3, 3
                    roe = fund.get('returnOnEquity', 0)
                    if roe:
                        if roe > 0.15:
                            f_score += 1
                        if roe < 0:
                            f_score -= 1
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
                    'stock_info': {
                        'symbol': comp_symbol,
                        'shares': 0,
                        'cost_basis': 0,
                        'category': '競品參考',
                    },
                    'stock_data': stock_data,
                    'news': news,
                    'analysis_result': analysis_result,
                })
                print_fn(f"    ✅ {comp_symbol} (競品)")
        except Exception as e:
            print_fn(f"  ⚠️  載入競品失敗: {e}")

    enrich_option_market_data(options, print_fn=print_fn)
    allocation = calculate_allocation_fn(results, cash, options)
    generated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html_content = generate_html_fn(results, allocation, options, generated_at)
    html_file.write_text(html_content, encoding='utf-8')

    print_fn(f"\n{'=' * 56}")
    print_fn(f"  ✅ index.html 已重新生成: {html_file}")
    print_fn(f"  投資組合總值: ${allocation['total_value']:,.0f}")
    print_fn(f"{'=' * 56}")
    print_fn("\n  開啟儀表板:")
    print_fn("    python stock_assistant.py --open")
    print_fn(f"    或直接用瀏覽器開啟: {html_file.absolute()}")
    print_fn("")
