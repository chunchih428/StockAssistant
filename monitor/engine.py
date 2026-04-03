"""
monitor/engine.py — 監測主引擎

run_monitor() 是與外部（stock_assistant.py）的唯一介面，
接收 results / allocation / candidate_symbols / config，
回傳可直接序列化成 JSON 嵌入 index.html 的 alerts_data dict。
"""
from __future__ import annotations

from datetime import datetime

from .config import load_monitor_config, get_thresholds, get_scoring_weights
from .rules import RuleContext, run_all_rules, LEVEL_HOLD, LEVEL_CLOSE, LEVEL_REDUCE, LEVEL_WATCH, LEVEL_ADD, LEVEL_COLOR
from .scorer import score_candidate


# ─── 組合層級規則 ────────────────────────────────────────────
def _portfolio_alerts(allocation: dict, results: list, thresholds: dict) -> list[dict]:
    """
    計算組合層級警示：HHI 集中度 / Top-1 / Portfolio Beta。
    回傳 list of {level, rule, msg, level_color}。
    """
    alerts = []
    positions = [p for p in allocation.get("positions", []) if (p.get("market_value") or 0) > 0]
    total_mv = sum(p["market_value"] for p in positions)
    if total_mv <= 0:
        return alerts

    # ── Top-1 集中度 ──────────────────────────────────────
    pcts = sorted(
        [(p["symbol"], p["market_value"] / total_mv * 100) for p in positions],
        key=lambda x: -x[1],
    )
    if pcts:
        top_sym, top_pct = pcts[0]
        warn = thresholds.get("warn_top1_pct", 25)
        hard = thresholds.get("max_top1_pct", 35)
        if top_pct >= hard:
            alerts.append(_palert(LEVEL_REDUCE, "top1_concentration",
                f"最大持倉 {top_sym} 佔 {top_pct:.1f}%（>{hard}%），高度集中，建議分批減倉"))
        elif top_pct >= warn:
            alerts.append(_palert(LEVEL_REDUCE, "top1_concentration_warn",
                f"最大持倉 {top_sym} 佔 {top_pct:.1f}%（>{warn}%），注意集中度"))

    # ── HHI ───────────────────────────────────────────────
    hhi = sum((p["market_value"] / total_mv) ** 2 for p in positions)
    hard_hhi = thresholds.get("max_hhi", 0.25)
    warn_hhi = thresholds.get("warn_hhi", 0.15)
    if hhi > hard_hhi:
        alerts.append(_palert(LEVEL_REDUCE, "hhi_high",
            f"HHI 集中度 {hhi:.3f}（>{hard_hhi}），組合高度集中，建議分散配置"))
    elif hhi > warn_hhi:
        alerts.append(_palert(LEVEL_REDUCE, "hhi_warn",
            f"HHI 集中度 {hhi:.3f}（>{warn_hhi}），中度集中"))

    # ── 加權平均 Beta ──────────────────────────────────────
    beta_vals, beta_weights = [], []
    for r in results:
        if r.get("stock_info", {}).get("category") == "競品參考":
            continue
        beta = r.get("stock_data", {}).get("fundamental", {}).get("beta")
        shares = r.get("stock_info", {}).get("shares", 0) or 0
        price = r.get("stock_data", {}).get("fundamental", {}).get("current_price") or 0
        mv = price * shares
        if beta is not None and mv > 0:
            try:
                beta_vals.append(float(beta))
                beta_weights.append(mv)
            except (TypeError, ValueError):
                pass
    if beta_vals:
        total_w = sum(beta_weights)
        port_beta = sum(b * w for b, w in zip(beta_vals, beta_weights)) / total_w
        hard_beta = thresholds.get("max_portfolio_beta", 1.6)
        warn_beta = thresholds.get("warn_portfolio_beta", 1.3)
        if port_beta > hard_beta:
            alerts.append(_palert(LEVEL_REDUCE, "beta_high",
                f"組合加權 Beta = {port_beta:.2f}（>{hard_beta}），大盤波動放大效應高"))
        elif port_beta > warn_beta:
            alerts.append(_palert(LEVEL_REDUCE, "beta_warn",
                f"組合加權 Beta = {port_beta:.2f}（>{warn_beta}），波動偏高"))

    return alerts


def _cash_alerts(allocation: dict, thresholds: dict) -> list[dict]:
    """現金部位監測：過多（機會成本）或過少（緩衝不足）都會觸發警示。"""
    alerts = []
    total_value = allocation.get("total_value", 0)
    cash = allocation.get("cash", 0)
    if total_value <= 0:
        return alerts

    cash_pct = cash / total_value * 100
    max_pct  = thresholds.get("max_cash_pct", 25)
    warn_pct = thresholds.get("warn_high_cash_pct", 18)
    min_pct  = thresholds.get("min_cash_pct", 5)

    if cash_pct > max_pct:
        alerts.append(_palert(LEVEL_REDUCE, "cash_excess",
            f"現金佔比 {cash_pct:.1f}%（>{max_pct}%），機會成本偏高，可考慮分批進場"))
    elif cash_pct > warn_pct:
        alerts.append(_palert(LEVEL_WATCH, "cash_high",
            f"現金佔比 {cash_pct:.1f}%（>{warn_pct}%），保守佈局，留意錯失反彈機會"))
    elif cash_pct < min_pct:
        alerts.append(_palert(LEVEL_WATCH, "cash_low",
            f"現金佔比 {cash_pct:.1f}%（<{min_pct}%），緩衝過薄，市場回調時風險偏高"))

    return alerts


