import pandas as pd


def _safe_round(val, digits=2):
    """Safely round numeric values while tolerating None/NaN."""
    try:
        if val is None:
            return None
        if pd.isna(val):
            return None
        return round(float(val), digits)
    except Exception:
        return None


def compute_technical_from_history(hist):
    """Compute technical metrics from a 1-year OHLCV history DataFrame."""
    tech = {}
    if hist is None or hist.empty:
        return tech

    close = hist['Close']
    vol = hist['Volume']
    if len(close) > 0:
        tech['current_price'] = _safe_round(close.iloc[-1])

    if len(close) >= 50:
        tech['ma50'] = _safe_round(close.rolling(50).mean().iloc[-1])
    if len(close) >= 200:
        tech['ma200'] = _safe_round(close.rolling(200).mean().iloc[-1])
    tech['high_52w'] = _safe_round(close.max())
    tech['low_52w'] = _safe_round(close.min())

    if len(vol) >= 20:
        tech['avg_vol_20d'] = int(vol.tail(20).mean())
    if len(vol) > 0:
        tech['current_vol'] = int(vol.iloc[-1])

    if len(close) >= 60:
        p_now = float(close.iloc[-1])
        p_3mo = float(close.iloc[-60])
        tech['change_3mo_pct'] = _safe_round((p_now - p_3mo) / p_3mo * 100)

    return tech


def fetch_technical(symbol, stock, cached_tech=None, cache_mgr=None):
    """Fetch/cache technical data for a ticker."""
    if cached_tech is not None:
        return dict(cached_tech), True

    hist = stock.history(period='1y')
    tech = compute_technical_from_history(hist)

    if cache_mgr:
        cache_mgr.set('technical', symbol, tech)

    return tech, False
