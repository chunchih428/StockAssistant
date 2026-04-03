"""
monitor/backtest.py — 回測引擎

從 archive/index_YYYYMMDD.html 萃取歷史評分快照，
搭配 yfinance 抓取同期股價，模擬各警示規則的預測準確率。

Usage（透過 monitor.py CLI）:
    python monitor.py --backtest [--days 20]
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ─── 資料結構 ─────────────────────────────────────────────────
@dataclass
class SnapshotRecord:
    date:        str          # YYYY-MM-DD（快照日期）
    symbol:      str
    fund_score:  float | None
    tech_score:  float | None
    risk_score:  float | None
    trend:       str
    rsi:         float | None
    price:       float | None
    pnl_pct:     float | None
    alloc_pct:   float | None
    recommendation: str


@dataclass
class RuleResult:
    """單筆快照套用某規則後的結果。"""
    date:         str
    symbol:       str
    signal:       str          # ADD / REDUCE / CLOSE / WATCH / HOLD
    triggered:    bool
    forward_return: float | None   # forward N-day 報酬（%）


@dataclass
class RulePerformance:
    rule_id:      str
    total_signals: int
    add_count:    int
    reduce_count: int
    add_avg_return:    float | None
    reduce_avg_return: float | None
    add_accuracy:      float | None   # ADD後漲的比例
    reduce_accuracy:   float | None   # REDUCE後跌的比例
    threshold_value:   Any            # 觸發此結果時使用的閾值


# ─── 萃取歷史快照 ────────────────────────────────────────────
_DATA_PATTERN = re.compile(r"const\s+D\s*=\s*(\{.*?\});?\s*\n", re.DOTALL)


def load_archive_snapshots(archive_dir: Path | str) -> list[SnapshotRecord]:
    """
    掃描 archive/index_YYYYMMDD.html，萃取每個快照的各股評分資料。
    回傳 SnapshotRecord 清單，按日期排序。
    """
    archive_dir = Path(archive_dir)
    if not archive_dir.exists():
        return []

    records: list[SnapshotRecord] = []
    html_files = sorted(archive_dir.glob("index_????????.html"))

    for html_file in html_files:
        date_str = _extract_date(html_file.name)
        if not date_str:
            continue

        try:
            content = html_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        data = _extract_json_from_html(content)
        if not data:
            continue

        stocks = data.get("stocks", [])
        alloc = data.get("allocation", {})
        alloc_map = {p["symbol"]: p.get("alloc_pct", 0)
                     for p in alloc.get("positions", []) if p.get("symbol")}

        for s in stocks:
            sym = s.get("symbol", "")
            shares = s.get("shares", 0) or 0
            if not sym or shares <= 0:
                continue  # 只記錄有持倉的股票

            fund = s.get("fundamental") or {}
            tech = s.get("technical")   or {}

            records.append(SnapshotRecord(
                date=date_str,
                symbol=sym,
                fund_score=fund.get("fund_score"),
                tech_score=tech.get("tech_score"),
                risk_score=tech.get("risk_score"),
                trend=tech.get("trend_status") or "UNKNOWN",
                rsi=tech.get("rsi"),
                price=s.get("price") or tech.get("current_price"),
                pnl_pct=s.get("pnl_pct"),
                alloc_pct=alloc_map.get(sym),
                recommendation=s.get("recommendation") or "",
            ))

    records.sort(key=lambda r: r.date)
    return records


def _extract_date(filename: str) -> str | None:
    """從 index_YYYYMMDD.html 提取 YYYY-MM-DD。"""
    m = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _extract_json_from_html(content: str) -> dict | None:
    """從 HTML 中提取 const D={...} 的 JSON。"""
    m = _DATA_PATTERN.search(content)
    if not m:
        # 試備用：尋找 __DATA_JSON__ 已替換的版本
        alt = re.search(r"const D=(\{.*?\});", content, re.DOTALL)
        if not alt:
            return None
        raw = alt.group(1)
    else:
        raw = m.group(1)
    try:
        return json.loads(raw)
    except Exception:
        return None


# ─── 抓取 forward return ────────────────────────────────────
def fetch_forward_returns(
    snapshots: list[SnapshotRecord],
    forward_days: int = 20,
) -> dict[tuple[str, str], float]:
    """
    批量抓取各 (date, symbol) 的 forward N-day 報酬（%）。
    回傳 {(date, symbol): return_pct}。
    利用 yfinance，按 symbol 分組批次下載以提升效率。
    """
    try:
        import yfinance as yf
    except ImportError:
        print("  [Backtest] 缺少 yfinance，無法計算 forward return")
        return {}

    # 按 symbol 分組，找出需要的日期範圍
    from collections import defaultdict
    sym_dates: dict[str, list[str]] = defaultdict(list)
    for rec in snapshots:
        sym_dates[rec.symbol].append(rec.date)

    result: dict[tuple[str, str], float] = {}

    for sym, dates in sym_dates.items():
        min_date = min(dates)
        # 多抓 forward_days*2 個日曆日（考慮假日）
        end_dt = (datetime.strptime(max(dates), "%Y-%m-%d")
                  + timedelta(days=forward_days * 2)).strftime("%Y-%m-%d")
        try:
            hist = yf.download(sym, start=min_date, end=end_dt,
                               progress=False, auto_adjust=True)
            if hist is None or hist.empty:
                continue
            close = hist["Close"].dropna()
        except Exception:
            continue

        for date_str in dates:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                # 找當日或之後最近的交易日收盤價
                future_dt = dt + timedelta(days=forward_days)
                # 取目標日期最近的交易日
                avail = close.index[close.index >= dt.strftime("%Y-%m-%d")]
                fut_avail = close.index[close.index >= future_dt.strftime("%Y-%m-%d")]
                if len(avail) == 0 or len(fut_avail) == 0:
                    continue
                p0 = float(close[avail[0]])
                p1 = float(close[fut_avail[0]])
                if p0 > 0:
                    result[(date_str, sym)] = round((p1 - p0) / p0 * 100, 2)
            except Exception:
                continue

    return result


# ─── 模擬單條規則表現 ────────────────────────────────────────
def simulate_rule(
    snapshots: list[SnapshotRecord],
    forward_returns: dict[tuple[str, str], float],
    rule_id: str,
    threshold_fn,          # callable(rec: SnapshotRecord) -> signal_level str | None
    threshold_value: Any = None,
) -> RulePerformance:
    """
    對每筆快照套用 threshold_fn，收集信號，對應 forward return，
    計算規則的準確率與平均報酬。
    """
    add_returns, reduce_returns = [], []

    for rec in snapshots:
        signal = threshold_fn(rec)
        fwd = forward_returns.get((rec.date, rec.symbol))
        if fwd is None:
            continue

        if signal == "ADD":
            add_returns.append(fwd)
        elif signal in ("REDUCE", "CLOSE"):
            reduce_returns.append(fwd)

    def _avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else None

    def _accuracy(lst, condition):
        if not lst:
            return None
        return round(sum(1 for x in lst if condition(x)) / len(lst) * 100, 1)

    return RulePerformance(
        rule_id=rule_id,
        total_signals=len(add_returns) + len(reduce_returns),
        add_count=len(add_returns),
        reduce_count=len(reduce_returns),
        add_avg_return=_avg(add_returns),
        reduce_avg_return=_avg(reduce_returns),
        add_accuracy=_accuracy(add_returns, lambda x: x > 0),
        reduce_accuracy=_accuracy(reduce_returns, lambda x: x < 0),
        threshold_value=threshold_value,
    )


# ─── 主回測入口 ──────────────────────────────────────────────
def run_backtest(
    archive_dir: Path | str,
    forward_days: int = 20,
    verbose: bool = True,
) -> dict:
    """
    主回測函式，回傳結構化報告 dict。

    Returns
    -------
    {
        "snapshots_count": int,
        "date_range": [start, end],
        "forward_days": int,
        "rules": {rule_id: RulePerformance.__dict__, ...},
    }
    """
    archive_dir = Path(archive_dir)
    snapshots = load_archive_snapshots(archive_dir)

    if len(snapshots) < 5:
        return {
            "error": f"快照數量不足（目前 {len(snapshots)} 個），建議累積至少 10 個後再回測",
            "snapshots_count": len(snapshots),
        }

    if verbose:
        dates = sorted({r.date for r in snapshots})
        print(f"\n  [Backtest] 快照 {len(snapshots)} 筆 / {len(dates)} 個日期 "
              f"（{dates[0]} ~ {dates[-1]}）")
        print(f"  [Backtest] 抓取 forward {forward_days}d 報酬中...")

    fwd_returns = fetch_forward_returns(snapshots, forward_days)

    if verbose:
        print(f"  [Backtest] 取得 {len(fwd_returns)} 筆 forward return")

    # ── 定義要測試的規則與閾值函式 ──────────────────────────
    rule_specs = _build_rule_specs()
    rule_results = {}

    for rule_id, fn, val in rule_specs:
        perf = simulate_rule(snapshots, fwd_returns, rule_id, fn, val)
        rule_results[rule_id] = {
            "rule_id":          perf.rule_id,
            "total_signals":    perf.total_signals,
            "add_count":        perf.add_count,
            "reduce_count":     perf.reduce_count,
            "add_avg_return":   perf.add_avg_return,
            "reduce_avg_return": perf.reduce_avg_return,
            "add_accuracy":     perf.add_accuracy,
            "reduce_accuracy":  perf.reduce_accuracy,
            "threshold_value":  perf.threshold_value,
        }

    dates = sorted({r.date for r in snapshots})
    return {
        "snapshots_count": len(snapshots),
        "date_range": [dates[0], dates[-1]] if dates else [None, None],
        "forward_days": forward_days,
        "rules": rule_results,
    }


def _build_rule_specs() -> list[tuple[str, Any, Any]]:
    """
    回傳 [(rule_id, threshold_fn, threshold_value), ...]
    每個 threshold_fn(rec: SnapshotRecord) -> "ADD" | "REDUCE" | None
    """
    specs = []

    # tech_score_reduce 系列
    for thr in [35, 40, 45, 50]:
        def make_fn(t):
            def fn(rec: SnapshotRecord):
                ts = rec.tech_score
                if ts is not None and ts < t and rec.trend not in ("DOWNTREND", "BREAKDOWN"):
                    return "REDUCE"
                return None
            return fn
        specs.append((f"tech_weak_{thr}", make_fn(thr), thr))

    # fund_score_add 系列
    for thr in [60, 65, 70, 75]:
        def make_fn(t):
            def fn(rec: SnapshotRecord):
                fs = rec.fund_score
                ts = rec.tech_score
                if (fs or 0) >= t and (ts or 0) >= 55 and rec.trend in ("UPTREND", "RECOVERY", "OVERSOLD_UPTREND"):
                    return "ADD"
                return None
            return fn
        specs.append((f"add_signal_fund{thr}", make_fn(thr), thr))

    # stop_loss 系列
    for thr in [-15, -18, -20, -25]:
        def make_fn(t):
            def fn(rec: SnapshotRecord):
                if rec.pnl_pct is not None and rec.pnl_pct <= t:
                    return "REDUCE"
                return None
            return fn
        specs.append((f"stop_loss_{abs(thr)}pct", make_fn(thr), thr))

    # rsi_overbought
    for thr in [70, 75, 80]:
        def make_fn(t):
            def fn(rec: SnapshotRecord):
                if rec.rsi is not None and rec.rsi > t:
                    return "REDUCE"
                return None
            return fn
        specs.append((f"rsi_overbought_{thr}", make_fn(thr), thr))

    # oversold_add（超賣反彈加碼）
    for thr in [55, 60, 65]:
        def make_fn(t):
            def fn(rec: SnapshotRecord):
                if (rec.trend == "OVERSOLD_UPTREND" and (rec.fund_score or 0) >= t
                        and (rec.pnl_pct or 0) < -3):
                    return "ADD"
                return None
            return fn
        specs.append((f"oversold_add_fund{thr}", make_fn(thr), thr))

    return specs


# ─── 格式化輸出 ──────────────────────────────────────────────
def print_backtest_report(report: dict):
    """把 run_backtest() 的結果格式化輸出到終端。"""
    if "error" in report:
        print(f"\n  ⚠️  {report['error']}")
        return

    print(f"\n{'═'*70}")
    print(f"  📊 回測報告  |  快照 {report['snapshots_count']} 筆  "
          f"（{report['date_range'][0]} ~ {report['date_range'][1]}）  "
          f"|  forward {report['forward_days']}d")
    print(f"{'─'*70}")
    print(f"  {'規則':<30} {'信號數':>5}  {'ADD準確率':>8}  {'REDUCE準確率':>10}  "
          f"{'ADD avg%':>8}  {'REDUCE avg%':>10}")
    print(f"{'─'*70}")

    rules = report.get("rules", {})
    # 按 ADD準確率 + REDUCE準確率 綜合排序
    sorted_rules = sorted(
        rules.values(),
        key=lambda x: (
            (x.get("add_accuracy") or 0) * 0.5 +
            (x.get("reduce_accuracy") or 0) * 0.5
        ),
        reverse=True,
    )

    for r in sorted_rules:
        if r["total_signals"] == 0:
            continue
        add_acc   = f"{r['add_accuracy']:.1f}%" if r['add_accuracy'] is not None else "—"
        red_acc   = f"{r['reduce_accuracy']:.1f}%" if r['reduce_accuracy'] is not None else "—"
        add_ret   = f"+{r['add_avg_return']:.1f}%" if r['add_avg_return'] and r['add_avg_return'] >= 0 else (f"{r['add_avg_return']:.1f}%" if r['add_avg_return'] else "—")
        red_ret   = f"{r['reduce_avg_return']:.1f}%" if r['reduce_avg_return'] is not None else "—"
        print(
            f"  {r['rule_id']:<30} {r['total_signals']:>5}  {add_acc:>8}  "
            f"{red_acc:>10}  {add_ret:>8}  {red_ret:>10}"
        )

    print(f"{'═'*70}")
    print("  說明：ADD準確率 = 觸發加倉後股價上漲比例；REDUCE準確率 = 觸發減倉後股價下跌比例")
