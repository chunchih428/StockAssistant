# 候選股信號規則說明

> 適用範圍：「候選評分」→「個股評分一覽」→ 警示 / 信號欄
> 信號由**綜合分**決定，再疊加趨勢條件與個別科目不及格保護。
> 所有門檻皆可在 `config/monitor_config.json` → `candidate_signals` 調整。

---

## 信號總覽

| 信號 | 顏色 | 最低綜合分 | 額外條件 |
|------|------|-----------|---------|
| 💎 強力買入 | 🟣 紫 | 75 | 趨勢必須為向上（UPTREND / RECOVERY / OVERSOLD_UPTREND） |
| ✅ 可以買入 | 🟢 綠 | 65 | 無 |
| 👀 觀察等候 | 🟡 黃 | 52 | 無 |
| ⏸️ 尚未就緒 | ⚫ 灰 | 40 | 無 |
| ❌ 不予以考慮 | 🔴 紅 | 0 | 無 |

---

## 綜合分計算公式

```
綜合分 = 基本面分 × 0.40
       + 技術面分 × 0.35
       + 風險面分 × 0.20
       + 消息面加減 × 0.05（正規化後上限 ±5 分）
```

### 各項子分滿分

| 子分項 | 滿分 | 說明 |
|--------|------|------|
| 基本面分（fund_score） | 100 | 營收/毛利/FCF/ROIC/PEG/分析師/負債 |
| 技術面分（tech_score） | 100 | 趨勢/RSI/MACD/布林帶/成交量比/ATR |
| 風險面分（risk_score） | 100 | VaR/Sortino/Max Drawdown/Beta/Calmar |

### 消息面加減（news boost）

| 情緒 | 原始分 | 實際加減 |
|------|--------|---------|
| strongly_bullish | +15 | **+5** |
| bullish | +8 | **+5** |
| neutral | +2 | **+5** |
| mixed | 0 | **0** |
| bearish | -8 | **-5** |
| strongly_bearish | -15 | **-5** |

> 消息面不影響子分分級，僅作為綜合分的小幅修正（最多 ±5）。

---

## 信號決定流程

```
1. 計算綜合分
        ↓
2. 對應 Tier（由高到低，取第一個 composite ≥ min_score 的 tier）
        ↓
3. 若該 tier 有 require_uptrend = true（即 💎 強力買入）
   且趨勢不屬向上系列 → 降到下一個 tier
        ↓
4. Disqualify 保護：若 fund_score < 40 OR tech_score < 35
   且當前 tier 高於「⏸️ 尚未就緒」→ 強制壓到「⏸️ 尚未就緒」
   （Disqualify 只往下壓，不往上推）
        ↓
5. 輸出最終信號
```

---

## 強力買入觸發範例

| 條件 | 需符合 |
|------|--------|
| 綜合分 | ≥ 75 |
| 趨勢 | UPTREND 或 RECOVERY 或 OVERSOLD_UPTREND |
| 基本面分 | ≥ 40（Disqualify 保護） |
| 技術面分 | ≥ 35（Disqualify 保護） |

---

## Disqualify 保護說明

即使綜合分很高（如 80 分），只要：

- 基本面分 < 40，**或**
- 技術面分 < 35

信號就會被壓制為「⏸️ 尚未就緒」，**不會顯示 💎 強力買入 / ✅ 可以買入 / 👀 觀察等候**。

反之，若綜合分本身就在「⏸️ 尚未就緒」以下（< 40），Disqualify 不會把信號往上拉。

---

## 說明理由欄（reasons）產生邏輯

信號旁的說明標籤由以下規則自動產生：

| 條件 | 說明標籤 |
|------|---------|
| fund_score ≥ 80 | 基本面優秀(N) |
| fund_score 65–79 | 基本面良好(N) |
| fund_score < 45 | 基本面偏弱(N) |
| 趨勢 = UPTREND | 上升趨勢 |
| 趨勢 = OVERSOLD_UPTREND | 超賣反彈 |
| 趨勢 = RECOVERY | 趨勢修復中 |
| 趨勢 = DOWNTREND | ⚠️下跌趨勢 |
| 趨勢 = BREAKDOWN | ⚠️技術崩跌 |
| RSI < 32 | RSI超賣(N) |
| RSI 40–58 | RSI健康(N) |
| RSI > 72 | RSI超買(N) |
| risk_score ≥ 70 | 風險低(N) |
| risk_score < 35 | ⚠️風險高(N) |
| 近3月漲幅 ≥ +15% | 近3月強勢(+N%) |
| 近3月漲幅 ≤ -15% | 近3月弱勢(N%) |
| 距52w高點 < -20% | 距52w高點-N%（低位） |
| news = strongly_bullish | 🔥消息面強力利多 |
| news = bullish | 消息面偏多 |
| news = strongly_bearish | 🚨消息面強力利空 |
| news = bearish | ⚠️消息面偏空 |

---

## 閾值速查（monitor_config.json → candidate_signals）

| 參數 | 預設值 | 說明 |
|------|--------|------|
| tiers[0].min_score | 75 | 強力買入最低綜合分 |
| tiers[1].min_score | 65 | 可以買入最低綜合分 |
| tiers[2].min_score | 52 | 觀察等候最低綜合分 |
| tiers[3].min_score | 40 | 尚未就緒最低綜合分 |
| tiers[4].min_score | 0 | 不予以考慮（兜底） |
| disqualify.fund_score_min | 40 | 基本面不及格門檻 |
| disqualify.tech_score_min | 35 | 技術面不及格門檻 |

### 綜合分加權比例（composite_for_candidates）

| 參數 | 預設值 |
|------|--------|
| fund_score 權重 | 0.40 |
| tech_score 權重 | 0.35 |
| risk_score 權重 | 0.20 |
| news_boost 權重 | 0.05 |
