import yfinance as yf

from .fundamental_ai import translate_summary_with_gemini

# 標的分類（用於選擇評分邏輯）
ETF_LIKE = {
    'QQQ', 'SPY', 'VOO', 'IBIT', 'SQQQ', 'TQQQ', 'QID',
    'AMZU', 'GGLL', 'TSLL', 'METU'
}

# 手動設定的質性評分（0-100），用於無法取得財務資料的標的
MANUAL_SCORES = {
    # 大型科技（基本面強）
    'NVDA':  92, 'META':  88, 'GOOGL': 87, 'GOOG': 87, 'MSFT': 89,
    'AMZN':  86, 'AAPL':  82, 'TSLA':  70,
    # 成長科技
    'CRWD':  82, 'NET':   80, 'PLTR':  72, 'SHOP': 74, 'NFLX': 78,
    'COIN':  62, 'SOFI':  58, 'IBIT':  65,
    # 電力/基礎設施（AI 受惠）
    'CEG':   78, 'ETN':   80, 'PWR':   79, 'VST':  76, 'VRT':  77,
    'CCJ':   72, 'SMR':   60, 'OKLO':  50,
    # 科技中型股
    'NTAP':  72, 'ORCL':  76, 'PANW':  81, 'GTLB': 68, 'LASR': 55,
    'ONDS':  40,  # 小型股，基本面較弱
    # ETF / 指數
    'QQQ':   80, 'VOO':   82, 'SPY':   80, 'TQQQ': 60, 'SQQQ': 40,
    'AMZU':  65, 'GGLL':  62, 'TSLL':  58,
    # 其他
    'MCD':   78, 'UNH':   72, 'LMT':   74, 'COST': 80,
}

# 基本面評分權重定義
DEFAULT_FUND_WEIGHTS = {
    'rev_growth': {
        'over_30': 30,
        'over_15': 22,
        'over_5': 14,
        'over_0': 6,
        'below_0': -10
    },
    'gross_margin': {
        'over_60': 25,
        'over_40': 16,
        'over_20': 8,
        'default': 0
    },
    'fcf_margin': {
        'over_20': 15,
        'over_10': 10,
        'over_0': 5,
        'below_0': -8
    },
    'debt_equity': {
        'below_05': 10,
        'below_15': 4,
        'over_50': -10
    },
    'analyst_rec': {
        'below_18': 20,
        'below_23': 14,
        'below_30': 6,
        'over_40': -10
    }
}

FUNDAMENTAL_KEYS = [
    "marketCap",
    "enterpriseValue",
    "trailingPE",
    "forwardPE",
    "priceToSalesTrailing12Months",
    "pegRatio",
    "priceToBook",
    "beta",
    "dividendYield",
    "trailingEps",
    "forwardEps",
    "revenueGrowth",
    "earningsGrowth",
    "grossMargins",
    "operatingMargins",
    "profitMargins",
    "totalRevenue",
    "freeCashflow",
    "operatingCashflow",
    "totalDebt",
    "totalCash",
    "debtToEquity",
    "currentRatio",
    "returnOnEquity",
    "returnOnAssets",
    "longName",
    "shortName",
    "sector",
    "industry",
    "longBusinessSummary",
    "recommendationMean",
]


def extract_current_price(info):
    return info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")


