---
name: news-analyzer
description: |
  **Stock News Sentiment Analyzer**: Reads raw news JSON files for any stock ticker, classifies each article as bullish/bearish/neutral, ranks by impact, and outputs a structured analysis JSON with detailed reasoning in Traditional Chinese.
  - MANDATORY TRIGGERS: 新聞分析, news analysis, sentiment analysis, 利多利空, bullish bearish, ticker analysis, stock news, 股票新聞, 新聞情緒, analyze news JSON, CatchNews
  - Also trigger when: the user asks to analyze, classify, or summarize financial news for any stock ticker; the user mentions files like `{TICKER}.json` in a news cache directory; the user wants to produce `{TICKER}_analysis.json`; the user says "do the same analysis for other tickers" or similar batch requests
  - Do NOT trigger for: general stock price lookups, trading execution, portfolio management, or non-news financial data (fundamentals, technicals)
---

# Stock News Sentiment Analyzer

This skill transforms raw financial news JSON files into structured sentiment analysis reports. Each article is classified as bullish, bearish, or neutral for the target ticker, ranked by impact, and annotated with detailed reasoning in Traditional Chinese.

## Why This Skill Exists

Financial news arrives as a flat list of headlines. Investors need to quickly understand: "Is the overall news picture positive or negative for this stock, and which stories matter most?" This skill bridges that gap by producing a consistent, machine-readable JSON that can be consumed by dashboards, reports, or further analysis pipelines.

## Input Format

The skill expects a JSON file at a path like `cache/news/{TICKER}.json` with this structure:

```json
{
  "articles": [
    {
      "title": "Article headline — optional subtitle or summary text",
      "link": "https://...",
      "publisher": "CNBC",
      "date": "2026-02-28 00:56",
      "_source": "finnhub",
      "_score": 17.28
    }
  ],
  "_cached_at": "2026-03-02T12:34:06.580134"
}
```

The `title` field often contains both the headline and a truncated summary after a dash (` — `). Extract as much context as possible from this combined text.

## Analysis Process

For each article, determine:

1. **Sentiment direction** — Is this bullish, bearish, or neutral *for the specific ticker being analyzed*? An article about a competitor's failure might be bullish for our ticker even though the article itself sounds negative. Think from the perspective of the ticker's stock price.

2. **Impact level** (high / medium / low) — Consider:
   - How directly does this affect the company's revenue, profit, or strategic position?
   - Is it a one-time event or a structural shift?
   - How prominent is the source? (e.g., CNBC, WSJ carry more weight than niche blogs)
   - Does it involve specific dollar amounts, executive actions, or regulatory decisions?

3. **Category** — Pick the most fitting from the standard set (see Output Schema below). If none fit well, you can use a descriptive slug like `supply_chain_risk`.

4. **Rank** — Within each sentiment group (bullish/bearish/neutral), rank by impact. Rank 1 = highest impact.

5. **Article cap** — Keep at most **8 articles** per sentiment group (bullish/bearish). Retain only the highest-impact items; neutral has no cap. Update `summary.*_count` and `total_articles` accordingly.

6. **Reason** — Write a detailed paragraph in Traditional Chinese that includes:
   - Specific names (people, companies, institutions)
   - Specific numbers (dollar amounts, percentages, dates)
   - The causal chain: why does this news item affect the stock?
   - Context that a financial analyst would find useful

### Handling Edge Cases

- **Duplicate coverage**: If two articles cover the same event, keep the more detailed one in its sentiment group and move the duplicate to `neutral` with `category: "duplicate_coverage"` and a reason explaining the overlap.
- **Mixed signals**: Some articles are bullish on one dimension but bearish on another (e.g., "revenue up but margins compressed"). Classify by the *net* impact on stock price. If truly balanced, use `neutral`.
- **Tangential mentions**: If the ticker is only mentioned in passing (e.g., in a list of companies), classify as `neutral` unless the context implies a clear directional impact.
- **ETFs and indices**: For ETFs (QQQ, VOO, IBIT, etc.), analyze sentiment for the *ETF itself*, not its underlying holdings. Macro factors, fund flows, and structural risks matter more than individual stock news.
- **Leveraged / thematic ETFs**: For products like AMZU or GGLL, note that leverage amplifies both upside and downside. The sentiment analysis should account for the underlying asset's news but flag the amplification risk.

## Output Schema (v1.1)

Save the output as `{TICKER}_analysis.json` in the same directory as the input file.

