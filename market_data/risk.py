import numpy as np
import pandas as pd

# 日化無風險利率（假設5%年化）
RISK_FREE = 0.05 / 252

# 風險評分權重定義 (0 - 100分，愈高分代表風險愈低/風險回報愈好)
DEFAULT_RISK_WEIGHTS = {
    'var_95': {
        'above_minus_2pct': 30,  # 損失 < 2%
        'above_minus_4pct': 20,  # 損失 < 4%
        'above_minus_6pct': 10,  # 損失 < 6%
        'below_minus_6pct': 0    # 損失 >= 6%
    },
    'sharpe': {
        'above_1': 25,
        'above_05': 15,
        'above_0': 5,
        'below_0': 0
    },
    'sortino': {
        'above_15': 25,
        'above_1': 15,
        'above_0': 5,
        'below_0': 0
    },
    'beta': {
        'below_08': 20,
        'below_12': 15,
        'below_15': 5,
        'above_15': 0
    }
}

def _safe_round(val, digits=2):
    try:
        if val is None or pd.isna(val):
            return None
        return round(float(val), digits)
    except Exception:
        return None

def compute_var_cvar(returns: pd.Series, conf_95=0.95, conf_99=0.99):
    """歷史模擬法計算 1-day VaR & CVaR"""
    clean = returns.dropna()
    if len(clean) < 20:
        return np.nan, np.nan, np.nan
    var_95 = np.percentile(clean, (1 - conf_95) * 100)
    var_99 = np.percentile(clean, (1 - conf_99) * 100)
    cvar_95 = clean[clean <= var_95].mean()
    return var_95, var_99, cvar_95


def compute_sharpe_sortino(returns: pd.Series, rf: float = RISK_FREE) -> tuple[float, float]:
    """計算全期的 Sharpe 與 Sortino"""
    clean = returns.dropna()
    if len(clean) < 20:
        return np.nan, np.nan

    excess = clean - rf
    std = clean.std()
    sharpe = excess.mean() / std * np.sqrt(252) if std > 0 else np.nan

    downside = clean[clean < 0].std() * np.sqrt(252)
    sortino = (clean.mean() - rf) * 252 / downside if downside > 0 else np.nan
    
    return sharpe, sortino


def compute_risk_score(returns: pd.Series, info: dict, config: dict = None) -> dict:
    weights = (config or {}).get('risk_weights', DEFAULT_RISK_WEIGHTS)
    
    score = 0.0
    details = {}
    
    var_95, var_99, cvar_95 = compute_var_cvar(returns)
    sharpe, sortino = compute_sharpe_sortino(returns)
    beta = info.get('beta', None)
    
    # 1. VaR 95 (0 - 30 分)
    if not np.isnan(var_95):
        details['var_95'] = _safe_round(var_95 * 100, 2)
        w_var = weights.get('var_95', {})
        if var_95 > -0.02:    score += w_var.get('above_minus_2pct', 30)
        elif var_95 > -0.04:  score += w_var.get('above_minus_4pct', 20)
        elif var_95 > -0.06:  score += w_var.get('above_minus_6pct', 10)
        else:                 score += w_var.get('below_minus_6pct', 0)
    else:
        details['var_95'] = None
        
    # 2. Sharpe (0 - 25 分)
    if not np.isnan(sharpe):
        details['sharpe'] = _safe_round(sharpe, 2)
        w_sharpe = weights.get('sharpe', {})
        if sharpe > 1.0:   score += w_sharpe.get('above_1', 25)
        elif sharpe > 0.5: score += w_sharpe.get('above_05', 15)
        elif sharpe > 0:   score += w_sharpe.get('above_0', 5)
        else:              score += w_sharpe.get('below_0', 0)
    else:
        details['sharpe'] = None
        
    # 3. Sortino (0 - 25 分)
    if not np.isnan(sortino):
        details['sortino'] = _safe_round(sortino, 2)
        w_sortino = weights.get('sortino', {})
        if sortino > 1.5:   score += w_sortino.get('above_15', 25)
        elif sortino > 1.0: score += w_sortino.get('above_1', 15)
        elif sortino > 0:   score += w_sortino.get('above_0', 5)
        else:               score += w_sortino.get('below_0', 0)
    else:
        details['sortino'] = None
        
    # 4. Beta (0 - 20 分)
    if beta is not None and not np.isnan(beta):
        details['beta'] = _safe_round(beta, 2)
        w_beta = weights.get('beta', {})
        if beta < 0.8:    score += w_beta.get('below_08', 20)
        elif beta < 1.2:  score += w_beta.get('below_12', 15)
        elif beta < 1.5:  score += w_beta.get('below_15', 5)
        else:             score += w_beta.get('above_15', 0)
    else:
        details['beta'] = None
        
    # 在歷史資料不足時，給一個中庸分數 50 分
    if np.isnan(var_95) and np.isnan(sharpe) and beta is None:
        final_score = 50.0
    else:
        final_score = min(100.0, max(0.0, score))
        
    details['risk_score'] = round(final_score, 1)
    return details


