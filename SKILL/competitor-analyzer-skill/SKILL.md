---
name: competitor-analyzer
description: |
  **Stock Competitor Analyzer**: Searches the web to identify the #1 real-world competitor for each of the user's stock holdings, broken down by business segment. Outputs a structured competitors.json mapping each ticker to its true top rivals — not limited to the user's portfolio.
  - MANDATORY TRIGGERS: 競爭對手, competitor, 競品, rivals, 對手分析, competitive analysis, competitor map, 頭號對手, generate competitors, update competitors
  - Also trigger when: the user asks who competes with their stocks; the user wants to refresh or regenerate competitors.json; the user mentions "找出對手" or "比較競品"
  - Do NOT trigger for: news analysis, price lookups, portfolio rebalancing, or technical analysis
---

# Stock Competitor Analyzer

This skill identifies the **real #1 competitor** for each stock in the user's portfolio, broken down by business segment. Unlike simple sector-matching, it uses web search to find genuinely meaningful competitive relationships — companies that directly compete for the same customers, same market, same technology.

## Why This Skill Exists

The existing `generate_competitors.py` only matches stocks within the portfolio by sector/industry, which misses the real picture. For example, NVDA's true GPU competitor is AMD, not another stock the user happens to own. This skill fills that gap by searching for actual competitive dynamics.

## Workflow

### Step 1: Read the Portfolio

Read `holdings.csv` from the project root. Extract unique tickers, filtering out:
- **Cash entries**: symbol = `cash`
- **Options**: symbols containing `(` (e.g., `SOFI(270115C00010000)`)
- **Leveraged / thematic ETFs**: `AMZU`, `GGLL` (these track an underlying stock, not a separate company)
- **Broad-market ETFs**: `QQQ`, `VOO`, `IBIT` (no single competitor makes sense)

This leaves the **real individual stocks** to analyze.

Also read `company_names.json` for ticker → company name mapping to aid search accuracy.

### Step 2: For Each Ticker, Search & Identify Competitors

For each stock ticker, do the following:

1. **Web search** with a query like: `"{Company Name}" top competitors 2025 2026 by business segment`
2. **Read** 1-2 of the most relevant results (prefer sources like: Investopedia, MarketBeat, Yahoo Finance, industry analysis sites)
3. **Identify business segments** the company operates in (e.g., AMZN → e-commerce, cloud/AWS, advertising, streaming)
4. **For each segment**, pick the **single #1 competitor** — the company that most directly and significantly competes in that space. This competitor does NOT need to be in the user's portfolio. Think broadly. Consider:
   - Direct product competition (AMD vs NVDA in GPUs)
   - Market share rivalry (Google vs Meta in digital ads)
   - Strategic overlap (MSFT Azure vs AMZN AWS in cloud)

### Step 3: Output `competitors.json`

Write the result to `competitors.json` in the project root, using **exactly the same format** as the existing file:

```json
{
  "AMZN": ["WMT", "MSFT", "GOOG", "DIS"],
  "NVDA": ["AMD", "INTC", "MSFT"],
  "TSLA": ["TM", "BYD", "RIVN"],
  ...
}
```

**Format rules:**
- Keys = tickers from the portfolio (ALL tickers from holdings.csv, including ETFs/options/cash)
- Values = array of competitor tickers (as traded on US exchanges when possible; if the competitor is not US-listed, use the most recognized ticker or ADR, e.g., `BYDDY` for BYD)
- For ETFs, leveraged products, options, and cash: use an **empty array** `[]`
- Deduplicate: if a competitor appears across multiple segments for the same stock, list it only once
- Order competitors by significance (most important segment first)

### Step 4: Output Summary Report

After writing `competitors.json`, also write a human-readable `COMPETITORS_SUMMARY.txt` to the project root:

```
COMPETITOR ANALYSIS SUMMARY
Generated: {date}

========================================
{TICKER} ({Company Name})
========================================
Segments & #1 Competitors:

  1. {Segment Name}
     #1 Competitor: {COMPETITOR_TICKER} ({Competitor Company Name})
     Reason: {1-sentence explanation in Traditional Chinese}

  2. {Segment Name}
     #1 Competitor: {COMPETITOR_TICKER} ({Competitor Company Name})
     Reason: {1-sentence explanation in Traditional Chinese}

---
```

Repeat for each analyzed ticker.

## Important Notes

- **Be thorough with web search**: Don't rely solely on LLM knowledge. The user explicitly wants web-sourced, up-to-date competitor data.
- **Think beyond the portfolio**: The whole point is to find the TRUE competitor, not just match with other held stocks.
- **One competitor per segment**: Keep it focused — the #1 rival, not a laundry list.
- **US tickers preferred**: When a competitor is listed on US exchanges, use the US ticker. For foreign companies, use the ADR ticker if available.
- **Speed matters**: Process tickers efficiently. You can batch web searches where topics overlap (e.g., cloud competitors might appear in both AMZN and MSFT searches).

## Language — 繁體中文

All Chinese text in the summary report MUST be in Traditional Chinese (繁體中文). Follow the same typographic rules as `news-analyzer`:
- Add spaces between Chinese and English/numbers: `Amazon 宣布投資 $50B`
- Use full-width punctuation in Chinese context: `，` `。` `；`
- Never mix simplified and traditional characters
