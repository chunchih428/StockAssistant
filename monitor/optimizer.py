"""
monitor/optimizer.py — 閾值 + 評分權重動態優化

從回測結果中找出最佳參數組合，自動更新 monitor_config.json。

Usage（透過 monitor.py CLI）:
    python monitor.py --optimize --dry-run    # 只印建議，不寫檔
    python monitor.py --optimize              # 更新 monitor_config.json
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .backtest import (
    load_archive_snapshots,
    fetch_forward_returns,
    simulate_rule,
    SnapshotRecord,
)
from .config import load_monitor_config, reload_monitor_config

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "monitor_config.json"
_HISTORY_PATH        = Path(__file__).resolve().parent.parent / "output" / "optimization_history.json"

# ─── 閾值參數搜尋空間 ────────────────────────────────────────
THRESHOLD_GRID = {
    "tech_score_reduce":    [35, 40, 45, 50],
    "tech_score_add":       [52, 55, 58, 62, 65],
    "fund_score_add":       [60, 65, 70, 75, 80],
    "fund_score_close":     [25, 30, 35],
    "stop_loss_pct":        [-15, -18, -20, -25],
    "take_profit_pct":      [50, 60, 70, 80],
    "rsi_overbought":       [70, 75, 80],
    "rsi_oversold":         [25, 28, 32],
    "add_max_alloc_pct":    [18, 22, 25],
    "min_cash_pct":         [3, 5, 8],
    "max_cash_pct":         [20, 25, 30],
    "warn_high_cash_pct":   [15, 18, 22],
}


def optimize_thresholds(
    snapshots: list[SnapshotRecord],
    forward_returns: dict[tuple[str, str], float],
    forward_days: int = 20,
) -> dict[str, Any]:
    """
    Grid search 找出讓「ADD信號平均報酬 - REDUCE信號平均報酬」最大的閾值組合。
    回傳建議的新 thresholds dict（只包含與現有設定不同的項目）。
    """
    best: dict[str, dict] = {}   # {param_name: {value, score, n_signals}}

    for param, candidates in THRESHOLD_GRID.items():
        fn_builder = _make_threshold_fn(param)
        if fn_builder is None:
            continue

        best_score = -999.0
        best_val = None
        best_n = 0

        for val in candidates:
            fn = fn_builder(val)
            perf = simulate_rule(snapshots, forward_returns, param, fn, val)

            # 目標函數：ADD準確率 × 0.5 + REDUCE準確率 × 0.5（各自有信號時才計）
            add_acc = perf.add_accuracy or 0
            red_acc = perf.reduce_accuracy or 0
            n = perf.total_signals

            if n < 3:   # 信號太少，不可信
                continue

            # 加權：有效信號數越多，分數越可信
            weight = min(n / 20, 1.0)
            score = (add_acc * 0.5 + red_acc * 0.5) * weight

            if score > best_score:
                best_score = score
                best_val   = val
                best_n     = n

        if best_val is not None:
            best[param] = {
                "value":    best_val,
                "score":    round(best_score, 2),
                "n_signals": best_n,
            }

    return best


def optimize_scoring_weights(
    snapshots: list[SnapshotRecord],
    forward_returns: dict[tuple[str, str], float],
) -> dict[str, Any]:
    """
    優化候選股綜合評分的子項比重：
    調整 fund/tech/risk 各佔多少比例，使「評分 vs forward return」相關性最高。
    回傳建議的 composite_for_candidates dict。
    """
    try:
        import numpy as np
    except ImportError:
        print("  [Optimizer] 需要 numpy 才能優化評分權重，略過")
        return {}

    # 收集 (composite_score, forward_return) 資料點
    weight_grid = [
        (wf, wt, wr)
        for wf in [0.3, 0.35, 0.4, 0.45, 0.5]
        for wt in [0.25, 0.3, 0.35, 0.4]
        for wr in [0.1, 0.15, 0.2, 0.25]
        if 0.85 <= wf + wt + wr <= 0.95   # 剩餘給 news_boost
    ]

    best_corr = -999.0
    best_weights = None

    for wf, wt, wr in weight_grid:
        scores, returns = [], []
        for rec in snapshots:
            fwd = forward_returns.get((rec.date, rec.symbol))
            if fwd is None:
                continue
            fs = rec.fund_score or 0
            ts = rec.tech_score or 0
            rs = rec.risk_score or 0
            comp = fs * wf + ts * wt + rs * wr
            scores.append(comp)
            returns.append(fwd)

        if len(scores) < 10:
            continue

        try:
            corr = float(np.corrcoef(scores, returns)[0, 1])
            if corr > best_corr:
                best_corr = corr
                best_weights = (wf, wt, wr)
        except Exception:
            continue

    if best_weights is None:
        return {}

    wf, wt, wr = best_weights
    wn = round(1.0 - wf - wt - wr, 2)

    return {
        "fund_score": wf,
        "tech_score": wt,
        "risk_score": wr,
        "news_boost": max(wn, 0.01),
        "_corr":      round(best_corr, 4),
    }


# ─── 主優化入口 ──────────────────────────────────────────────
def run_optimization(
    archive_dir: Path | str,
    config_path: Path | str | None = None,
    forward_days: int = 20,
    dry_run: bool = True,
    verbose: bool = True,
) -> dict:
    """
    完整優化流程：
    1. 載入歷史快照
    2. 抓取 forward return
    3. 優化閾值
    4. 優化評分權重
    5. （dry_run=False 時）寫回 monitor_config.json

    回傳建議的更新內容。
    """
    archive_dir = Path(archive_dir)
    config_path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    snapshots = load_archive_snapshots(archive_dir)
    if len(snapshots) < 10:
        return {"error": f"快照不足（{len(snapshots)} 個），建議至少 10 個後再優化"}

    if verbose:
        dates = sorted({r.date for r in snapshots})
        print(f"\n  [Optimizer] 快照 {len(snapshots)} 筆 / {len(dates)} 個日期")
        print(f"  [Optimizer] 抓取 forward {forward_days}d 報酬...")

    fwd_returns = fetch_forward_returns(snapshots, forward_days)
    if verbose:
        print(f"  [Optimizer] 取得 {len(fwd_returns)} 筆 forward return，開始 grid search...")

    # 優化閾值
    best_thresholds = optimize_thresholds(snapshots, fwd_returns, forward_days)

    # 優化評分權重
    best_weights = optimize_scoring_weights(snapshots, fwd_returns)

    # 載入現有設定
    current_cfg = load_monitor_config(config_path)
    current_thresholds = current_cfg.get("thresholds", {})
    current_weights    = current_cfg.get("scoring_weights", {}).get("composite_for_candidates", {})

    # 比較差異
    threshold_changes = {}
    for param, info in best_thresholds.items():
        old_val = current_thresholds.get(param)
        new_val = info["value"]
        if old_val != new_val:
            threshold_changes[param] = {"before": old_val, "after": new_val, "n_signals": info["n_signals"]}

    weight_changes = {}
    if best_weights:
        for k in ("fund_score", "tech_score", "risk_score", "news_boost"):
            old = current_weights.get(k)
            new = best_weights.get(k)
            if new is not None and old != new:
                weight_changes[k] = {"before": old, "after": new}

    suggestion = {
        "threshold_changes": threshold_changes,
        "weight_changes":    weight_changes,
        "forward_days":      forward_days,
        "snapshots_count":   len(snapshots),
        "dry_run":           dry_run,
    }

    # 格式化輸出
    if verbose:
        _print_optimization_report(suggestion, current_cfg)

    # 寫回 config
    if not dry_run and (threshold_changes or weight_changes):
        _apply_changes(config_path, current_cfg, threshold_changes, weight_changes, suggestion)
        if verbose:
            print(f"\n  ✅ monitor_config.json 已更新（備份於 output/optimization_history.json）")
    elif not dry_run:
        if verbose:
            print("\n  ℹ️  無需更新，當前設定已是最優")
    else:
        if verbose:
            print("\n  （dry-run 模式，未實際修改設定）")
            print("  執行 python monitor.py --optimize 以套用建議")

    return suggestion


def _apply_changes(
    config_path: Path,
    current_cfg: dict,
    threshold_changes: dict,
    weight_changes: dict,
    suggestion: dict,
):
    """把優化結果寫回 monitor_config.json，並備份歷史記錄。"""
    # 備份歷史
    _save_history(suggestion, current_cfg)

    # 更新閾值
    for param, info in threshold_changes.items():
        current_cfg.setdefault("thresholds", {})[param] = info["after"]

    # 更新評分權重
    if weight_changes:
        sc = current_cfg.setdefault("scoring_weights", {})
        comp = sc.setdefault("composite_for_candidates", {})
        for k, info in weight_changes.items():
            comp[k] = info["after"]

    # 更新元資料
    current_cfg["_version"] = current_cfg.get("_version", 0) + 1
    current_cfg["_last_optimized"] = datetime.now().strftime("%Y-%m-%d")

    config_path.write_text(
        json.dumps(current_cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 讓 config 模組重新讀取
    reload_monitor_config(config_path)


def _save_history(suggestion: dict, old_cfg: dict):
    """追加一筆優化記錄到 output/optimization_history.json。"""
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    history = []
    if _HISTORY_PATH.exists():
        try:
            history = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []

    record = {
        "optimized_at": datetime.now().isoformat(),
        "suggestion":   suggestion,
        "old_thresholds": old_cfg.get("thresholds", {}),
    }
    history.append(record)

    # 只保留最近 90 筆
    if len(history) > 90:
        history = history[-90:]

    _HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _print_optimization_report(suggestion: dict, current_cfg: dict):
    print(f"\n{'═'*65}")
    print(f"  🔧 優化建議報告  |  forward {suggestion['forward_days']}d  "
          f"|  快照 {suggestion['snapshots_count']} 筆")
    print(f"{'─'*65}")

    tc = suggestion.get("threshold_changes", {})
    wc = suggestion.get("weight_changes", {})

    if not tc and not wc:
        print("  ✅ 當前設定已是最優，無需調整")
    else:
        if tc:
            print("\n  📌 警示閾值調整建議：")
            for param, info in tc.items():
                arrow = "→"
                print(f"    {param:<30} {info['before']} {arrow} {info['after']}  "
                      f"（回測信號 {info['n_signals']} 次）")
        if wc:
            print("\n  📌 候選股評分權重調整建議：")
            for k, info in wc.items():
                print(f"    composite_for_candidates.{k:<15} {info['before']} → {info['after']}")

    print(f"{'═'*65}")


# ─── 工具函式：建立閾值函式 ────────────────────────────────
def _make_threshold_fn(param: str):
    """根據參數名稱回傳對應的 (threshold_value) -> signal_fn 建構器。"""
    if param == "tech_score_reduce":
        def builder(val):
            def fn(rec): return "REDUCE" if (rec.tech_score or 100) < val and rec.trend not in ("DOWNTREND","BREAKDOWN") else None
            return fn
        return builder

    if param == "tech_score_add":
        def builder(val):
            def fn(rec): return "ADD" if (rec.tech_score or 0) >= val and (rec.fund_score or 0) >= 60 and rec.trend in ("UPTREND","RECOVERY","OVERSOLD_UPTREND") else None
            return fn
        return builder

    if param == "fund_score_add":
        def builder(val):
            def fn(rec): return "ADD" if (rec.fund_score or 0) >= val and (rec.tech_score or 0) >= 55 and rec.trend in ("UPTREND","RECOVERY","OVERSOLD_UPTREND") else None
            return fn
        return builder

    if param == "fund_score_close":
        def builder(val):
            def fn(rec): return "REDUCE" if (rec.fund_score or 100) < val else None
            return fn
        return builder

    if param == "stop_loss_pct":
        def builder(val):
            def fn(rec): return "REDUCE" if rec.pnl_pct is not None and rec.pnl_pct <= val else None
            return fn
        return builder

    if param == "take_profit_pct":
        def builder(val):
            def fn(rec): return "REDUCE" if rec.pnl_pct is not None and rec.pnl_pct >= val else None
            return fn
        return builder

    if param == "rsi_overbought":
        def builder(val):
            def fn(rec): return "REDUCE" if rec.rsi is not None and rec.rsi > val else None
            return fn
        return builder

    if param == "rsi_oversold":
        def builder(val):
            def fn(rec): return "ADD" if rec.rsi is not None and rec.rsi < val and rec.trend in ("OVERSOLD_UPTREND","RECOVERY") else None
            return fn
        return builder

    if param == "add_max_alloc_pct":
        def builder(val):
            def fn(rec): return "ADD" if (rec.alloc_pct or 100) < val and (rec.fund_score or 0) >= 65 and rec.trend in ("UPTREND","RECOVERY") else None
            return fn
        return builder

    return None
