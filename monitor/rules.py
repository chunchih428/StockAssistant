"""
monitor/rules.py — 可插拔規則引擎

每條規則是一個函式，透過 @register_rule 掛進 RULE_REGISTRY。
新增規則只需：
    @register_rule
    def my_new_rule(ctx: RuleContext) -> Alert | None:
        ...
"""
from __future__ import annotations
from dataclasses import dataclass, field

# ─── 警示等級常數 ──────────────────────────────────────────────
LEVEL_CLOSE  = 0   # 🔴 停損 / 平倉
LEVEL_REDUCE = 1   # 🟠 減倉
LEVEL_WATCH  = 2   # 🟡 觀察
LEVEL_ADD    = 3   # 💎 加倉機會
LEVEL_HOLD   = 4   # 🟢 持有

LEVEL_LABEL = {
    LEVEL_CLOSE:  "CLOSE",
    LEVEL_REDUCE: "REDUCE",
    LEVEL_WATCH:  "WATCH",
    LEVEL_ADD:    "ADD",
    LEVEL_HOLD:   "HOLD",
}

LEVEL_ICON = {
    LEVEL_CLOSE:  "🔴",
    LEVEL_REDUCE: "🟠",
    LEVEL_WATCH:  "🟡",
    LEVEL_ADD:    "💎",
    LEVEL_HOLD:   "🟢",
}

LEVEL_COLOR = {
    LEVEL_CLOSE:  "#dc2626",
    LEVEL_REDUCE: "#f97316",
    LEVEL_WATCH:  "#eab308",
    LEVEL_ADD:    "#7c3aed",
    LEVEL_HOLD:   "#059669",
}


@dataclass
class Alert:
    level:   int
    rule:    str   # rule id，方便日後過濾 / 回測
    msg:     str   # 顯示給用戶的說明文字
    detail:  dict  = field(default_factory=dict)  # 保留數值，供回測用

    def to_dict(self) -> dict:
        return {
            "level":       self.level,
            "level_label": LEVEL_LABEL.get(self.level, ""),
            "level_icon":  LEVEL_ICON.get(self.level, ""),
            "level_color": LEVEL_COLOR.get(self.level, "#94a3b8"),
            "rule":        self.rule,
            "msg":         self.msg,
        }


@dataclass
class RuleContext:
    """傳入每條規則的上下文物件，統一介面。"""
    symbol:         str
    fund:           dict          # fundamental cache
    tech:           dict          # technical cache
    alloc_pct:      float | None  # 佔組合比例（%）
    pnl_pct:        float | None  # 持倉損益（%）
    recommendation: str           # AI 建議 (add/reduce/close/hold/unknown)
    thresholds:     dict          # 已套用 override 的有效閾值


# ─── 規則 Registry ────────────────────────────────────────────
RULE_REGISTRY: list = []

def register_rule(fn):
    """裝飾器：把函式加入全域規則清單。"""
    RULE_REGISTRY.append(fn)
    return fn


# ═══════════════════════════════════════════════════════════════
#  🔴 LEVEL_CLOSE 規則
# ═══════════════════════════════════════════════════════════════

@register_rule
def rule_stop_loss(ctx: RuleContext) -> Alert | None:
    limit = ctx.thresholds.get("stop_loss_pct", -20)
    if ctx.pnl_pct is not None and ctx.pnl_pct <= limit:
        return Alert(LEVEL_CLOSE, "stop_loss",
                     f"虧損 {ctx.pnl_pct:.1f}%，觸及停損線（{limit}%），建議評估平倉",
                     {"pnl_pct": ctx.pnl_pct, "limit": limit})


@register_rule
def rule_fund_collapse(ctx: RuleContext) -> Alert | None:
    fs = ctx.fund.get("fund_score")
    limit = ctx.thresholds.get("fund_score_close", 30)
    if fs is not None and fs < limit:
        return Alert(LEVEL_CLOSE, "fund_collapse",
                     f"基本面崩壞（評分 {int(fs)} < {limit}），建議全面退出",
                     {"fund_score": fs, "limit": limit})


@register_rule
def rule_breakdown(ctx: RuleContext) -> Alert | None:
    trend = ctx.tech.get("trend_status", "")
    ts = ctx.tech.get("tech_score")
    if trend == "BREAKDOWN" and ts is not None and ts < 40:
        return Alert(LEVEL_CLOSE, "breakdown",
                     f"技術崩跌（BREAKDOWN）且技術分 {int(ts)}，高風險",
                     {"trend": trend, "tech_score": ts})


@register_rule
def rule_ai_close(ctx: RuleContext) -> Alert | None:
    if ctx.recommendation == "close":
        return Alert(LEVEL_CLOSE, "ai_close", "AI 分析建議平倉")


# ═══════════════════════════════════════════════════════════════
#  🟠 LEVEL_REDUCE 規則
# ═══════════════════════════════════════════════════════════════

