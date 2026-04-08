"""
monitor/scorer.py — 候選股綜合評分 v3

綜合分 = fund_score × 0.45 + tech_score × 0.30 + risk_score × 0.15 + news_boost × 0.10
         （news_boost 直接加減，上限 ±5 分）
所有權重來自 monitor_config.json 的 scoring_weights.composite_for_candidates。
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .config import get_scoring_weights, get_candidate_signals

TREND_UPWARD = {"UPTREND", "RECOVERY", "OVERSOLD_UPTREND"}

# 建議建倉比例（依信號等級）
SUGGESTED_ALLOC = {
    "💎 強力買入": "12–15%（分批，首批 5%）",
    "✅ 可以買入": "6–10%（分批，首批 4%）",
    "👀 觀察等候": "0%",
    "⏸️  尚未就緒": "0%",
    "❌ 不予以考慮": "0%",
}


@dataclass
class CandidateScore:
    symbol:           str
    composite:        float | None
    signal:           str
    color:            str
    fund_score:       float | None
    tech_score:       float | None
    risk_score:       float | None
    trend:            str
    rsi:              float | None
    price:            float | None
    change_3mo:       float | None
    high_52w:         float | None
    drawdown_pct:     float | None   # 距 52w 高點回撤 %
    news_sentiment:   str            # bullish / bearish / neutral / mixed / ""
    reasons:          list[str]
    in_portfolio:     bool
    suggested_alloc:  str            # v2 新增：建議建倉比例
    sector_alloc_pct: float | None   # v2 新增：同產業已持有佔比 %

    def to_dict(self) -> dict:
        return {
            "symbol":           self.symbol,
            "composite":        self.composite,
            "signal":           self.signal,
            "signal_color":     self.color,
            "fund_score":       self.fund_score,
            "tech_score":       self.tech_score,
            "risk_score":       self.risk_score,
            "trend":            self.trend,
            "rsi":              self.rsi,
            "price":            self.price,
            "change_3mo":       self.change_3mo,
            "drawdown_pct":     self.drawdown_pct,
            "news_sentiment":   self.news_sentiment,
            "reasons":          self.reasons,
            "in_portfolio":     self.in_portfolio,
            "suggested_alloc":  self.suggested_alloc,
            "sector_alloc_pct": self.sector_alloc_pct,
        }


def score_candidate(
    symbol: str,
    fund: dict,
    tech: dict,
    in_portfolio: bool = False,
    config: dict | None = None,
    sector_alloc_pct: float | None = None,   # v2 新增：同產業已持有佔比
    prev_signal: str | None = None,           # v2 新增：上次信號（滯後機制用）
) -> CandidateScore:
    """
    計算候選股綜合評分 v2。
    fund / tech 為 cache 讀出的 dict（同 dashboard 使用的格式）。
    """
    weights_cfg = get_scoring_weights(config)
    comp_w   = weights_cfg.get("composite_for_candidates", {})
    news_cfg = weights_cfg.get("news_sentiment", {})

    # v2 預設權重：fund 0.45 / tech 0.30 / risk 0.15 / news 0.10
    w_f = comp_w.get("fund_score",  0.45)
    w_t = comp_w.get("tech_score",  0.30)
    w_r = comp_w.get("risk_score",  0.15)
    w_n = comp_w.get("news_boost",  0.10)

    fs    = fund.get("fund_score")
    ts    = tech.get("tech_score")
    rs    = tech.get("risk_score")
    trend = tech.get("trend_status") or "UNKNOWN"
    rsi   = tech.get("rsi")
    price = tech.get("current_price") or fund.get("current_price")
    change_3mo = tech.get("change_3mo_pct")
    high_52w   = tech.get("high_52w")
    peg        = fund.get("pegRatio")

    # 消息面（從 fund cache 的 news_analysis 讀取）
    news_sentiment = _extract_news_sentiment(fund)
    # v2：news_cfg 儲存的是 ±50 尺度的原始分，乘以 w_n 後 cap 在 ±5
    news_raw   = news_cfg.get(news_sentiment, 0) if news_sentiment else 0
    news_boost = min(5.0, max(-5.0, news_raw * w_n)) if news_raw != 0 else 0.0

    # 計算綜合分
    if fs is None and ts is None and rs is None:
        composite = None
    else:
        composite = 0.0
        if fs is not None: composite += fs * w_f
        if ts is not None: composite += ts * w_t
        if rs is not None: composite += rs * w_r
        composite += news_boost
        composite = round(composite, 1)

    # 距 52w 高點回撤
    drawdown = None
    if price and high_52w and high_52w > 0:
        drawdown = round((price - high_52w) / high_52w * 100, 1)

    # 買入信號分級（v3）
    signals_cfg = get_candidate_signals(config)
    signal, color, signal_reasons = _buy_signal(
        composite, fs, ts, trend, signals_cfg,
        sector_alloc_pct=sector_alloc_pct,
        prev_signal=prev_signal,
    )

    # 建議建倉比例
    suggested_alloc = _get_suggested_alloc(signal)

    # 說明理由（v3：新增趨勢保護、Soft DQ 限制標籤）
    reasons = _build_reasons(
        fs, ts, rs, trend, rsi, change_3mo, drawdown, news_sentiment,
        peg=peg, sector_alloc_pct=sector_alloc_pct, signal=signal,
    )
    reasons.extend(signal_reasons)

    return CandidateScore(
        symbol=symbol,
        composite=composite,
        signal=signal,
        color=color,
        fund_score=fs,
        tech_score=ts,
        risk_score=rs,
        trend=trend,
        rsi=rsi,
        price=price,
        change_3mo=change_3mo,
        high_52w=high_52w,
        drawdown_pct=drawdown,
        news_sentiment=news_sentiment,
        reasons=reasons,
        in_portfolio=in_portfolio,
        suggested_alloc=suggested_alloc,
        sector_alloc_pct=sector_alloc_pct,
    )


def _buy_signal(
    composite,
    fs,
    ts,
    trend,
    signals_cfg: dict | None = None,
    sector_alloc_pct: float | None = None,
    prev_signal: str | None = None,
):
    """v3：根據綜合分決定買入信號，疊加趨勢保護、Disqualify、產業曝險、滯後機制。"""
    cfg   = signals_cfg or get_candidate_signals()
    tiers = sorted(cfg.get("tiers", []), key=lambda t: t["min_score"], reverse=True)
    disq       = cfg.get("disqualify", {})
    disq_soft  = cfg.get("disqualify_soft", {})
    hysteresis = cfg.get("hysteresis_band", 3)
    extra_reasons: list[str] = []

    if composite is None:
        return "⏸️  無資料", "#94a3b8", []

    def _find_tier(label_prefix):
        return next((t for t in tiers if t["label"].startswith(label_prefix)), None)

    watch_tier     = _find_tier("👀")
    not_ready_tier = _find_tier("⏸️")

    # ── 1. composite 對應 tier（純分數比較） ────────────────────
    composite_tier = None
    for tier in tiers:
        if composite >= tier["min_score"]:
            composite_tier = tier
            break
    if composite_tier is None:
        composite_tier = tiers[-1] if tiers else {"label": "⏸️  尚未就緒", "color": "#94a3b8", "min_score": 0}

    # ── 2. 趨勢保護（v3）───────────────────────────────────────
    # a. 💎 強力買入：趨勢必須向上，否則降到 ✅ 可以買入
    if composite_tier.get("require_uptrend") and trend not in TREND_UPWARD:
        buy_tier = _find_tier("✅")
        if buy_tier:
            composite_tier = buy_tier

    # b. ✅ 可以買入：趨勢不得為 BREAKDOWN / DOWNTREND，否則降到 👀 觀察等候
    TREND_REJECT = {"BREAKDOWN", "DOWNTREND"}
    if composite_tier.get("reject_breakdown") and trend in TREND_REJECT:
        if watch_tier and composite_tier["min_score"] > watch_tier["min_score"]:
            composite_tier = watch_tier
            extra_reasons.append("⚠️趨勢不佳，信號受限")

    # ── 3. 硬性 Disqualify：fund < 40 OR tech < 35 → 尚未就緒 ──
    fund_hard = disq.get("fund_score_min", 40)
    tech_hard = disq.get("tech_score_min", 35)
    if (fs or 0) < fund_hard or (ts or 0) < tech_hard:
        disq_label = disq.get("disqualify_label", "⏸️  尚未就緒")
        disq_tier  = next((t for t in tiers if t["label"] == disq_label), None)
        if disq_tier and composite_tier["min_score"] > disq_tier["min_score"]:
            return disq_tier["label"], disq_tier["color"], extra_reasons

    # ── 4. 軟性 Disqualify（v3）：只壓到 👀 觀察等候，絕不壓到尚未就緒 ──
    soft_fund = disq_soft.get("fund_score_min", 50)
    soft_tech = disq_soft.get("tech_score_min", 45)
    if watch_tier:
        fund_in_soft = fund_hard <= (fs or 0) < soft_fund
        tech_in_soft = tech_hard <= (ts or 0) < soft_tech
        if (fund_in_soft or tech_in_soft) and composite_tier["min_score"] > watch_tier["min_score"]:
            composite_tier = watch_tier
            extra_reasons.append("⚠️子分偏弱，信號受限")

    # ── 5. 產業曝險（v3）───────────────────────────────────────
    # 軟上限（≥40%）→ 上限觀察等候；硬上限（≥50%）→ 壓到尚未就緒
    sector_cap      = cfg.get("sector_cap_for_candidate", 40)
    sector_hard_cap = cfg.get("sector_hard_cap", 50)
    if sector_alloc_pct is not None:
        if sector_alloc_pct >= sector_hard_cap and not_ready_tier:
            if composite_tier["min_score"] > not_ready_tier["min_score"]:
                composite_tier = not_ready_tier
        elif sector_alloc_pct >= sector_cap and watch_tier:
            if composite_tier["min_score"] > watch_tier["min_score"]:
                composite_tier = watch_tier

    # ── 6. 滯後機制（v2）：降級需低於 prev_tier - hysteresis_band ──
    if prev_signal is not None:
        prev_tier = next((t for t in tiers if t["label"] == prev_signal), None)
        if prev_tier and composite_tier["min_score"] < prev_tier["min_score"]:
            if composite >= prev_tier["min_score"] - hysteresis:
                composite_tier = prev_tier

    return composite_tier["label"], composite_tier["color"], extra_reasons


def _get_suggested_alloc(signal: str) -> str:
    """根據信號取得建議建倉比例。"""
    for key, val in SUGGESTED_ALLOC.items():
        if signal.startswith(key[:3]):   # 用前 3 個字元比對（避免空白差異）
            return val
    return "0%"


def _extract_news_sentiment(fund: dict) -> str:
    """從 fund cache 中嘗試取得消息面情緒。"""
    na      = fund.get("news_analysis") or {}
    summary = na.get("summary") or {}
    return summary.get("overall_sentiment", "") or ""


def _build_reasons(
    fs, ts, rs, trend, rsi, change_3mo, drawdown, news_sentiment,
    peg=None, sector_alloc_pct=None, signal=None,
) -> list[str]:
    reasons = []

    # 基本面
    if fs is not None:
        if fs >= 80:   reasons.append(f"基本面優秀({int(fs)})")
        elif fs >= 65: reasons.append(f"基本面良好({int(fs)})")
        elif fs < 45:  reasons.append(f"基本面偏弱({int(fs)})")

    # Forward PEG 估值（v2 新增）
    if peg is not None and peg > 0:
        if peg < 1.0:   reasons.append(f"估值偏低(PEG={peg:.1f})")
        elif peg <= 2.0: reasons.append(f"估值合理(PEG={peg:.1f})")
        elif peg > 2.5: reasons.append(f"⚠️估值偏高(PEG={peg:.1f})")

    # 趨勢
    if trend == "UPTREND":             reasons.append("上升趨勢")
    elif trend == "OVERSOLD_UPTREND":  reasons.append("超賣反彈")
    elif trend == "RECOVERY":          reasons.append("趨勢修復中")
    elif trend == "DOWNTREND":         reasons.append("⚠️下跌趨勢")
    elif trend == "BREAKDOWN":         reasons.append("⚠️技術崩跌")

    # RSI
    if rsi is not None:
        if rsi < 32:          reasons.append(f"RSI超賣({rsi:.0f})")
        elif 40 <= rsi <= 58: reasons.append(f"RSI健康({rsi:.0f})")
        elif rsi > 72:        reasons.append(f"RSI超買({rsi:.0f})")

    # 風險
    if rs is not None and rs >= 70: reasons.append(f"風險低({int(rs)})")
    if rs is not None and rs < 35:  reasons.append(f"⚠️風險高({int(rs)})")

    # 近 3 月表現
    if change_3mo is not None:
        if change_3mo >= 15:    reasons.append(f"近3月強勢(+{change_3mo:.0f}%)")
        elif change_3mo <= -15: reasons.append(f"近3月弱勢({change_3mo:.0f}%)")

    # 距 52w 高點
    if drawdown is not None and drawdown < -20:
        reasons.append(f"距52w高點-{abs(drawdown):.0f}%（低位）")

    # 產業曝險（v2 新增）
    if sector_alloc_pct is not None and sector_alloc_pct >= 40:
        reasons.append(f"⚠️產業曝險偏高({sector_alloc_pct:.0f}%)")

    # 消息面
    if news_sentiment == "strongly_bullish":   reasons.append("🔥消息面強力利多")
    elif news_sentiment == "bullish":          reasons.append("消息面偏多")
    elif news_sentiment == "strongly_bearish": reasons.append("🚨消息面強力利空")
    elif news_sentiment == "bearish":          reasons.append("⚠️消息面偏空")

    # 建議建倉比例（v2 新增）
    if signal:
        alloc = _get_suggested_alloc(signal)
        if alloc and alloc != "0%":
            reasons.append(f"建議建倉 {alloc}")

    return reasons
