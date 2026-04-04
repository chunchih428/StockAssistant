"""Dashboard rendering helpers."""
import json
import re
from pathlib import Path

import markdown as md_lib

from cache_manager import find_latest_news_analysis_file

from .constants import CHART_COLORS, REC_INFO
from .template import DASHBOARD_TEMPLATE


def render_md(text):
    """Markdown -> HTML。"""
    text = re.sub(r'([^\n])\n(#{1,6} )', r'\1\n\n\2', text)
    text = re.sub(r'([^\n])\n(\|)', r'\1\n\n\2', text)
    return md_lib.markdown(text, extensions=['tables', 'fenced_code', 'sane_lists'])


def generate_html(results, allocation, options, generated_at, alerts_data=None):
    """生成互動式 HTML 儀表板（Vue 3 + Tailwind CSS）。

    Parameters
    ----------
    alerts_data : dict | None
        由 monitor.engine.run_monitor() 產生的監測警示資料。
        None 時儀表板不顯示警示面板（向下相容舊行為）。
    """
    return _build_interactive_dashboard(results, allocation, options, generated_at, alerts_data)


def _build_interactive_dashboard(results, allocation, options, generated_at, alerts_data=None):
    """建構互動式儀表板 HTML。"""
    competitors_map = {}
    candidate_symbols = []
    comp_path = Path(__file__).resolve().parent.parent / 'config' / 'competitors.json'
    candidates_paths = [
        Path(__file__).resolve().parent.parent / 'config' / 'candidates.txt',
        Path(__file__).resolve().parent.parent / 'candidates.txt',
    ]
    if comp_path.exists():
        try:
            _comp_raw = json.loads(comp_path.read_text(encoding='utf-8'))
            if 'holdings' in _comp_raw or 'competitors' in _comp_raw or 'candidates' in _comp_raw:
                competitors_map.update(_comp_raw.get('holdings', {}))
                competitors_map.update(_comp_raw.get('candidates', {}))
                competitors_map.update(_comp_raw.get('competitors', {}))
            else:
                competitors_map = _comp_raw
        except Exception:
            pass
    for candidates_path in candidates_paths:
        if not candidates_path.exists():
            continue
        try:
            raw_lines = candidates_path.read_text(encoding='utf-8').splitlines()
            for line in raw_lines:
                sym = line.strip().upper()
                if not sym or sym.startswith('#'):
                    continue
                if sym not in candidate_symbols:
                    candidate_symbols.append(sym)
        except Exception:
            pass

    stocks_data = []
    for r in results:
        si = r['stock_info']
        sd = r.get('stock_data', {})
        ar = r.get('analysis_result', {}) or {}
        news_list = r.get('news', [])
        fund = sd.get('fundamental', {})
        tech = sd.get('technical', {})
        error = sd.get('error')
        price = fund.get('current_price')
        cost = si.get('cost_basis', 0)
        shares = si.get('shares', 0)
        pnl = (price - cost) * shares if price and cost else 0
        pnl_pct = ((price - cost) / cost * 100) if price and cost else 0
        analysis_html = render_md(ar['analysis']) if ar.get('analysis') else ''

        news_analysis = None
        _cat = si.get('category', '')
        if _cat == '競品參考':
            _scope = 'competitors'
        elif _cat == '候選':
            _scope = 'candidates'
        else:
            _scope = 'holdings'
        na_path = find_latest_news_analysis_file(Path('cache'), _scope, si['symbol'])

        if na_path and na_path.exists():
            try:
                na_raw = json.loads(na_path.read_text(encoding='utf-8'))
                summary = na_raw.get('summary', {})
                news_analysis = {
                    'summary': {
                        'overall_sentiment': summary.get('overall_sentiment', ''),
                        'key_theme': summary.get('key_theme', ''),
                        'bullish_count': summary.get('bullish_count', 0),
                        'bearish_count': summary.get('bearish_count', 0),
                        'neutral_count': summary.get('neutral_count', 0),
                        'total': summary.get('total_articles', 0),
                    },
                    'bullish': na_raw.get('bullish', []),
                    'bearish': na_raw.get('bearish', []),
                    'neutral': na_raw.get('neutral', []),
                }
            except Exception:
                news_analysis = None

        stocks_data.append({
            'symbol': si['symbol'],
            'company': fund.get('company_name', si['symbol']),
            'category': si.get('category', ''),
            'price': price,
            'cost_basis': cost,
            'shares': shares,
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'error': error,
            'recommendation': ar.get('recommendation', 'unknown'),
            'confidence': ar.get('confidence', ''),
            'scores': ar.get('scores', {}),
            'analysis_html': analysis_html,
            'fundamental': {k: fund.get(k) for k in [
                'trailingPE', 'forwardPE', 'priceToSalesTrailing12Months', 'pegRatio',
                'priceToBook', 'beta', 'dividendYield', 'marketCap', 'enterpriseValue',
                'trailingEps', 'forwardEps', 'revenueGrowth', 'earningsGrowth',
                'grossMargins', 'operatingMargins', 'profitMargins', 'totalRevenue',
                'freeCashflow', 'fcf_margin', 'operatingCashflow', 'totalDebt', 'totalCash',
                'net_debt', 'debtToEquity', 'currentRatio', 'returnOnEquity', 'returnOnAssets',
                'sector', 'industry', 'next_earnings_date', 'longBusinessSummary',
                'fund_score',
            ]},
            'technical': tech,
            'news': [{
                'title': n.get('title', ''),
                'link': n.get('link', '#'),
                'publisher': n.get('publisher', ''),
                'date': n.get('date', ''),
                'score': n.get('_score', 0),
            } for n in news_list],
            'news_analysis': news_analysis,
            'competitors': competitors_map.get(si['symbol'], []),
        })

    options_data = [{
        'symbol': o.get('symbol', ''),
        'underlying': o.get('underlying', ''),
        'type': o.get('type', ''),
        'strike': o.get('strike', 0),
        'expiry': o.get('expiry', ''),
        'shares': o.get('shares', 0),
        'cost_basis': o.get('cost_basis', 0),
        'total_cost': o.get('total_cost', 0),
        'current_price': o.get('current_price'),
        'market_value': o.get('market_value', o.get('total_cost', 0)),
        'pnl': o.get('pnl', 0),
        'pnl_pct': o.get('pnl_pct', 0),
        'category': o.get('category', ''),
    } for o in options]

    alloc_data = {
        'total_value': allocation['total_value'],
        'total_cost': allocation.get('total_cost', 0),
        'total_pnl': allocation['total_pnl'],
        'cash': allocation['cash'],
        'cash_pct': allocation['cash_pct'],
        'positions': [{
            'symbol': p['symbol'],
            'alloc_pct': p['alloc_pct'],
            'market_value': p['market_value'],
            'shares': p['shares'],
            'cost_basis': p['cost_basis'],
            'cost_total': p['cost_total'],
            'current_price': p['current_price'],
            'pnl': p['pnl'],
            'pnl_pct': p['pnl_pct'],
            'category': p['category'],
        } for p in allocation['positions']],
        'options_value': allocation.get('options_value', 0),
        'options_pct': allocation.get('options_pct', 0),
        'portfolio_risk': allocation.get('portfolio_risk', {}),
    }

    embedded_json = json.dumps(
        {
            'stocks': stocks_data,
            'allocation': alloc_data,
            'options': options_data,
            'generated_at': generated_at,
            'candidates': candidate_symbols,
            'alerts': alerts_data or {},
        },
        ensure_ascii=False,
        default=str,
    )
    rec_info_json = json.dumps(REC_INFO, ensure_ascii=False)
    colors_json = json.dumps(CHART_COLORS)

    page = DASHBOARD_TEMPLATE
    page = page.replace('__DATA_JSON__', embedded_json)
    page = page.replace('__REC_INFO_JSON__', rec_info_json)
    page = page.replace('__COLORS_JSON__', colors_json)
    return page


def count_recommendations(results):
    """計算推薦統計。"""
    rec_counts = {'add': 0, 'reduce': 0, 'close': 0, 'hold': 0, 'unknown': 0}
    for r in results:
        rec = r.get('analysis_result', {}).get('recommendation', 'unknown')
        rec_counts[rec] = rec_counts.get(rec, 0) + 1
    return rec_counts
