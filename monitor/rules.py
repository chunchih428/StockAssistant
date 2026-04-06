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
    LEVEL_CLOSE:  "🚨 停損",
    LEVEL_REDUCE: "⚠️ 減倉",
    LEVEL_WATCH:  "👀 觀察",
    LEVEL_ADD:    "💎 加倉機會",
    LEVEL_HOLD:   "✅ 持有",
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
    symbol:                 str
    fund:                   dict          # fundamental cache
    tech:                   dict          # technical cache
    alloc_pct:              float | None  # 佔組合比例（%）
    pnl_pct:                float | None  # 持倉損益（%，從成本價計算）
    recommendation:         str           # AI 建議 (add/reduce/close/hold/unknown)
    thresholds:             dict          # 已套用 override 的有效閾值
    sector_alloc_pct:       float | None = None   # 同產業合計佔比（%）
    is_systemic_correction: bool = False          # 是否處於系統性修正


# ─── 規則 Registry ────────────────────────────────────────────
RULE_REGISTRY: list = []

# 系統性修正過濾：這些規則 ID 在系統性修正時自動降一等級
DRAWDOWN_BASED_RULES = frozenset({
    "drawdown_watch",
    "drawdown_fund_mismatch",
    "drawdown_cost_weak",
})

def register_rule(fn):
    """裝飾器：把函式加入全域規則清單。"""
    RULE_REGISTRY.append(fn)
    return fn


# ─── 輔助：計算距 52w 高點回撤 % ──────────────────────────────
def _drawdown_from_high(ctx: RuleContext) -> float | None:
    """從技術面 cache 計算當前價格距 52 週高點的回撤百分比（負值）。"""
    price   = ctx.tech.get("current_price")
    high_52 = ctx.tech.get("high_52w")
    if price and high_52 and high_52 > 0:
        return (price - high_52) / high_52 * 100
    return None


# ═══════════════════════════════════════════════════════════════
#  🔴 LEVEL_CLOSE 規則
# ═══════════════════════════════════════════════════════════════

