#!/usr/bin/env python3
"""
Stock Risk Monitor — 終端快速查看工具
═══════════════════════════════════════════════════════════
讀取最新 cache 資料，即時輸出：
  ① 持股警示（停損 / 減倉 / 加倉機會）
  ② 組合層級風險（HHI / 集中度 / Beta / 現金比例）
  ③ 候選股評分排行

不需要 API Key，直接讀取 cache/ 資料夾，秒出結果。
主要邏輯已移到 monitor/ 套件，此腳本僅負責 CLI 介面與終端格式化輸出。

Usage:
    python monitor.py              # 完整報告
    python monitor.py --brief      # 只顯示有警示的持股（略過 HOLD）
    python monitor.py --candidates # 只顯示候選股評分
    python monitor.py --json       # 輸出 JSON（供外部串接）
    python monitor.py --backtest [--days 20]  # 回測各規則準確率
    python monitor.py --optimize [--dry-run]  # 優化閾值 + 評分權重
═══════════════════════════════════════════════════════════
"""

import csv
import json
import sys
from pathlib import Path

BASE_DIR        = Path(__file__).parent
CACHE_DIR       = BASE_DIR / "cache"
CONFIG_DIR      = BASE_DIR / "config"
PORTFOLIO_FILE  = CONFIG_DIR / "holdings.csv"
CANDIDATES_FILE = CONFIG_DIR / "candidates.txt"
ARCHIVE_DIR     = BASE_DIR / "archive"

# ─── ANSI 顏色 ────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty() or "--color" in sys.argv

def _c(s, code): return f"\033[{code}m{s}\033[0m" if _USE_COLOR else str(s)
def bold(s):   return _c(s, "1")
def red(s):    return _c(s, "91")
def orange(s): return _c(s, "33")
def yellow(s): return _c(s, "93")
def green(s):  return _c(s, "92")
def blue(s):   return _c(s, "94")
def cyan(s):   return _c(s, "96")
def grey(s):   return _c(s, "90")
def purple(s): return _c(s, "95")

LEVEL_COLOR_FN = {0: red, 1: orange, 2: yellow, 3: purple, 4: green}

def score_str(score, width=3):
    if score is None: return grey("—".center(width))
    s = str(int(round(score))).center(width)
    if score >= 80: return green(s)
    if score >= 60: return blue(s)
    if score >= 40: return yellow(s)
    return red(s)

def pnl_str(val, suffix="%"):
    if val is None: return grey("—")
    sign = "+" if val >= 0 else ""
    return green(f"{sign}{val:.1f}{suffix}") if val >= 0 else red(f"{val:.1f}{suffix}")

def alloc_str(pct):
    if pct is None: return grey("—")
    s = f"{pct:.1f}%"
    return red(s) if pct >= 30 else yellow(s) if pct >= 20 else cyan(s)

TREND_DISP = {
    "UPTREND":         green("↑↑ 上升"),
    "OVERSOLD_UPTREND":green("↑  超賣反彈"),
    "RECOVERY":        cyan("↗  修復中"),
    "CONSOLIDATION":   yellow("→  盤整"),
    "BREAKDOWN":       red("↓  崩跌"),
    "DOWNTREND":       red("↓↓ 下跌"),
    "UNKNOWN":         grey("?  未知"),
}


# ─── 資料載入 ─────────────────────────────────────────────────
def _load_cache(scope: str, category: str, symbol: str) -> dict:
    if not CACHE_DIR.exists():
        return {}
    date_dirs = sorted(
        [d for d in CACHE_DIR.iterdir() if d.is_dir() and len(d.name) == 10],
        key=lambda d: d.name, reverse=True,
    )
    for d in date_dirs:
        path = d / scope / category / f"{symbol}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}

def load_fund(symbol, scope="holdings"): return _load_cache(scope, "fundamental", symbol)
def load_tech(symbol, scope="holdings"): return _load_cache(scope, "technical",   symbol)