def compute_fundamental_score(ticker: str, info: dict, config: dict = None) -> dict:
    """根據 yfinance info 字典計算基本面健康分 (0-100)，支援動態權重

    權重優先順序：
        1. config['fundamental_weights']（stock_assistant 傳入）
        2. monitor_config.json 的 scoring_weights.fundamental
        3. DEFAULT_FUND_WEIGHTS（程式碼預設值）
    """
    weights = (config or {}).get('fundamental_weights')
    if weights is None:
        try:
            from monitor.config import get_scoring_weights
            weights = get_scoring_weights().get('fundamental')
        except Exception:
            pass
    if weights is None:
        weights = DEFAULT_FUND_WEIGHTS
    
    if ticker in ETF_LIKE:
        return {'health_score': 60, 'source': 'default_etf'}
        
    score = 0.0
    details = {}

    # 1. 營收成長率
    rev_growth = info.get('revenueGrowth', None)
    if rev_growth is not None:
        details['rev_growth_yoy'] = rev_growth * 100
        w_rev = weights.get('rev_growth', {})
        if rev_growth > 0.30:    score += w_rev.get('over_30', 15)
        elif rev_growth > 0.15:  score += w_rev.get('over_15', 11)
        elif rev_growth > 0.05:  score += w_rev.get('over_5', 7)
        elif rev_growth > 0:     score += w_rev.get('over_0', 3)
        else:                    score += w_rev.get('below_0', -5)
    else:
        details['rev_growth_yoy'] = None

    # 2. 毛利率
    gross_margin = info.get('grossMargins', None)
    if gross_margin is not None:
        details['gross_margin'] = gross_margin * 100
        w_gm = weights.get('gross_margin', {})
        if gross_margin > 0.60:   score += w_gm.get('over_60', 15)
        elif gross_margin > 0.40: score += w_gm.get('over_40', 10)
        elif gross_margin > 0.20: score += w_gm.get('over_20', 5)
        else:                     score += w_gm.get('default', 0)
    else:
        details['gross_margin'] = None

    # 3. 自由現金流 margin
    fcf = info.get('freeCashflow', None)
    rev = info.get('totalRevenue', None)
    if fcf and rev and rev > 0:
        fcf_margin = fcf / rev
        details['fcf_margin'] = fcf_margin * 100
        w_fcf = weights.get('fcf_margin', {})
        if fcf_margin > 0.20:   score += w_fcf.get('over_20', 10)
        elif fcf_margin > 0.10: score += w_fcf.get('over_10', 7)
        elif fcf_margin > 0:    score += w_fcf.get('over_0', 3)
        else:                   score += w_fcf.get('below_0', -5)
    else:
        details['fcf_margin'] = None

    # 4. 負債/股東權益
    de_ratio = info.get('debtToEquity', None)
    if de_ratio is not None:
        details['debt_equity'] = de_ratio
        w_de = weights.get('debt_equity', {})
        if de_ratio < 0.5:    score += w_de.get('below_05', 5)
        elif de_ratio < 1.5:  score += w_de.get('below_15', 2)
        elif de_ratio > 5.0:  score += w_de.get('over_50', -5)
    else:
        details['debt_equity'] = None

    # 5. 分析師評級
    rec = info.get('recommendationMean', None)
    if rec is not None:
        details['analyst_rec'] = rec
        w_rec = weights.get('analyst_rec', {})
        if rec < 1.8:    score += w_rec.get('below_18', 10)
        elif rec < 2.3:  score += w_rec.get('below_23', 7)
        elif rec < 3.0:  score += w_rec.get('below_30', 3)
        elif rec > 4.0:  score += w_rec.get('over_40', -5)
    else:
        details['analyst_rec'] = None

    # 總分限制在 0-100 之間
    final_score = min(100.0, max(0.0, score))

    details['health_score'] = round(final_score, 1)
    
    has_valid_data = rev_growth is not None or gross_margin is not None or de_ratio is not None
    details['source'] = 'yfinance' if has_valid_data else 'fallback'
    if not has_valid_data:
        details['health_score'] = 50.0  # 預設中庸分數
        
    return details


def get_fundamental_data(
    symbol,
    stock,
    info,
    current_price,
    cached_fund=None,
    cache_mgr=None,
    translate_summary_fn=None,
    config=None,
):
    if cached_fund is not None:
        fundamental = dict(cached_fund)
        fundamental["current_price"] = current_price
        # 若 cache 中尚未包含 fund_score，則補算
        if fundamental.get('fund_score') is None and info:
            score_details = compute_fundamental_score(symbol, info, config)
            fundamental['fund_score'] = score_details.get('health_score')
            fundamental['fund_score_details'] = score_details
        return fundamental, True

    fundamental = {k: info.get(k) for k in FUNDAMENTAL_KEYS}
    fundamental["current_price"] = current_price
    fundamental["company_name"] = info.get("longName") or info.get("shortName") or symbol

    raw_summary = fundamental.get("longBusinessSummary")
    if raw_summary and translate_summary_fn:
        fundamental["longBusinessSummary"] = translate_summary_fn(raw_summary)

    fcf = fundamental.get("freeCashflow")
    rev = fundamental.get("totalRevenue")
    if fcf and rev and rev > 0:
        fundamental["fcf_margin"] = round(fcf / rev * 100, 2)

    debt = fundamental.get("totalDebt")
    cash_val = fundamental.get("totalCash")
    if debt is not None and cash_val is not None:
        fundamental["net_debt"] = debt - cash_val

    try:
        cal = stock.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            ed_val = ed[0] if isinstance(ed, list) and ed else ed
            if ed_val:
                fundamental["next_earnings_date"] = str(ed_val)[:10]
    except Exception:
        pass

    # 計算基本面評分
    score_details = compute_fundamental_score(symbol, info, config)
    fundamental['fund_score'] = score_details.get('health_score')
    fundamental['fund_score_details'] = score_details

    if cache_mgr:
        fund_to_cache = {k: v for k, v in fundamental.items() if k != "current_price"}
        cache_mgr.set("fundamental", symbol, fund_to_cache)

    return fundamental, False


def fetch_fundamental(symbol, cache_mgr=None, translate_summary_fn=None, config=None):
    cached_fund = cache_mgr.get("fundamental", symbol) if cache_mgr else None
    stock = yf.Ticker(symbol)
    info = stock.info or {}
    current_price = extract_current_price(info)

    if translate_summary_fn is None:
        translate_summary_fn = translate_summary_with_gemini

    fundamental, from_cache = get_fundamental_data(
        symbol=symbol,
        stock=stock,
        info=info,
        current_price=current_price,
        cached_fund=cached_fund,
        cache_mgr=cache_mgr,
        translate_summary_fn=translate_summary_fn,
        config=config,
    )
    return fundamental, current_price, from_cache