@register_rule
def rule_concentration(ctx: RuleContext) -> Alert | None:
    limit = ctx.thresholds.get("max_single_alloc_pct", 30)
    if ctx.alloc_pct is not None and ctx.alloc_pct > limit:
        return Alert(LEVEL_REDUCE, "concentration",
                     f"單一持倉佔比 {ctx.alloc_pct:.1f}%（>{limit}%），集中度過高，建議分批減倉",
                     {"alloc_pct": ctx.alloc_pct, "limit": limit})


@register_rule
def rule_take_profit(ctx: RuleContext) -> Alert | None:
    limit = ctx.thresholds.get("take_profit_pct", 60)
    if ctx.pnl_pct is not None and ctx.pnl_pct >= limit:
        return Alert(LEVEL_REDUCE, "take_profit",
                     f"已獲利 {ctx.pnl_pct:.1f}%（>{limit}%），可考慮鎖定部分利潤",
                     {"pnl_pct": ctx.pnl_pct, "limit": limit})


@register_rule
def rule_warn_loss(ctx: RuleContext) -> Alert | None:
    stop = ctx.thresholds.get("stop_loss_pct", -20)
    warn = ctx.thresholds.get("warn_loss_pct", -12)
    if ctx.pnl_pct is not None and stop < ctx.pnl_pct <= warn:
        return Alert(LEVEL_REDUCE, "warn_loss",
                     f"虧損 {ctx.pnl_pct:.1f}%，接近停損線（{stop}%），建議減少倉位",
                     {"pnl_pct": ctx.pnl_pct, "warn": warn, "stop": stop})


@register_rule
def rule_downtrend_tech(ctx: RuleContext) -> Alert | None:
    trend = ctx.tech.get("trend_status", "")
    ts = ctx.tech.get("tech_score")
    limit = ctx.thresholds.get("tech_score_reduce", 45)
    if trend == "DOWNTREND" and ts is not None and ts < limit:
        return Alert(LEVEL_REDUCE, "downtrend_tech",
                     f"下跌趨勢（DOWNTREND）且技術分 {int(ts)} < {limit}，建議降低暴露",
                     {"trend": trend, "tech_score": ts, "limit": limit})


@register_rule
def rule_high_risk(ctx: RuleContext) -> Alert | None:
    rs = ctx.tech.get("risk_score")
    limit = ctx.thresholds.get("risk_score_reduce", 30)
    if rs is not None and rs < limit:
        return Alert(LEVEL_REDUCE, "high_risk",
                     f"風險評分 {int(rs)} < {limit}（VaR / Sharpe / Sortino 均不理想），建議降低倉位",
                     {"risk_score": rs, "limit": limit})


@register_rule
def rule_ai_reduce(ctx: RuleContext) -> Alert | None:
    if ctx.recommendation == "reduce":
        return Alert(LEVEL_REDUCE, "ai_reduce", "AI 分析建議減倉")


# ═══════════════════════════════════════════════════════════════
#  🟡 LEVEL_WATCH 規則
# ═══════════════════════════════════════════════════════════════

@register_rule
def rule_rsi_overbought(ctx: RuleContext) -> Alert | None:
    rsi = ctx.tech.get("rsi")
    limit = ctx.thresholds.get("rsi_overbought", 75)
    if rsi is not None and rsi > limit:
        return Alert(LEVEL_WATCH, "rsi_overbought",
                     f"RSI = {rsi:.1f}（>{limit} 超買），短期可能回調，可設好停利點",
                     {"rsi": rsi, "limit": limit})


@register_rule
def rule_rsi_oversold_danger(ctx: RuleContext) -> Alert | None:
    """RSI 超賣但趨勢未翻多 → 可能繼續下跌，列為觀察。"""
    rsi = ctx.tech.get("rsi")
    trend = ctx.tech.get("trend_status", "")
    limit = ctx.thresholds.get("rsi_oversold", 28)
    if rsi is not None and rsi < limit and trend not in ("UPTREND", "OVERSOLD_UPTREND", "RECOVERY"):
        return Alert(LEVEL_WATCH, "rsi_oversold_danger",
                     f"RSI = {rsi:.1f}（<{limit} 超賣）且趨勢未翻多，小心繼續下跌",
                     {"rsi": rsi, "limit": limit, "trend": trend})


@register_rule
def rule_tech_weak(ctx: RuleContext) -> Alert | None:
    ts = ctx.tech.get("tech_score")
    limit = ctx.thresholds.get("tech_score_reduce", 45)
    trend = ctx.tech.get("trend_status", "")
    if ts is not None and ts < limit and trend not in ("DOWNTREND", "BREAKDOWN"):
        return Alert(LEVEL_WATCH, "tech_weak",
                     f"技術分走弱（{int(ts)} < {limit}），注意支撐位是否失守",
                     {"tech_score": ts, "limit": limit})


