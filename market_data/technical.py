import pandas as pd
import numpy as np

from .risk import compute_risk_score

# 預設的技術指標權重配置
DEFAULT_TECH_WEIGHTS = {
    'trend': {
        'UPTREND': 40, 'OVERSOLD_UPTREND': 35, 'RECOVERY': 25,
        'CONSOLIDATION': 20, 'BREAKDOWN': 10, 'DOWNTREND': 0, 'UNKNOWN': 20
    },
    'rsi': {
        'healthy_momentum': 20, # 40 <= rsi <= 65
        'normal': 12,           # 30 <= rsi < 40 or 65 < rsi <= 75
        'overheated': 5,        # rsi > 75
        'oversold': 8           # rsi < 30
    },
    'macd': {
        'bull_above_zero': 20, # macd > macd_sig and macd > 0
        'bull_below_zero': 12, # macd > macd_sig
        'bear_below_zero': 0,  # macd < macd_sig and macd < 0
        'bear_above_zero': 6   # macd < macd_sig and macd > 0
    },
    'bb': {
        'mid': 10,       # 0.3 <= bb <= 0.7
        'lower': 7,      # 0.1 <= bb < 0.3
        'below_low': 4,  # bb < 0.1
        'above_high': 4  # bb > 0.9
    },
    'atr': {
        'low_vol': 10,      # atr_pct < 0.02
        'normal_vol': 6,    # atr_pct < 0.04
        'high_vol': 2,      # atr_pct < 0.06
        'extreme_vol': 0    # atr_pct >= 0.06
    }
}


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


# ─── 指標計算函數 ─────────────────────────────────────────────────────────

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def compute_macd(close: pd.Series,
                 fast: int = 12, slow: int = 26, signal: int = 9
                 ) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0
                      ) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """當日成交量 / N日均量"""
    avg_vol = volume.rolling(period).mean()
    return volume / avg_vol.replace(0, np.nan)


def classify_trend(close_val, ma20, ma50, ma200, rsi) -> str:
    """根據 MA 排列與 RSI 分類趨勢狀態"""
    if pd.isna(ma20) or pd.isna(ma50):
        return "UNKNOWN"

    above_ma50  = close_val > ma50
    above_ma200 = close_val > ma200 if not pd.isna(ma200) else True
    ma20_vs_50  = ma20 > ma50

    if above_ma50 and above_ma200 and ma20_vs_50:
        if not pd.isna(rsi) and rsi < 30:
            return "OVERSOLD_UPTREND"   # 上升趨勢中超賣，可能機會
        return "UPTREND"
    elif close_val < ma50 and not ma20_vs_50:
        if not above_ma200:
            return "DOWNTREND"          # 全面破位
        return "BREAKDOWN"              # 跌破 MA50，MA200 尚在支撐
    elif close_val > ma50 and not ma20_vs_50:
        return "RECOVERY"               # 收回 MA50 但 MA20 仍在下方
    else:
        return "CONSOLIDATION"


def compute_tech_score(trend, rsi, macd, macd_sig, bb_pct, atr_pct, weights=None) -> float:
    """
    技術健康分數 0–100
    可以動態傳入 weights 來覆蓋預設權重。

    權重優先順序：
        1. weights 參數（直接傳入）
        2. monitor_config.json 的 scoring_weights.technical
        3. DEFAULT_TECH_WEIGHTS（程式碼預設值）
    """
    if weights is None:
        try:
            from monitor.config import get_scoring_weights
            weights = get_scoring_weights().get('technical')
        except Exception:
            pass
    if weights is None:
        weights = DEFAULT_TECH_WEIGHTS

    score = 0.0
    score += weights.get('trend', {}).get(trend, 20)

    # RSI 分
    if not pd.isna(rsi):
        w_rsi = weights.get('rsi', {})
        if 40 <= rsi <= 65:
            score += w_rsi.get('healthy_momentum', 20)
        elif 30 <= rsi < 40 or 65 < rsi <= 75:
            score += w_rsi.get('normal', 12)
        elif rsi > 75:
            score += w_rsi.get('overheated', 5)
        elif rsi < 30:
            score += w_rsi.get('oversold', 8)

    # MACD 分
    if not pd.isna(macd) and not pd.isna(macd_sig):
        w_macd = weights.get('macd', {})
        if macd > macd_sig and macd > 0:
            score += w_macd.get('bull_above_zero', 20)
        elif macd > macd_sig:
            score += w_macd.get('bull_below_zero', 12)
        elif macd < macd_sig and macd < 0:
            score += w_macd.get('bear_below_zero', 0)
        else:
            score += w_macd.get('bear_above_zero', 6)

    # 布林帶位置
    if not pd.isna(bb_pct):
        w_bb = weights.get('bb', {})
        if 0.3 <= bb_pct <= 0.7:
            score += w_bb.get('mid', 10)
        elif 0.1 <= bb_pct < 0.3:
            score += w_bb.get('lower', 7)
        elif bb_pct < 0.1:
            score += w_bb.get('below_low', 4)
        elif bb_pct > 0.9:
            score += w_bb.get('above_high', 4)

    # ATR 正規化分
    if not pd.isna(atr_pct):
        w_atr = weights.get('atr', {})
        if atr_pct < 0.02:
            score += w_atr.get('low_vol', 10)
        elif atr_pct < 0.04:
            score += w_atr.get('normal_vol', 6)
        elif atr_pct < 0.06:
            score += w_atr.get('high_vol', 2)
        else:
            score += w_atr.get('extreme_vol', 0)

    return min(100.0, max(0.0, score))


