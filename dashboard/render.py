"""Dashboard rendering helpers."""
import json
import re
from pathlib import Path

import markdown as md_lib

from cache_manager import find_latest_news_analysis_file

from .constants import CHART_COLORS, REC_INFO
from .template import DASHBOARD_TEMPLATE


def _build_scoring_display(weights: dict) -> dict:
    """
    將 monitor_config.json 的 scoring_weights 轉換為前端 display 結構。
    每個指標 → { title, max, rows: [{cond, val}] }
    """
    def _card(title, max_label, rows):
        return {"title": title, "max": max_label, "rows": [{"cond": c, "val": v} for c, v in rows]}

    fw = weights.get('fundamental', {})
    tw = weights.get('technical', {})
    rw = weights.get('risk', {})

    rg = fw.get('rev_growth', {})
    gm = fw.get('gross_margin', {})
    fcf = fw.get('fcf_margin', {})
    roic = fw.get('roic', {})
    peg = fw.get('forward_peg', {})
    rec = fw.get('analyst_rec', {})
    de = fw.get('debt_equity', {})

    fundamental = [
        _card("營收成長率", f"滿分 {rg.get('over_30', 25)}", [
            (">30%",  rg.get('over_30',  25)),
            (">15%",  rg.get('over_15',  18)),
            (">5%",   rg.get('over_5',   10)),
            (">0%",   rg.get('over_0',    4)),
            ("負成長", rg.get('below_0', -10)),
        ]),
        _card("毛利率", f"滿分 {gm.get('over_60', 20)}", [
            (">60%",  gm.get('over_60', 20)),
            (">40%",  gm.get('over_40', 14)),
            (">20%",  gm.get('over_20',  7)),
            ("≤20%",  gm.get('default',  0)),
        ]),
        _card("FCF Margin", f"滿分 {fcf.get('over_20', 15)}", [
            (">20%",  fcf.get('over_20',  15)),
            (">10%",  fcf.get('over_10',  10)),
            (">0%",   fcf.get('over_0',    5)),
            ("負數",   fcf.get('below_0', -8)),
        ]),
        _card("ROIC（ROE proxy）", f"滿分 {roic.get('over_25', 15)}", [
            (">25%",  roic.get('over_25', 15)),
            (">15%",  roic.get('over_15', 10)),
            (">8%",   roic.get('over_8',   5)),
            ("≤8%",   roic.get('default',  0)),
        ]),
        _card("Forward PEG", f"±{abs(peg.get('below_10', 10))}", [
            ("<1.0",  peg.get('below_10',  10)),
            ("<1.5",  peg.get('below_15',   5)),
            ("<2.5",  peg.get('below_25',   0)),
            (">3.0",  peg.get('over_30',  -10)),
        ]),
        _card("分析師評級", f"滿分 {rec.get('below_18', 10)}", [
            ("<1.8",  rec.get('below_18', 10)),
            ("<2.3",  rec.get('below_23',  7)),
            ("<3.0",  rec.get('below_30',  3)),
            (">4.0",  rec.get('over_40',  -5)),
        ]),
        _card("負債 / 權益比", f"±{abs(de.get('below_05', 5))}", [
            ("<0.5",  de.get('below_05',  5)),
            ("<1.5",  de.get('below_15',  2)),
            (">1.5",  0),
            (">3.0",  de.get('over_30',  -5)),
        ]),
    ]

    tr = tw.get('trend', {})
    ri = tw.get('rsi', {})
    mc = tw.get('macd', {})
    bb = tw.get('bb', {})
    vr = tw.get('vol_ratio', {})
    at = tw.get('atr', {})

    technical = [
        _card("趨勢狀態", f"滿分 {tr.get('UPTREND', 35)}", [
            ("多頭排列 (UPTREND)",          tr.get('UPTREND',          35)),
            ("多頭超賣 (OVERSOLD_UPTREND)", tr.get('OVERSOLD_UPTREND', 30)),
            ("跌深反彈 (RECOVERY)",         tr.get('RECOVERY',         20)),
            ("盤整整固 (CONSOLIDATION)",    tr.get('CONSOLIDATION',    15)),
            ("跌破支撐 (BREAKDOWN)",        tr.get('BREAKDOWN',         5)),
            ("空頭排列 (DOWNTREND)",        tr.get('DOWNTREND',         0)),
        ]),
        _card("RSI-14", f"滿分 {ri.get('peak_momentum', 20)}", [
            ("50 – 70（最佳動能）",   ri.get('peak_momentum',   20)),
            ("70 – 80（強勢動能）",   ri.get('strong_momentum', 15)),
            ("40 – 50（正常偏弱）",   ri.get('normal',          12)),
            ("≤40（超賣區）",         ri.get('oversold',         8)),
            (">80（過熱）",           ri.get('overheated',       5)),
        ]),
        _card("MACD", f"滿分 {mc.get('bull_above_zero', 15)}", [
            ("多頭 > 零軸", mc.get('bull_above_zero', 15)),
            ("多頭 < 零軸", mc.get('bull_below_zero', 10)),
            ("空頭 > 零軸", mc.get('bear_above_zero',  4)),
            ("空頭 < 零軸", mc.get('bear_below_zero',  0)),
        ]),
        _card("布林帶 %B", f"滿分 {bb.get('mid', 15)}", [
            ("0.4 – 0.7（中軌強勢）",  bb.get('mid',      15)),
            ("0.7 – 0.9（趨近上軌）",  bb.get('upper',    10)),
            ("0.2 – 0.4（中軌偏低）",  bb.get('lower',     8)),
            (">0.9（突破上軌）",       bb.get('breakout',  5)),
            ("<0.2（接近下軌）",       bb.get('near_low',  2)),
        ]),
        _card("成交量比（當日/20日均）", f"滿分 {vr.get('up_high', 10)}", [
            ("上漲 + 量增 (>1.2x)",  vr.get('up_high',  10)),
            ("上漲 + 量平 (0.8–1.2x)", vr.get('up_flat', 6)),
            ("下跌 + 量縮 (<0.8x)",  vr.get('down_low',  4)),
            ("下跌 + 量增 (>1.2x)",  vr.get('down_high', 0)),
        ]),
        _card("ATR 波動率", f"滿分 {at.get('low_vol', 5)}", [
            ("低波 (<3%)",   at.get('low_vol',     5)),
            ("正常 (<5%)",   at.get('normal_vol',  3)),
            ("高波 (<7%)",   at.get('high_vol',    1)),
            ("極端 (≥7%)",   at.get('extreme_vol', 0)),
        ]),
    ]

    va = rw.get('var_95', {})
    so = rw.get('sortino', {})
    md = rw.get('max_drawdown', {})
    bt = rw.get('beta', {})
    ca = rw.get('calmar', {})

    risk = [
        _card("VaR-95（1日）", f"滿分 {va.get('above_minus_3pct', 25)}", [
            ("損失 <3%",  va.get('above_minus_3pct', 25)),
            ("損失 <5%",  va.get('above_minus_5pct', 18)),
            ("損失 <7%",  va.get('above_minus_7pct', 10)),
            ("損失 ≥7%",  va.get('below_minus_7pct',  0)),
        ]),
        _card("Sortino Ratio", f"滿分 {so.get('above_15', 25)}", [
            (">1.5",  so.get('above_15', 25)),
            (">1.0",  so.get('above_1',  15)),
            (">0",    so.get('above_0',   5)),
            ("≤0",    so.get('below_0',   0)),
        ]),
        _card("Max Drawdown", f"滿分 {md.get('below_15pct', 25)}", [
            ("<15%",  md.get('below_15pct', 25)),
            ("<25%",  md.get('below_25pct', 18)),
            ("<40%",  md.get('below_40pct', 10)),
            ("<55%",  md.get('below_55pct',  5)),
            ("≥55%",  md.get('above_55pct',  0)),
        ]),
        _card("Beta（yfinance）", f"滿分 {bt.get('below_12', 15)}", [
            ("<1.2",  bt.get('below_12', 15)),
            ("<1.5",  bt.get('below_15', 10)),
            ("<2.0",  bt.get('below_20',  5)),
            ("≥2.0",  bt.get('above_20',  0)),
        ]),
        _card("Calmar Ratio", f"滿分 {ca.get('above_20', 10)}", [
            (">2.0",  ca.get('above_20', 10)),
            (">1.0",  ca.get('above_10',  7)),
            (">0.5",  ca.get('above_05',  3)),
            ("≤0.5",  ca.get('below_05',  0)),
        ]),
    ]

    return {"fundamental": fundamental, "technical": technical, "risk": risk}


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

    try:
        from monitor.config import get_scoring_weights, reload_monitor_config
        reload_monitor_config()
        _sw = get_scoring_weights()
    except Exception:
        _sw = {}
    scoring_config = _build_scoring_display(_sw)

    embedded_json = json.dumps(
        {
            'stocks': stocks_data,
            'allocation': alloc_data,
            'options': options_data,
            'generated_at': generated_at,
            'candidates': candidate_symbols,
            'alerts': alerts_data or {},
            'scoring_config': scoring_config,
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