def load_holdings() -> list[dict]:
    if not PORTFOLIO_FILE.exists():
        return []
    stocks = {}
    with open(PORTFOLIO_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = (row.get("symbol") or row.get("ticker") or row.get("股名") or "").strip().upper()
            if not symbol or symbol == "CASH" or "(" in symbol:
                continue
            try:
                shares = float(row.get("shares") or row.get("股數") or 0)
                cost   = float(row.get("cost_basis") or row.get("price") or row.get("買價") or 0)
            except ValueError:
                continue
            category = (row.get("category") or row.get("類別") or "").strip()
            if symbol in stocks:
                prev = stocks[symbol]
                total = prev["shares"] + shares
                wc = (prev["shares"] * prev["cost"] + shares * cost) / total if total else cost
                stocks[symbol] = {"symbol": symbol, "shares": total, "cost": wc, "category": category or prev["category"]}
            else:
                stocks[symbol] = {"symbol": symbol, "shares": shares, "cost": cost, "category": category}
    return [v for v in stocks.values() if v["shares"] > 0]


def load_candidates() -> list[str]:
    if not CANDIDATES_FILE.exists():
        return []
    out = []
    for line in CANDIDATES_FILE.read_text(encoding="utf-8").splitlines():
        sym = line.split("#", 1)[0].strip().upper()
        if sym and sym not in out:
            out.append(sym)
    return out


# ─── 終端報告格式化 ─────────────────────────────────────────
def _sep(char="─", w=72): print(grey(char * w))

def _header(title):
    w = 72
    print()
    print(bold(cyan("┌" + "─" * (w-2) + "┐")))
    pad = (w - 2 - len(title)) // 2
    print(bold(cyan("│")) + " " * pad + bold(title) + " " * (w - 2 - pad - len(title)) + bold(cyan("│")))
    print(bold(cyan("└" + "─" * (w-2) + "┘")))


def _run_terminal(brief=False, candidates_only=False):
    """終端模式主流程：從 cache 讀取，即時評估並輸出。"""
    from datetime import datetime
    from monitor import run_monitor
    from monitor.config import load_monitor_config

    holdings   = load_holdings()
    candidates = load_candidates()
    mon_cfg    = load_monitor_config()

    # 建立 results 格式（仿 stock_assistant.py 的 results list）
    results, total_mv = _build_results_from_cache(holdings)
    allocation = _build_allocation_from_cache(holdings, results, mon_cfg)

    alerts_data = run_monitor(results, allocation, candidates, mon_cfg)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print()
    print(bold(cyan("═" * 72)))
    print(bold(cyan(f"  📊 Stock Risk Monitor    {now_str}")))
    print(bold(cyan("═" * 72)))

    # ─ 組合警示 ──────────────────────────────────────────
    if not candidates_only:
        _header("① 持股即時警示")
        port = alerts_data.get("portfolio", [])
        if port:
            print()
            print(bold("  📦 組合層級警示"))
            for a in port:
                level_fn = LEVEL_COLOR_FN.get(a["level"], grey)
                print(f"    {level_fn(a['level_icon'])} {a['msg']}")

        holdings_map = alerts_data.get("holdings", {})
        if holdings_map:
            print()
            print(grey(f"  {'代號':<7} {'配置':>6} {'損益%':>8} {'基本面':^5} {'技術面':^5} {'風險':^5}  {'趨勢'}"))
            _sep()
            for sym, h in sorted(holdings_map.items(), key=lambda x: x[1]["top_level"]):
                if brief and h["top_level"] >= 4:
                    continue
                # 從 cache 讀取評分
                fund = load_fund(sym)
                tech  = load_tech(sym)
                fs = fund.get("fund_score")
                ts = tech.get("tech_score")
                rs = tech.get("risk_score")
                trend = tech.get("trend_status") or "UNKNOWN"
                trend_d = TREND_DISP.get(trend, grey(trend))
                print(
                    f"  {bold(sym):<7} {alloc_str(h['alloc_pct']):>6} {pnl_str(h['pnl_pct']):>8} "
                    f"{score_str(fs):^5} {score_str(ts):^5} {score_str(rs):^5}  {trend_d}"
                )
                for a in h["alerts"]:
                    lv = a["level"]
                    if lv == 4 and brief:
                        continue
                    fn = LEVEL_COLOR_FN.get(lv, grey)
                    icon = a.get("level_icon", "")
                    label = a.get("level_label", "")
                    print(f"    {fn(icon + ' ' + label):<22} {a['msg']}")
                print()
        elif not brief:
            print(grey("\n  ℹ️  無持股警示資料（請先執行 python stock_assistant.py）"))

    # ─ 候選股排行 ────────────────────────────────────────
    _header("② 候選股評分排行")
    cands = alerts_data.get("candidates", [])
    if not cands:
        print(yellow("  ⚠️  找不到候選股，請確認 config/candidates.txt"))
    else:
        print()
        print(grey(f"  {'#':>2}  {'代號':<7} {'綜合分':>6} {'基本面':^5} {'技術面':^5} {'風險':^5}  {'趨勢':<14} {'信號'}"))
        _sep()
        for i, c in enumerate(cands, 1):
            trend = c.get("trend") or "UNKNOWN"
            td = TREND_DISP.get(trend, grey(trend))
            comp = c.get("composite")
            comp_s = bold(score_str(comp, 4)) if comp else grey(" — ")
            sig = c.get("signal", "")
            in_port = f" {cyan('[持]')}" if c.get("in_portfolio") else ""
            print(
                f"  {i:>2}. {bold(c['symbol']):<7} {comp_s:>6} "
                f"{score_str(c.get('fund_score')):^5} {score_str(c.get('tech_score')):^5} "
                f"{score_str(c.get('risk_score')):^5}  {td:<14} {purple(sig)}{in_port}"
            )
            reasons = c.get("reasons", [])
            if reasons:
                print(f"     {grey('→')} {grey(' ｜ '.join(reasons[:3]))}")
        print()

    # ─ 操作說明 ─────────────────────────────────────────
    _sep("═")
    print(bold("  操作說明"))
    print(f"  {red('🔴 停損/平倉')}  → 立即評估是否出場")
    print(f"  {orange('🟠 減倉建議')}  → 分批減少 1/3～1/2 倉位")
    print(f"  {yellow('🟡 觀察警示')}  → 設好停損點，密切關注支撐")
    print(f"  {purple('💎 加倉機會')}  → 條件符合時分批加碼（每次 ≤ 5% 總資金）")
    print(f"  {green('🟢 持有')}      → 各指標正常，無需操作")
    print()
    print(grey("  資料來源：本地 cache/（上次執行 stock_assistant.py 的結果）"))
    print(grey("  更新資料：python stock_assistant.py --fresh"))
    print(grey("  回測優化：python monitor.py --backtest | --optimize"))
    print()


def _build_results_from_cache(holdings: list[dict]) -> tuple[list, float]:
    """從 cache 重組 results list，供 run_monitor() 使用。"""
    results = []
    for h in holdings:
        sym   = h["symbol"]
        scope = "competitors" if h.get("category") == "競品參考" else "holdings"
        fund  = load_fund(sym, scope)
        tech  = load_tech(sym, scope)
        results.append({
            "stock_info":     {"symbol": sym, "shares": h["shares"], "cost_basis": h["cost"], "category": h.get("category", "")},
            "stock_data":     {"fundamental": fund, "technical": tech},
            "analysis_result": {"recommendation": fund.get("recommendation", "")},
            "news":           [],
        })
    return results, 0.0


def _build_allocation_from_cache(holdings, results, mon_cfg) -> dict:
    """建構 allocation dict，提供 cash_pct 給現金監測規則。"""
    # 嘗試從 config/holdings.csv 讀取現金
    cash = 0.0
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                sym = (row.get("symbol") or "").strip().upper()
                if sym == "CASH":
                    shares = float(row.get("shares") or 0)
                    cost   = float(row.get("cost_basis") or row.get("price") or 0)
                    cash  += (shares * cost) if shares else cost
    except Exception:
        pass

    positions = []
    total_mv = cash
    for r in results:
        si = r["stock_info"]
        fund = r["stock_data"]["fundamental"]
        price = r["stock_data"]["technical"].get("current_price") or fund.get("current_price")
        mv = (price or 0) * si["shares"]
        total_mv += mv
        pnl = (price - si["cost_basis"]) * si["shares"] if price else 0
        pnl_pct = ((price - si["cost_basis"]) / si["cost_basis"] * 100) if price and si["cost_basis"] else 0
        positions.append({
            "symbol": si["symbol"],
            "shares": si["shares"],
            "cost_basis": si["cost_basis"],
            "cost_total": si["cost_basis"] * si["shares"],
            "market_value": mv,
            "current_price": price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "alloc_pct": 0,
            "category": si.get("category", ""),
        })

    for p in positions:
        p["alloc_pct"] = p["market_value"] / total_mv * 100 if total_mv > 0 else 0

    return {
        "total_value": total_mv,
        "total_cost":  sum(p["cost_total"] for p in positions) + cash,
        "total_pnl":   sum(p["pnl"] for p in positions),
        "cash":        cash,
        "cash_pct":    cash / total_mv * 100 if total_mv > 0 else 0,
        "options_value": 0,
        "options_pct":   0,
        "positions":   [p for p in positions if p["market_value"] > 0],
    }


def _run_json():
    """輸出完整 JSON（供外部程式串接）。"""
    from monitor import run_monitor
    from monitor.config import load_monitor_config
    holdings   = load_holdings()
    candidates = load_candidates()
    mon_cfg    = load_monitor_config()
    results, _ = _build_results_from_cache(holdings)
    allocation = _build_allocation_from_cache(holdings, results, mon_cfg)
    alerts_data = run_monitor(results, allocation, candidates, mon_cfg)
    print(json.dumps(alerts_data, ensure_ascii=False, indent=2))


def _run_backtest(forward_days=20):
    """執行回測，輸出規則準確率報告。"""
    from monitor.backtest import run_backtest, print_backtest_report
    report = run_backtest(ARCHIVE_DIR, forward_days=forward_days, verbose=True)
    print_backtest_report(report)


def _run_optimize(dry_run=True, forward_days=20):
    """執行優化，找最佳閾值 + 評分權重。"""
    from monitor.optimizer import run_optimization
    run_optimization(
        archive_dir=ARCHIVE_DIR,
        forward_days=forward_days,
        dry_run=dry_run,
        verbose=True,
    )


# ─── 入口 ────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    # 解析 --days
    forward_days = 20
    if "--days" in args:
        try:
            forward_days = int(args[args.index("--days") + 1])
        except (ValueError, IndexError):
            pass

    if "--json" in args:
        _run_json()
    elif "--backtest" in args:
        _run_backtest(forward_days=forward_days)
    elif "--optimize" in args:
        dry_run = "--dry-run" not in args
        # 如果明確指定 --dry-run，dry_run=True；否則預設也是 dry_run=True 除非加 --apply
        dry_run = "--apply" not in args
        _run_optimize(dry_run=dry_run, forward_days=forward_days)
    else:
        _run_terminal(
            brief=("--brief" in args),
            candidates_only=("--candidates" in args),
        )