```json
{
  "ticker": "AMZN",
  "company": "Amazon.com Inc.",
  "analysis_date": "2026-03-02",
  "source_file": "cache/news/AMZN.json",
  "summary": {
    "total_articles": 10,
    "bullish_count": 6,
    "bearish_count": 3,
    "neutral_count": 1,
    "overall_sentiment": "bullish",
    "key_theme": "一句話概括最重要的主題 (Traditional Chinese)"
  },
  "bullish": [
    {
      "rank": 1,
      "title": "Original article title from source",
      "publisher": "CNBC",
      "date": "2026-02-28",
      "impact": "high",
      "category": "strategic_investment",
      "reason": "詳細分析段落，包含具體人名、機構名、金額、因果鏈 (Traditional Chinese, 2-4 sentences)"
    }
  ],
  "bearish": [],
  "neutral": [],
  "_schema_version": "1.1",
  "_schema_notes": {
    "impact_levels": ["high", "medium", "low"],
    "sentiment_options": ["bullish", "bearish", "neutral", "mixed"],
    "common_categories": [
      "strategic_investment",
      "cloud_and_ai",
      "chip_and_hardware",
      "analyst_sentiment",
      "market_expansion",
      "institutional_selling",
      "layoffs",
      "labor_risk",
      "earnings",
      "regulation",
      "competition",
      "product_launch",
      "duplicate_coverage"
    ]
  }
}
```

### Field Requirements

| Field | Required | Notes |
|-------|----------|-------|
| `ticker` | Yes | Uppercase, matches input filename |
| `company` | Yes | Full legal name or common name |
| `analysis_date` | Yes | YYYY-MM-DD format |
| `source_file` | Yes | Relative path to input JSON |
| `summary.total_articles` | Yes | Must equal number of input articles |
| `summary.*_count` | Yes | Must equal actual array lengths |
| `summary.overall_sentiment` | Yes | One of: bullish, bearish, neutral, mixed |
| `summary.key_theme` | Yes | Traditional Chinese, one sentence |
| `*.rank` | Yes | Sequential within each group, starting at 1 |
| `*.title` | Yes | Copied from source article |
| `*.publisher` | Yes | Copied from source article |
| `*.date` | Yes | YYYY-MM-DD (normalize from source format) |
| `*.impact` | Yes | One of: high, medium, low |
| `*.category` | Yes | Prefer standard categories; custom slugs OK |
| `*.reason` | Yes | Traditional Chinese, 2-4 sentences with specifics |

## Batch Processing

When the user asks to analyze multiple tickers, process them efficiently:

1. Read all input files in parallel
2. Write all analysis files
3. Run the validation script on all outputs
4. Present a summary table to the user

## Validation

After writing any analysis JSON, validate it with the built-in script:

```bash
python /path/to/news-analyzer/scripts/validate_analysis.py <file1> <file2> ...
```

This checks: all required fields present, counts match array lengths, impact/sentiment values are valid, and JSON is well-formed. Report any failures to the user.

## Language — 繁體中文 (CRITICAL)

All `reason` fields and `category` and `key_theme` **MUST** be written in **Traditional Chinese** (繁體中文), **NOT** Simplified Chinese (简体中文). This is a strict requirement. Field names, category slugs, and structural elements remain in English for machine readability.

### Common mistakes to avoid

When generating Chinese text, you **MUST** use Traditional Chinese characters. Below are frequently confused pairs — always use the **right column**:

| ❌ Simplified (Do NOT use) | ✅ Traditional (Use this) | Example context |
|---|---|---|
| 与 | 與 | 與 OpenAI 合作 |
| 进 | 進 | 進一步擴展 |
| 发 | 發 | 發展、發布 |
| 对 | 對 | 對股價的影響 |
| 长 | 長 | 長期成長 |
| 产 | 產 | 產業、產品 |
| 业 | 業 | 業務、業績 |
| 资 | 資 | 資本、投資 |
| 经 | 經 | 經營、經濟 |
| 济 | 濟 | 經濟 |
| 动 | 動 | 推動、驅動 |
| 关 | 關 | 關鍵、相關 |
| 开 | 開 | 開發、開放 |
| 实 | 實 | 實際、實現 |
| 现 | 現 | 現金、實現 |
| 达 | 達 | 達成、達到 |
| 强 | 強 | 強化、增強 |
| 价 | 價 | 股價、價值 |
| 领 | 領 | 領域、領先 |
| 运 | 運 | 運營、運算 |
| 显 | 顯 | 顯示、明顯 |
| 这 | 這 | 這項交易 |
| 个 | 個 | 多個因素 |
| 过 | 過 | 超過、通過 |
| 设 | 設 | 設施、設計 |
| 计 | 計 | 計畫、設計 |
| 术 | 術 | 技術 |
| 机 | 機 | 機構、機會 |
| 构 | 構 | 結構、機構 |
| 场 | 場 | 市場 |
| 为 | 為 | 成為、因為 |
| 万 | 萬 | 數萬 |
| 亿 | 億 | 數十億 |
| 从 | 從 | 從…到… |
| 电 | 電 | 電力、電子 |
| 网 | 網 | 網路 |
| 联 | 聯 | 聯盟、關聯 |
| 创 | 創 | 創新、創辦 |
| 数 | 數 | 數據中心 |
| 据 | 據 | 數據、根據 |
| 云 | 雲 | 雲端運算 |
| 竞 | 競 | 競爭 |
| 争 | 爭 | 競爭 |
| 风 | 風 | 風險 |
| 险 | 險 | 風險 |
| 后 | 後 | 之後 |
| 时 | 時 | 時間、當時 |
| 间 | 間 | 期間 |
| 问 | 問 | 問題 |
| 题 | 題 | 問題、主題 |
| 变 | 變 | 變化、改變 |
| 转 | 轉 | 轉型、轉變 |
| 会 | 會 | 社會、會議 |
| 国 | 國 | 美國、國際 |
| 师 | 師 | 分析師 |
| 财 | 財 | 財報、財務 |
| 体 | 體 | 整體、實體 |
| 于 | 於 | 關於、位於 |
| 热 | 熱 | 熱門、熱度 |
| 两 | 兩 | 兩者、兩年 |
| 别 | 別 | 區別、特別 |
| 洁 | 潔 | 清潔能源 |
| 里 | 裡 | 裡面（方位） |
| 拥 | 擁 | 擁有 |

**Self-check**: After writing any `reason` or `key_theme`, scan for the simplified characters listed above and replace them. If unsure, prefer the character with more strokes — Traditional Chinese characters are generally more complex than their Simplified equivalents.

## Typographic Formatting Rules (CRITICAL)

All `reason` and `key_theme` fields must follow these typographic rules for readability and consistency. These are standard Traditional Chinese typesetting conventions.

### 1. Spacing: Chinese ↔ English / Numbers

在中文字與英文字母或數字之間，**必須加一個半形空格**。

| ❌ Bad | ✅ Good |
|---|---|
| `Amazon宣布投資$50B` | `Amazon 宣布投資 $50B` |
| `2026年2月下跌12%` | `2026 年 2 月下跌 12%` |
| `OpenAI的Frontier模型` | `OpenAI 的 Frontier 模型` |
| `AWS成為獨家合作夥伴` | `AWS 成為獨家合作夥伴` |
| `市值達$730B估值` | `市值達 $730B 估值` |

**Rules:**
- Add a space **before** an English word or number that follows a Chinese character
- Add a space **after** an English word or number that precedes a Chinese character
- This also applies to currency symbols: `$`、`€`、`¥`
- Do **NOT** add spaces within English phrases or numbers themselves (e.g., `$50B` stays as-is)
- Do **NOT** add spaces between Chinese characters and full-width punctuation

### 2. Punctuation: Use Full-Width (全形)

在中文語境下，**標點符號一律使用全形**。

| ❌ Half-width (Don't use) | ✅ Full-width (Use this) |
|---|---|
| `,` | `，` |
| `.` (句尾) | `。` |
| `;` | `；` |
| `:` | `：` |
| `!` | `！` |
| `?` | `？` |
| `(` `)` | `（` `）` |
| `"` `"` | `「` `」` |

**Exceptions — keep half-width:**
- Inside pure English text or brand names: `OpenAI, Inc.`
- Decimal points in numbers: `3.14`, `$50.5B`
- Colons in timestamps or URLs: `18:30`, `https://`
- Commas in large numbers: `2,200`

### 3. Other Conventions

- **書名號**：提及報告、節目名稱時可用「」，例如：CNBC「Halftime Report」
- **破折號**：使用全形「——」而非半形 `--`
- **省略號**：使用「……」（兩個全形省略符號）而非 `...`
- **數字格式**：金額用 `$50B`、`€18B`，百分比用 `12%`，不需中文化「美元」「歐元」等貨幣單位（保持簡潔）
- **年份與日期**：`2026 年 2 月 28 日` 或 `2026-02-28`，年月日之間加空格
- **不要混用簡繁**：整段文字必須全部使用繁體字，不得出現任何簡體字