def _palert(level, rule, msg) -> dict:
    return {
        "level": level,
        "rule": rule,
        "msg": msg,
        "level_color": LEVEL_COLOR.get(level, "#94a3b8"),
    }


# ─── 主引擎 ─────────────────────────────────────────────────
def run_monitor(
    results: list,
    allocation: dict,
    candidate_symbols: list[str],
    config: dict | None = None,
    monitor_config_path=None,
) -> dict:
    """
    監測主引擎。

    Parameters
    ----------
    results            : fetch_holdings_data() 回傳的 list
    allocation         : calculate_allocation() 回傳的 dict
    candidate_symbols  : 候選股代號清單（來自 candidates.txt）
    config             : stock_assistant 的 config（可選，用於取得其他設定）
    monitor_config_path: 指定 monitor_config.json 路徑（測試用）

    Returns
    -------
    alerts_data dict，可直接嵌入 index.html 的 embedded_json。
    """
    mon_cfg = load_monitor_config(monitor_config_path)

    # ── 計算全局閾值（不含個股 override，個股層再各自取）
    global_thresholds = mon_cfg.get("thresholds", {})

    # ── 組合層級警示 ──────────────────────────────────────
    portfolio_alerts = _portfolio_alerts(allocation, results, global_thresholds)
    portfolio_alerts += _cash_alerts(allocation, global_thresholds)

    # ── 計算 alloc_pct 對照表 ──────────────────────────────
    total_mv = sum(
        (p.get("market_value") or 0)
        for p in allocation.get("positions", [])
    )
    alloc_map: dict[str, float] = {}
    for p in allocation.get("positions", []):
        sym = p.get("symbol", "")
        mv = p.get("market_value") or 0
        alloc_map[sym] = mv / total_mv * 100 if total_mv > 0 else 0.0

    # ── 持股逐股警示 ──────────────────────────────────────
    portfolio_symbols = set()
    holdings_alerts: dict[str, dict] = {}

    for r in results:
        si = r.get("stock_info", {})
        sd = r.get("stock_data", {})
        ar = r.get("analysis_result", {}) or {}
        symbol = si.get("symbol", "")
        category = si.get("category", "")

        # 跳過競品參考（不在持倉內）
        if category == "競品參考":
            continue

        fund  = sd.get("fundamental", {})
        tech  = sd.get("technical", {})
        price = fund.get("current_price")
        cost  = si.get("cost_basis", 0)
        shares = si.get("shares", 0)

        # 只處理有實際持股的標的
        if not shares or shares <= 0:
            continue

        portfolio_symbols.add(symbol)
        pnl_pct = ((price - cost) / cost * 100) if price and cost else None
        alloc_pct = alloc_map.get(symbol)
        rec = ar.get("recommendation", "") or ""

        # 取得個股有效閾值（套用 override）
        thresholds = get_thresholds(mon_cfg, symbol)

        ctx = RuleContext(
            symbol=symbol,
            fund=fund,
            tech=tech,
            alloc_pct=alloc_pct,
            pnl_pct=pnl_pct,
            recommendation=rec,
            thresholds=thresholds,
        )
        alerts = run_all_rules(ctx)
        top_level = alerts[0].level if alerts else LEVEL_HOLD

        holdings_alerts[symbol] = {
            "symbol":    symbol,
            "top_level": top_level,
            "top_level_color": LEVEL_COLOR.get(top_level, "#94a3b8"),
            "alerts":    [a.to_dict() for a in alerts],
            "pnl_pct":   round(pnl_pct, 2) if pnl_pct is not None else None,
            "alloc_pct": round(alloc_pct, 2) if alloc_pct is not None else None,
        }

    # ── 候選股評分 ────────────────────────────────────────
    # 建立 symbol → result 的對照表（從已抓的 results 中找）
    results_map = {
        r["stock_info"]["symbol"]: r
        for r in results
        if r.get("stock_info", {}).get("symbol")
    }

    scored_candidates = []
    for sym in candidate_symbols:
        r = results_map.get(sym, {})
        fund = r.get("stock_data", {}).get("fundamental", {}) if r else {}
        tech  = r.get("stock_data", {}).get("technical", {})  if r else {}

        # 若 results 沒有（候選股可能不在 holdings/競品資料中），嘗試讀 cache
        if not fund and not tech:
            fund, tech = _load_from_cache(sym)

        cs = score_candidate(
            symbol=sym,
            fund=fund,
            tech=tech,
            in_portfolio=(sym in portfolio_symbols),
            config=mon_cfg,
        )
        scored_candidates.append(cs.to_dict())

    # 依綜合分降序排列（None 排最後）
    scored_candidates.sort(key=lambda x: -(x.get("composite") or -999))

    return {
        "generated_at": datetime.now().isoformat(),
        "portfolio":    portfolio_alerts,
        "holdings":     holdings_alerts,
        "candidates":   scored_candidates,
    }


def _load_from_cache(symbol: str) -> tuple[dict, dict]:
    """嘗試從 cache/ 讀取 fund + tech，找不到回傳空 dict。"""
    try:
        from pathlib import Path
        from cache_manager import load_latest_cache_json
        cache_dir = Path(__file__).resolve().parent.parent / "cache"
        # 先嘗試 holdings，再嘗試 competitors
        for scope in ("holdings", "competitors"):
            fund = load_latest_cache_json(cache_dir, scope, "fundamental", symbol)
            tech = load_latest_cache_json(cache_dir, scope, "technical",   symbol)
            if fund or tech:
                return fund, tech
    except Exception:
        pass
    return {}, {}