@register_rule
def rule_stop_loss_cost(ctx: RuleContext) -> Alert | None:
    """v3：從持有成本計算停損，門檻 -25%（唯你真正虧損才觸發，取代 v2 的 52w 回撤停損）。"""
    limit = ctx.thresholds.get("stop_loss_cost_pct", -25)
    if ctx.pnl_pct is not None and ctx.pnl_pct <= limit:
        return Alert(LEVEL_CLOSE, "stop_loss_cost",
                     f"從成本虧損 {ctx.pnl_pct:.1f}%，觸及停損線（{limit}%），建議評估平倉",
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
def rule_sector_concentration(ctx: RuleContext) -> Alert | None:
    """v2 新增：同產業合計佔比過高。"""
    limit = ctx.thresholds.get("max_sector_alloc_pct", 50)
    if ctx.sector_alloc_pct is not None and ctx.sector_alloc_pct > limit:
        return Alert(LEVEL_REDUCE, "sector_concentration",
                     f"同產業持倉合計佔比 {ctx.sector_alloc_pct:.1f}%（>{limit}%），產業集中度過高，建議分散配置",
                     {"sector_alloc_pct": ctx.sector_alloc_pct, "limit": limit})


@register_rule
def rule_take_profit(ctx: RuleContext) -> Alert | None:
    """v2：門檻從 +60% 提高至 +100%，且趨勢非 UPTREND 才觸發（避免強勢中被迫減碼）。"""
    limit = ctx.thresholds.get("take_profit_pct", 100)
    trend = ctx.tech.get("trend_status", "")
    if ctx.pnl_pct is not None and ctx.pnl_pct >= limit and trend != "UPTREND":
        return Alert(LEVEL_REDUCE, "take_profit",
                     f"已獲利 {ctx.pnl_pct:.1f}%（>{limit}%）且趨勢非 UPTREND，可考慮鎖定部分利潤",
                     {"pnl_pct": ctx.pnl_pct, "limit": limit, "trend": trend})


@register_rule
def rule_warn_loss_heavy(ctx: RuleContext) -> Alert | None:
    """v3：改為持有成本損益計算，-15% ～ -25%（建議減倉 1/2）。"""
    stop  = ctx.thresholds.get("stop_loss_cost_pct", -25)
    heavy = ctx.thresholds.get("warn_loss_heavy_pct", -15)
    if ctx.pnl_pct is not None and stop < ctx.pnl_pct <= heavy:
        return Alert(LEVEL_REDUCE, "warn_loss_heavy",
                     f"從成本虧損 {ctx.pnl_pct:.1f}%（{heavy}% ～ {stop}%），建議減倉 1/2",
                     {"pnl_pct": ctx.pnl_pct, "heavy": heavy, "stop": stop})


@register_rule
def rule_warn_loss(ctx: RuleContext) -> Alert | None:
    """v3：改為持有成本損益計算，-8% ～ -15%（建議減倉 1/4）。"""
    heavy = ctx.thresholds.get("warn_loss_heavy_pct", -15)
    light = ctx.thresholds.get("warn_loss_light_pct", -8)
    if ctx.pnl_pct is not None and heavy < ctx.pnl_pct <= light:
        return Alert(LEVEL_REDUCE, "warn_loss",
                     f"從成本虧損 {ctx.pnl_pct:.1f}%（{light}% ～ {heavy}%），建議減倉 1/4",
                     {"pnl_pct": ctx.pnl_pct, "light": light, "heavy": heavy})


@register_rule
def rule_drawdown_cost_weak(ctx: RuleContext) -> Alert | None:
    """v3 新增：52w 回撤大 + 成本虧損 + 基本面偏弱，三重確認才減倉。（系統性修正時降一等級）"""
    dd = _drawdown_from_high(ctx)
    fs = ctx.fund.get("fund_score") or 0
    if dd is not None and dd < -35 and (ctx.pnl_pct or 0) < -5 and fs < 50:
        return Alert(LEVEL_REDUCE, "drawdown_cost_weak",
                     f"52w 回撤 {dd:.1f}% + 成本虧損 {ctx.pnl_pct:.1f}% + 基本面偏弱({int(fs)})，建議降低倉位",
                     {"drawdown_pct": dd, "pnl_pct": ctx.pnl_pct, "fund_score": fs})


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
    """v2：門檻從 75 提高至 80，且趨勢非 UPTREND 才觸發（與技術面評分 v2 統一）。"""
    rsi   = ctx.tech.get("rsi")
    trend = ctx.tech.get("trend_status", "")
    limit = ctx.thresholds.get("rsi_overbought", 80)
    if rsi is not None and rsi > limit and trend != "UPTREND":
        return Alert(LEVEL_WATCH, "rsi_overbought",
                     f"RSI = {rsi:.1f}（>{limit} 過熱）且趨勢非 UPTREND，短期可能回調",
                     {"rsi": rsi, "limit": limit, "trend": trend})


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
    """v2：技術門檻 58→55，持倉上限 22%→25%。"""
    fs = ctx.fund.get("fund_score") or 0
    ts = ctx.tech.get("tech_score") or 0
    trend = ctx.tech.get("trend_status", "")
    fs_th = ctx.thresholds.get("fund_score_add", 70)
    ts_th = ctx.thresholds.get("tech_score_add", 55)
    max_alloc = ctx.thresholds.get("add_max_alloc_pct", 25)

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
    dd = _drawdown_from_high(ctx)
    in_dip = (dd is not None and dd < -3) or (ctx.pnl_pct is not None and ctx.pnl_pct < -3)
    if trend == "OVERSOLD_UPTREND" and fs >= fs_th and in_dip:
        return Alert(LEVEL_ADD, "oversold_add",
                     f"超賣反彈且尚在高點以下，可考慮分批加碼（基本面 {int(fs)}）",
                     {"fund_score": fs, "trend": trend, "pnl_pct": ctx.pnl_pct})


@register_rule
def rule_quality_dip(ctx: RuleContext) -> Alert | None:
    """v2：基本面門檻 70→65（fund_score_add_dip）。"""
    fs = ctx.fund.get("fund_score") or 0
    trend = ctx.tech.get("trend_status", "")
    fs_th = ctx.thresholds.get("fund_score_add_dip", 65)
    dd = _drawdown_from_high(ctx)
    in_dip = (dd is not None and dd < -8) or (ctx.pnl_pct is not None and ctx.pnl_pct < -8)
    if in_dip and fs >= fs_th and trend == "CONSOLIDATION":
        return Alert(LEVEL_ADD, "quality_dip",
                     f"優質股進入盤整低位，可留意加碼時機（基本面 {int(fs)}）",
                     {"fund_score": fs, "pnl_pct": ctx.pnl_pct, "trend": trend})


@register_rule
def rule_fund_upgrade(ctx: RuleContext) -> Alert | None:
    """v2 新增：基本面評分大幅改善（如財報超預期）。需 fund cache 提供 fund_score_prev。"""
    fs      = ctx.fund.get("fund_score")
    fs_prev = ctx.fund.get("fund_score_prev")  # 上期評分（尚未填入時為 None，自然跳過）
    trend   = ctx.tech.get("trend_status", "")
    min_imp = ctx.thresholds.get("fund_improvement_min", 10)
    if fs is not None and fs_prev is not None and (fs - fs_prev) >= min_imp \
            and trend not in ("DOWNTREND", "BREAKDOWN"):
        return Alert(LEVEL_ADD, "fund_upgrade",
                     f"基本面評分大幅改善（{int(fs_prev)} → {int(fs)}，+{int(fs - fs_prev)}），事件性加倉機會",
                     {"fund_score": fs, "fund_score_prev": fs_prev, "improvement": fs - fs_prev})


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