def compute_technical_from_history(hist, config=None, info=None):
    """Compute technical metrics from a 1-year OHLCV history DataFrame."""
    tech = {}
    if hist is None or hist.empty:
        return tech

    close = hist['Close']
    vol = hist['Volume']
    high = hist.get('High', close)
    low  = hist.get('Low', close)

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

    # 進階技術指標與分數計算
    try:
        if len(close) >= 20:
            ma20 = close.rolling(20).mean()
            ma50 = close.rolling(50).mean() if len(close) >= 50 else pd.Series(np.nan, index=close.index)
            ma200 = close.rolling(200).mean() if len(close) >= 200 else pd.Series(np.nan, index=close.index)

            rsi_series = compute_rsi(close, 14)
            macd_line, signal_line, macd_hist = compute_macd(close)
            bb_u, bb_m, bb_l = compute_bollinger(close, 20, 2.0)
            atr_series = compute_atr(high, low, close, 14)
            vol_ratio_series = compute_volume_ratio(vol, 20)

            last_close = float(close.iloc[-1])
            last_ma20 = float(ma20.iloc[-1])
            last_ma50 = float(ma50.iloc[-1])
            last_ma200 = float(ma200.iloc[-1])
            last_rsi = float(rsi_series.iloc[-1])
            last_macd = float(macd_line.iloc[-1])
            last_signal = float(signal_line.iloc[-1])
            last_bb_u = float(bb_u.iloc[-1])
            last_bb_l = float(bb_l.iloc[-1])
            bb_pct_val = (last_close - last_bb_l) / (last_bb_u - last_bb_l) if (last_bb_u - last_bb_l) != 0 else np.nan
            last_atr = float(atr_series.iloc[-1])
            atr_pct_val = last_atr / last_close if last_close != 0 else np.nan
            last_vol_ratio = float(vol_ratio_series.iloc[-1])

            trend = classify_trend(last_close, last_ma20, last_ma50, last_ma200, last_rsi)

            # 從 config 中取得權重，如果沒有則使用預設
            weights = (config or {}).get('technical_weights', DEFAULT_TECH_WEIGHTS)
            tech_score = compute_tech_score(trend, last_rsi, last_macd, last_signal, bb_pct_val, atr_pct_val, weights)

            tech.update({
                'ma20': _safe_round(last_ma20),
                'rsi14': _safe_round(last_rsi),
                'macd': _safe_round(last_macd, 3),
                'macd_signal': _safe_round(last_signal, 3),
                'bb_upper': _safe_round(last_bb_u),
                'bb_lower': _safe_round(last_bb_l),
                'bb_pct': _safe_round(bb_pct_val),
                'atr14': _safe_round(last_atr),
                'vol_ratio': _safe_round(last_vol_ratio),
                'trend_status': trend,
                'tech_score': _safe_round(tech_score)
            })
    except Exception as e:
        # 當資料不足或計算錯誤時，退回到基本計算，不阻斷執行
        pass

    if len(close) > 0:
        returns = close.pct_change()
        risk_details = compute_risk_score(returns, info or {}, config)
        tech.update(risk_details)

    return tech


def fetch_technical(symbol, stock, cached_tech=None, cache_mgr=None, config=None):
    """Fetch/cache technical data for a ticker."""
    if cached_tech is not None:
        return dict(cached_tech), True

    hist = stock.history(period='1y')
    info = stock.info or {}
    tech = compute_technical_from_history(hist, config, info)

    if cache_mgr:
        cache_mgr.set('technical', symbol, tech)

    return tech, False
