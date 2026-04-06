# 持股警示規則說明

> 適用範圍：「持股評分一覽」→ 警示欄
> 警示欄只顯示**最高等級**警示 + 第一條說明文字。
> 所有閾值皆可在 `config/monitor_config.json` → `thresholds` 調整，也可用 `overrides` 對個股單獨覆蓋。

---

## 等級總覽

| 等級 | 標籤 | 顏色 | 優先序 |
|------|------|------|--------|
| 0 | 🚨 停損 | 🔴 紅 | 最高 |
| 1 | ⚠️ 減倉 | 🟠 橙 | ↑ |
| 2 | 👀 觀察 | 🟡 黃 | ↓ |
| 3 | 💎 加倉機會 | 💜 紫 | ↓ |
| 4 | ✅ 持有 | 🟢 綠 | 最低（無規則觸發時預設） |

---

## 🚨 停損（LEVEL 0）

| 規則 ID | 觸發條件 | 預設閾值 |
|---------|---------|---------|
| `stop_loss` | 持倉虧損 ≤ stop_loss_pct | **-20%** |
| `fund_collapse` | 基本面評分 < fund_score_close | **30 分** |
| `breakdown` | 趨勢 = BREAKDOWN **且** 技術分 < 40 | — |
| `ai_close` | AI 分析建議平倉 | — |

---

## ⚠️ 減倉（LEVEL 1）

| 規則 ID | 觸發條件 | 預設閾值 |
|---------|---------|---------|
| `concentration` | 單一持倉佔組合比例 > max_single_alloc_pct | **30%** |
| `take_profit` | 持倉獲利 ≥ take_profit_pct | **+60%** |
| `warn_loss` | 虧損介於 warn_loss_pct 與 stop_loss_pct 之間 | **-12% ～ -20%** |
| `downtrend_tech` | 趨勢 = DOWNTREND **且** 技術分 < tech_score_reduce | **45 分** |
| `high_risk` | 風險評分 < risk_score_reduce | **30 分** |
| `ai_reduce` | AI 分析建議減倉 | — |

---

## 👀 觀察（LEVEL 2）

| 規則 ID | 觸發條件 | 預設閾值 |
|---------|---------|---------|
| `rsi_overbought` | RSI > rsi_overbought | **75** |
| `rsi_oversold_danger` | RSI < rsi_oversold **且** 趨勢未翻多（非 UPTREND / RECOVERY / OVERSOLD_UPTREND） | **28** |
| `tech_weak` | 技術分 < tech_score_reduce **且** 趨勢非 DOWNTREND / BREAKDOWN | **45 分** |
| `var_high` | 1-Day VaR(95%) < -5%（單日下行風險偏高） | **-5%** |
| `high_leverage` | 負債 / 權益比 > 3.0 | **3.0** |
| `rev_decline` | 營收年增率 < -5% | **-5%** |

---

## 💎 加倉機會（LEVEL 3）

| 規則 ID | 觸發條件 | 預設閾值 |
|---------|---------|---------|
| `add_signal` | 基本面分 ≥ fund_score_add **且** 技術分 ≥ tech_score_add **且** 趨勢向上（UPTREND / RECOVERY / OVERSOLD_UPTREND）**且** 持倉佔比 < add_max_alloc_pct | 基本面 **70**、技術 **58**、持倉上限 **22%** |
| `oversold_add` | 趨勢 = OVERSOLD_UPTREND **且** 基本面分 ≥ 62 **且** 損益 < -3% | — |
| `quality_dip` | 基本面分 ≥ fund_score_add **且** 持倉回落 > -8% **且** 趨勢 = CONSOLIDATION | 基本面 **70** |
| `ai_add` | AI 建議加倉 **且** 趨勢屬向上系列（UPTREND / RECOVERY / OVERSOLD_UPTREND / CONSOLIDATION） | — |

---

## ✅ 持有（LEVEL 4）

無任何規則觸發時，預設顯示「持有，各項指標正常，維持現有倉位」。

---

## 閾值速查（monitor_config.json → thresholds）

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `stop_loss_pct` | -20 | 停損線（%） |
| `warn_loss_pct` | -12 | 虧損警告線（%） |
| `take_profit_pct` | 60 | 止盈線（%） |
| `max_single_alloc_pct` | 30 | 單一持倉佔組合上限（%） |
| `add_max_alloc_pct` | 22 | 加倉後持倉上限（%） |
| `fund_score_close` | 30 | 基本面崩壞停損門檻 |
| `fund_score_add` | 70 | 加倉所需最低基本面分 |
| `tech_score_reduce` | 45 | 技術走弱減倉門檻 |
| `tech_score_add` | 58 | 加倉所需最低技術分 |
| `risk_score_reduce` | 30 | 風險過高減倉門檻 |
| `rsi_overbought` | 75 | RSI 超買警戒線 |
| `rsi_oversold` | 28 | RSI 超賣警戒線 |

---

## 規則執行邏輯

1. 每次儀表板重建時，對每支持股執行所有已註冊規則（`monitor/rules.py`）
2. 觸發的 Alert 按等級排序，取**最高等級**顯示在警示欄
3. 若同一等級有多條規則同時觸發，顯示第一條說明；完整清單可在個股面板展開查看
4. 新增規則只需在 `rules.py` 加上 `@register_rule` 裝飾器，無需修改其他程式碼
