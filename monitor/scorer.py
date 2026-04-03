"""
monitor/scorer.py — 候選股綜合評分

綜合分 = fund_score × w_f + tech_score × w_t + risk_score × w_r + news_boost × w_n
所有權重來自 monitor_config.json 的 scoring_weights.composite_for_candidates。
"""
from __future__ import annotations
from dataclasses import dataclass

from .config import get_scoring_weights


# 買入信號分級門檻（綜合分）
_BUY_SIGNAL_TIERS = [
    (75, "💎 強力買入", "#7c3aed"),
    (65, "✅ 可以買入", "#059669"),
    (52, "👀 觀察等候", "#eab308"),
    (0,  "⏸️  尚未就緒", "#94a3b8"),
]

TREND_UPWARD = {"UPTREND", "RECOVERY", "OVERSOLD_UPTREND"}


@dataclass
class CandidateScore:
    symbol:     str
    composite:  float | None
    signal:     str
    color:      str
    fund_score: float | None
    tech_score: float | None
    risk_score: float | None
    trend:      str
    rsi:        float | None
    price:      float | None
    change_3mo: float | None
    high_52w:   float | None
    drawdown_pct: float | None   # 距 52w 高點回撤 %
    news_sentiment: str          # bullish / bearish / neutral / mixed / ""
    reasons:    list[str]
    in_portfolio: bool

    def to_dict(self) -> dict:
        return {
            "symbol":       self.symbol,
            "composite":    self.composite,
            "signal":       self.signal,
            "signal_color": self.color,
            "fund_score":   self.fund_score,
            "tech_score":   self.tech_score,
            "risk_score":   self.risk_score,
            "trend":        self.trend,
            "rsi":          self.rsi,
            "price":        self.price,
            "change_3mo":   self.change_3mo,
            "drawdown_pct": self.drawdown_pct,
            "news_sentiment": self.news_sentiment,
            "reasons":      self.reasons,
            "in_portfolio": self.in_portfolio,
        }


def score_candidate(
    symbol: str,
    fund: dict,
    tech: dict,
    in_portfolio: bool = False,
    config: dict | None = None,
) -> CandidateScore:
    """
    計算候選股綜合評分。
    fund / tech 為 cache 讀出的 dict（同 dashboard 使用的格式）。
    """
    weights_cfg = get_scoring_weights(config)
    comp_w = weights_cfg.get("composite_for_candidates", {})
    news_cfg = weights_cfg.get("news_sentiment", {})

    w_f = comp_w.get("fund_score", 0.40)
    w_t = comp_w.get("tech_score", 0.35)
    w_r = comp_w.get("risk_score", 0.20)
    w_n = comp_w.get("news_boost", 0.05)

    fs = fund.get("fund_score")
    ts = tech.get("tech_score")
    rs = tech.get("risk_score")
    trend = tech.get("trend_status") or "UNKNOWN"
    rsi   = tech.get("rsi")
    price = tech.get("current_price") or fund.get("current_price")
    change_3mo = tech.get("change_3mo_pct")
    high_52w   = tech.get("high_52w")

    # 消息面（從 fund cache 的 news_analysis 讀取）
    news_sentiment = _extract_news_sentiment(fund)
    news_score = news_cfg.get(news_sentiment, 0) if news_sentiment else 0

    # 計算綜合分
    if fs is None and ts is None and rs is None:
        composite = None
    else:
        composite = 0.0
        if fs is not None: composite += fs * w_f
        if ts is not None: composite += ts * w_t
        if rs is not None: composite += rs * w_r
        # news boost 以 100 為基準正規化
        composite += news_score * w_n * 100 / max(abs(news_score), 1) if news_score != 0 else 0
        composite = round(composite, 1)

    # 距 52w 高點回撤
    drawdown = None
    if price and high_52w and high_52w > 0:
        drawdown = round((price - high_52w) / high_52w * 100, 1)

    # 買入信號分級
    signal, color = _buy_signal(composite, fs, ts, trend)

    # 說明理由
    reasons = _build_reasons(fs, ts, rs, trend, rsi, change_3mo, drawdown, news_sentiment)

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
    )


def _buy_signal(composite, fs, ts, trend):
    """根據綜合分 + 輔助條件決定買入信號。"""
    if composite is None:
        return "⏸️  無資料", "#94a3b8"

    # 若技術面或基本面明顯弱，降級
    if (fs or 0) < 40 or (ts or 0) < 35:
        return "⏸️  尚未就緒", "#94a3b8"

    for threshold, label, color in _BUY_SIGNAL_TIERS:
        if composite >= threshold:
            # 💎 強力買入需額外確認趨勢向上
            if label == "💎 強力買入" and trend not in TREND_UPWARD:
                return "✅ 可以買入", "#059669"
            return label, color

    return "⏸️  尚未就緒", "#94a3b8"


def _extract_news_sentiment(fund: dict) -> str:
    """從 fund cache 中嘗試取得消息面情緒。"""
    # news_analysis 欄位由 render.py 填入（holdings cache 可能沒有）
    na = fund.get("news_analysis") or {}
    summary = na.get("summary") or {}
    return summary.get("overall_sentiment", "") or ""


def _build_reasons(fs, ts, rs, trend, rsi, change_3mo, drawdown, news_sentiment) -> list[str]:
    reasons = []
    if fs is not None:
        if fs >= 80:   reasons.append(f"基本面優秀({int(fs)})")
        elif fs >= 65: reasons.append(f"基本面良好({int(fs)})")
        elif fs < 45:  reasons.append(f"基本面偏弱({int(fs)})")

    if trend == "UPTREND":             reasons.append("上升趨勢")
    elif trend == "OVERSOLD_UPTREND":  reasons.append("超賣反彈")
    elif trend == "RECOVERY":          reasons.append("趨勢修復中")
    elif trend == "DOWNTREND":         reasons.append("⚠️下跌趨勢")
    elif trend == "BREAKDOWN":         reasons.append("⚠️技術崩跌")

    if rsi is not None:
        if rsi < 32:       reasons.append(f"RSI超賣({rsi:.0f})")
        elif 40 <= rsi <= 58: reasons.append(f"RSI健康({rsi:.0f})")
        elif rsi > 72:     reasons.append(f"RSI超買({rsi:.0f})")

    if rs is not None and rs >= 70: reasons.append(f"風險低({int(rs)})")
    if rs is not None and rs < 35:  reasons.append(f"⚠️風險高({int(rs)})")

    if change_3mo is not None:
        if change_3mo >= 15:   reasons.append(f"近3月強勢(+{change_3mo:.0f}%)")
        elif change_3mo <= -15: reasons.append(f"近3月弱勢({change_3mo:.0f}%)")

    if drawdown is not None and drawdown < -20:
        reasons.append(f"距52w高點-{abs(drawdown):.0f}%（低位）")

    if news_sentiment == "bullish":  reasons.append("消息面偏多")
    elif news_sentiment == "bearish": reasons.append("⚠️消息面偏空")

    return reasons