# ─── 組合層級風險 ──────────────────────────────────────────────────────────

def compute_hhi(market_values) -> float:
    """Herfindahl-Hirschman Index（集中度，0=完全分散，1=完全集中）"""
    arr = np.array([abs(float(v)) for v in market_values if v is not None], dtype=float)
    total = arr.sum()
    if total <= 0:
        return np.nan
    w = arr / total
    return float((w ** 2).sum())


def compute_portfolio_risk_metrics(allocation: dict, results: list) -> dict:
    """
    計算組合層級風險指標：
    - HHI 集中度 + Top-1/3/5
    - 有效槓桿（含選擇權市值）
    - 加權平均 Beta（由個股 yfinance beta 加權）
    """
    positions = [p for p in allocation.get('positions', []) if (p.get('market_value') or 0) > 0]
    total_value = allocation.get('total_value', 0)

    if not positions or total_value <= 0:
        return {}

    market_values = [p['market_value'] for p in positions]

    # HHI
    hhi = compute_hhi(market_values)
    if np.isnan(hhi):
        hhi_label = 'N/A'
    elif hhi > 0.25:
        hhi_label = '高度集中'
    elif hhi > 0.15:
        hhi_label = '中度集中'
    elif hhi > 0.08:
        hhi_label = '適度集中'
    else:
        hhi_label = '分散'

    # Top-1/3/5 集中度
    sorted_pcts = sorted([p['alloc_pct'] for p in positions], reverse=True)
    top1 = sorted_pcts[0] if sorted_pcts else 0
    top3 = sum(sorted_pcts[:3])
    top5 = sum(sorted_pcts[:5])

    # 有效槓桿 = (股票市值 + 選擇權市值) / 組合淨值
    stock_exposure = sum(abs(v) for v in market_values)
    options_value = abs(allocation.get('options_value') or 0)
    effective_leverage = (stock_exposure + options_value) / total_value

    # 加權平均 Beta（排除競品）
    beta_vals, beta_weights = [], []
    for r in results:
        if r.get('stock_info', {}).get('category') == '競品參考':
            continue
        beta = r.get('stock_data', {}).get('fundamental', {}).get('beta')
        price = r.get('stock_data', {}).get('fundamental', {}).get('current_price') or 0
        shares = r.get('stock_info', {}).get('shares') or 0
        mv = price * shares
        if beta is not None and mv > 0:
            try:
                beta_vals.append(float(beta))
                beta_weights.append(mv)
            except (TypeError, ValueError):
                pass

    portfolio_beta = None
    if beta_vals:
        total_w = sum(beta_weights)
        if total_w > 0:
            portfolio_beta = sum(b * w for b, w in zip(beta_vals, beta_weights)) / total_w

    return {
        'hhi': _safe_round(hhi, 4),
        'hhi_label': hhi_label,
        'top1_concentration': _safe_round(top1, 1),
        'top3_concentration': _safe_round(top3, 1),
        'top5_concentration': _safe_round(top5, 1),
        'effective_leverage': _safe_round(effective_leverage, 3),
        'portfolio_beta': _safe_round(portfolio_beta, 2),
    }
