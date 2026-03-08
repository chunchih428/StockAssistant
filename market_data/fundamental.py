import yfinance as yf

from .fundamental_ai import translate_summary_with_gemini


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
]


def extract_current_price(info):
    return info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")


def get_fundamental_data(
    symbol,
    stock,
    info,
    current_price,
    cached_fund=None,
    cache_mgr=None,
    translate_summary_fn=None,
):
    if cached_fund is not None:
        fundamental = dict(cached_fund)
        fundamental["current_price"] = current_price
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

    if cache_mgr:
        fund_to_cache = {k: v for k, v in fundamental.items() if k != "current_price"}
        cache_mgr.set("fundamental", symbol, fund_to_cache)

    return fundamental, False


def fetch_fundamental(symbol, cache_mgr=None, translate_summary_fn=None):
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
    )
    return fundamental, current_price, from_cache