@register_rule
def rule_var_high(ctx: RuleContext) -> Alert | None:
    var_95 = ctx.tech.get("var_95")   # 已是 % 數值（負值）
    if var_95 is not None and var_95 < -5:
        return Alert(LEVEL_WATCH, "var_high",
                     f"1-Day VaR(95%) = {var_95:.2f}%（單日最大虧損風險偏高）",
                     {"var_95": var_95})


@register_rule
def rule_high_leverage(ctx: RuleContext) -> Alert | None:
    debt_eq = ctx.fund.get("debtToEquity")
    if debt_eq is not None and debt_eq > 3.0:
        return Alert(LEVEL_WATCH, "high_leverage",
                     f"負債/權益比 = {debt_eq:.1f}（>3），財務槓桿偏高",
                     {"debtToEquity": debt_eq})


@register_rule
def rule_rev_decline(ctx: RuleContext) -> Alert | None:
    rev_g = ctx.fund.get("revenueGrowth")
    if rev_g is not None and rev_g < -0.05:
        return Alert(LEVEL_WATCH, "rev_decline",
                     f"營收衰退 {rev_g * 100:.1f}%，留意基本面是否持續轉差",
                     {"revenueGrowth": rev_g})


# ═══════════════════════════════════════════════════════════════
#  💎 LEVEL_ADD 規則
# ═══════════════════════════════════════════════════════════════

@register_rule
def rule_add_signal(ctx: RuleContext) -> Alert | None:
    fs = ctx.fund.get("fund_score") or 0
    ts = ctx.tech.get("tech_score") or 0
    trend = ctx.tech.get("trend_status", "")
    fs_th = ctx.thresholds.get("fund_score_add", 70)
    ts_th = ctx.thresholds.get("tech_score_add", 58)
    max_alloc = ctx.thresholds.get("add_max_alloc_pct", 22)

    is_quality = fs >= fs_th
    is_tech_ok = ts >= ts_th
    is_upward  = trend in ("UPTREND", "RECOVERY", "OVERSOLD_UPTREND")
    not_full   = (ctx.alloc_pct or 100) < max_alloc

    if is_quality and is_tech_ok and is_upward and not_full:
        return Alert(LEVEL_ADD, "add_signal",
                     f"基本面 {int(fs)} ＋ 技術面 {int(ts)} ＋ {trend} → 可分批加碼",
                     {"fund_score": fs, "tech_score": ts, "trend": trend, "alloc_pct": ctx.alloc_pct})


@register_rule
def rule_oversold_add(ctx: RuleContext) -> Alert | None:
    trend = ctx.tech.get("trend_status", "")
    fs = ctx.fund.get("fund_score") or 0
    fs_th = max(ctx.thresholds.get("fund_score_add", 70) - 8, 55)  # 超賣加碼門檻稍低
    if trend == "OVERSOLD_UPTREND" and fs >= fs_th and (ctx.pnl_pct or 0) < -3:
        return Alert(LEVEL_ADD, "oversold_add",
                     f"超賣反彈且尚在成本線以下，可考慮分批加碼（基本面 {int(fs)}）",
                     {"fund_score": fs, "trend": trend, "pnl_pct": ctx.pnl_pct})


@register_rule
def rule_quality_dip(ctx: RuleContext) -> Alert | None:
    fs = ctx.fund.get("fund_score") or 0
    trend = ctx.tech.get("trend_status", "")
    fs_th = ctx.thresholds.get("fund_score_add", 70)
    if (ctx.pnl_pct or 0) < -8 and fs >= fs_th and trend == "CONSOLIDATION":
        return Alert(LEVEL_ADD, "quality_dip",
                     f"優質股回落 {ctx.pnl_pct:.1f}% 進入盤整，可留意加碼時機",
                     {"fund_score": fs, "pnl_pct": ctx.pnl_pct, "trend": trend})


@register_rule
def rule_ai_add(ctx: RuleContext) -> Alert | None:
    trend = ctx.tech.get("trend_status", "")
    if ctx.recommendation == "add" and trend in ("UPTREND", "RECOVERY", "OVERSOLD_UPTREND", "CONSOLIDATION"):
        return Alert(LEVEL_ADD, "ai_add",
                     f"AI 分析建議加倉（趨勢：{trend}）")


# ─── 執行所有規則 ──────────────────────────────────────────────
def run_all_rules(ctx: RuleContext) -> list[Alert]:
    """
    對 ctx 跑所有已註冊規則，回傳有觸發的 Alert 清單（依 level 排序）。
    若無任何觸發，回傳一個 HOLD Alert。
    """
    alerts = []
    for rule_fn in RULE_REGISTRY:
        try:
            result = rule_fn(ctx)
            if result is not None:
                alerts.append(result)
        except Exception as e:
            print(f"  [Monitor] 規則 {rule_fn.__name__} 執行錯誤：{e}")

    alerts.sort(key=lambda a: a.level)

    if not alerts:
        alerts.append(Alert(LEVEL_HOLD, "hold", "各項指標正常，維持現有倉位"))

    return alerts
