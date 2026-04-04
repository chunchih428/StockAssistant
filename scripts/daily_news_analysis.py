#!/usr/bin/env python3
"""
Daily News Sentiment Analysis
==============================
每天下午 6:00 自動執行：掃描 cache/news/ 下所有 {TICKER}.json，
呼叫 Claude API 進行新聞情緒分析，輸出 {TICKER}_analysis.json。

使用方式：
  python3 daily_news_analysis.py              # 分析所有 Ticker
  python3 daily_news_analysis.py AMZN NVDA    # 只分析指定 Ticker

設定 cron（Mac/Linux）：
  1. 在終端機執行：crontab -e
  2. 加入下面這行（將路徑換成你自己的資料夾路徑）：
     0 18 * * * cd /你的路徑/PersonalFinanceCC && /usr/bin/python3 daily_news_analysis.py >> logs/analysis.log 2>&1
  3. 儲存並關閉

注意：需要先安裝 anthropic SDK：pip3 install anthropic
"""

import json
import os
import sys
import glob
from datetime import date
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("請先安裝 anthropic SDK：pip3 install anthropic")
    sys.exit(1)

# ── 設定 ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
NEWS_DIR = SCRIPT_DIR / "cache" / "news"
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 從環境變數取得 API Key
try:
    from dotenv import load_dotenv
    env_path = SCRIPT_DIR.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANALYSIS_PROMPT = """你是一位專業的股票新聞情緒分析師。

給定以下股票代碼的新聞 JSON，請逐篇分析每篇新聞對 {ticker} 股價的影響方向。

## 分析規則

對每篇新聞：
1. **方向判斷**：bullish（利多）、bearish（利空）、neutral（中性）
   - 從 {ticker} 股價與基本面的角度判斷，而非新聞本身的情緒
   - 競爭對手的壞消息可能對 {ticker} 是利多
2. **影響力**：high / medium / low
   - 考量直接性、金額大小、來源公信力、是否為結構性改變
3. **分類**：從以下選擇最符合的（可自訂 slug）：
   strategic_investment, cloud_and_ai, chip_and_hardware, analyst_sentiment,
   market_expansion, institutional_selling, layoffs, labor_risk, earnings,
   regulation, competition, product_launch, duplicate_coverage
4. **Rank**：各組內依影響力排序，1 = 最高
5. **Reason**：用繁體中文寫 2-4 句，含具體人名、機構、金額、因果鏈
6. **保留原始欄位**：請直接從輸入新聞中複製 title、publisher、date、link 等欄位到輸出，確保 link 欄位存在

## 特殊處理
- 重複報導同一事件：主要版本保留原分組，次要版本移入 neutral 並標記 duplicate_coverage
- 切線提及（ticker 只是列表中的一員）：歸入 neutral
- ETF 類（QQQ/VOO/IBIT 等）：分析對 ETF 整體的影響，考慮資金流向與總體風險

## 輸入新聞
```json
{articles_json}
```

## 輸出格式
直接回傳有效的 JSON，不要加 markdown 代碼塊：
{{
  "ticker": "{ticker}",
  "company": "{company}",
  "analysis_date": "{today}",
  "source_file": "cache/news/{ticker}.json",
  "summary": {{
    "total_articles": <輸入文章總數>,
    "bullish_count": <利多數>,
    "bearish_count": <利空數>,
    "neutral_count": <中性數>,
    "overall_sentiment": "<strongly_bullish|bullish|neutral|mixed|bearish|strongly_bearish>",
    "key_theme": "<一句話總結最重要主題，繁體中文>"
  }},
  "bullish": [ {{ "rank":1, "title":"...", "publisher":"...", "date":"YYYY-MM-DD", "link":"...", "impact":"high|medium|low", "category":"...", "reason":"..." }} ],
  "bearish": [],
  "neutral": [],
  "_schema_version": "1.1",
  "_schema_notes": {{
    "impact_levels": ["high","medium","low"],
    "sentiment_options": ["strongly_bullish","bullish","neutral","mixed","bearish","strongly_bearish"],
    "sentiment_guide": {{
      "strongly_bullish": "重大正面催化劑：財報大幅超預期、多家上調目標價、重大合約/併購",
      "bullish": "正面消息占多數，無顯著利空",
      "neutral": "無重大消息，或正負小幅抵銷",
      "mixed": "同時存在顯著利多與利空，多空並陳",
      "bearish": "負面消息占多數",
      "strongly_bearish": "重大負面催化劑：財報大幅低於預期、重大訴訟/監管制裁、高層醜聞"
    }},
    "common_categories": ["strategic_investment","cloud_and_ai","chip_and_hardware","analyst_sentiment","market_expansion","institutional_selling","layoffs","labor_risk","earnings","regulation","competition","product_launch","duplicate_coverage"]
  }}
}}
"""

# 公司名稱對照表（可自行擴充）
COMPANY_NAMES = {
    "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "NVDA": "NVIDIA Corporation",
    "TSLA": "Tesla Inc.",
    "META": "Meta Platforms Inc.",
    "MSFT": "Microsoft Corporation",
    "COIN": "Coinbase Global Inc.",
    "CRWD": "CrowdStrike Holdings Inc.",
    "NET": "Cloudflare Inc.",
    "NFLX": "Netflix Inc.",
    "NTAP": "NetApp Inc.",
    "PWR": "Quanta Services Inc.",
    "CCJ": "Cameco Corporation",
    "CEG": "Constellation Energy Corporation",
    "ETN": "Eaton Corporation PLC",
    "QQQ": "Invesco QQQ Trust (Nasdaq-100 ETF)",
    "VOO": "Vanguard S&P 500 ETF",
    "IBIT": "iShares Bitcoin Trust ETF",
    "AMZU": "Direxion Daily AMZN Bull 2X Shares",
    "GGLL": "Direxion Daily GOOGL Bull 2X Shares",
    "LASR": "nLIGHT Inc.",
}


def clean_title(title: str) -> str:
    """清理標題：移除 dash/破折號之後的內容。"""
    # 移除 — (em dash) 或 - (hyphen) 後的內容
    for separator in [" — ", " - ", " – "]:
        if separator in title:
            return title.split(separator)[0].strip()
    return title


def enrich_analysis_with_links(analysis: dict, original_articles: list) -> None:
    """
    將原始新聞的 link 匹配添加到分析結果中，並清理標題。
    通過標題匹配（前 50 個字符）來找對應的新聞。
    """
    # 建立標題到新聞的映射（使用前 50 個字符作為 key）
    title_to_article = {}
    for article in original_articles:
        title = article.get("title", "")
        key = title[:50].lower()
        title_to_article[key] = article

    # 為每個分析結果添加 link 並清理標題
    for section in ["bullish", "bearish", "neutral"]:
        for item in analysis.get(section, []):
            original_title = item.get("title", "")
            key = original_title[:50].lower()

            # 匹配原始新聞並添加 link
            if key in title_to_article:
                matched_article = title_to_article[key]
                if "link" in matched_article:
                    item["link"] = matched_article["link"]

            # 清理標題
            item["title"] = clean_title(original_title)


def validate_analysis(data: dict) -> list[str]:
    """基本 schema 驗證，回傳錯誤訊息列表。"""
    errors = []
    required = ["ticker","company","analysis_date","source_file","summary","bullish","bearish","neutral"]
    for k in required:
        if k not in data:
            errors.append(f"缺少欄位: {k}")
    summary = data.get("summary", {})
    for k in ["total_articles","bullish_count","bearish_count","neutral_count","overall_sentiment","key_theme"]:
        if k not in summary:
            errors.append(f"summary 缺少: {k}")
    for section in ["bullish","bearish","neutral"]:
        items = data.get(section, [])
        count_key = f"{section}_count"
        if summary.get(count_key) != len(items):
            errors.append(f"count 不符：summary.{count_key}={summary.get(count_key)} 但陣列有 {len(items)} 筆")
    return errors


def _find_latest_news(ticker: str) -> tuple[Path | None, str | None]:
    """掃描 cache/ 下的所有日期子目錄，找最新的 {ticker}.json，並回傳 (path, scope)。"""
    cache_dir = SCRIPT_DIR / "cache"
    if not cache_dir.exists():
        return None, None

    date_dirs = sorted(
        [d for d in cache_dir.iterdir() if d.is_dir() and len(d.name) == 10],
        key=lambda d: d.name,
        reverse=True,
    )

    for d in date_dirs:
        # Check both holdings and competitors
        for scope in ["holdings", "competitors"]:
            path = d / scope / "news" / f"{ticker}.json"
            if path.exists():
                return path, scope
    return None, None


def analyze_ticker(ticker: str, client: anthropic.Anthropic) -> bool:
    """分析單一 Ticker，成功回傳 True。"""
    input_path, scope = _find_latest_news(ticker)

    if not input_path:
        print(f"  [{ticker}] ❌ 找不到輸入檔案")
        return False

    today = date.today().isoformat()
    # Output to today's date, keeping the same scope as the input file
    output_dir = SCRIPT_DIR / "cache" / today / scope / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ticker}_analysis.json"

    with open(input_path, encoding="utf-8") as f:
        raw = json.load(f)

    articles = raw.get("articles", [])
    if not articles:
        print(f"  [{ticker}] ⚠️  沒有新聞文章，跳過")
        return False

    company = COMPANY_NAMES.get(ticker, f"{ticker} Corp.")

    prompt = ANALYSIS_PROMPT.format(
        ticker=ticker,
        company=company,
        today=today,
        articles_json=json.dumps(articles, ensure_ascii=False, indent=2)
    )

    print(f"  [{ticker}] 🔍 分析中（{len(articles)} 篇文章）...")

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()

        # 清理可能的 markdown 代碼塊
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        result = json.loads(response_text)

    except json.JSONDecodeError as e:
        print(f"  [{ticker}] ❌ JSON 解析失敗: {e}")
        return False
    except Exception as e:
        print(f"  [{ticker}] ❌ API 呼叫失敗: {e}")
        return False

    # 添加 link 並清理標題
    enrich_analysis_with_links(result, articles)

    # 驗證
    errors = validate_analysis(result)
    if errors:
        print(f"  [{ticker}] ⚠️  驗證警告:")
        for err in errors:
            print(f"    - {err}")

    # 寫入
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    s = result.get("summary", {})
    print(
        f"  [{ticker}] ✅ 完成 "
        f"bull={s.get('bullish_count',0)} "
        f"bear={s.get('bearish_count',0)} "
        f"neut={s.get('neutral_count',0)} "
        f"→ {s.get('overall_sentiment','?')}"
    )
    return True


def main():
    if not API_KEY:
        print("❌ 請設定環境變數 ANTHROPIC_API_KEY")
        print("   範例：export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=API_KEY)

    # 決定要分析哪些 Ticker
    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
    else:
        # 掃描所有日期子目錄下的原始新聞 JSON（排除 _analysis.json）
        seen = set()
        cache_dir = SCRIPT_DIR / "cache"
        if cache_dir.exists():
            for date_dir in cache_dir.iterdir():
                if not date_dir.is_dir() or len(date_dir.name) != 10:
                    continue
                for scope in ["holdings", "competitors"]:
                    news_dir = date_dir / scope / "news"
                    if news_dir.exists():
                        for f in news_dir.glob('*.json'):
                            if not f.stem.endswith('_analysis'):
                                seen.add(f.stem)
        tickers = sorted(seen)

    print(f"\n{'='*50}")
    print(f"Daily News Analysis — {date.today().isoformat()}")
    print(f"分析目標：{len(tickers)} 個 Ticker")
    print(f"{'='*50}\n")

    success, failed = 0, []
    for ticker in tickers:
        if analyze_ticker(ticker, client):
            success += 1
        else:
            failed.append(ticker)

    print(f"\n{'='*50}")
    print(f"完成：{success}/{len(tickers)} 個 Ticker")
    if failed:
        print(f"失敗：{', '.join(failed)}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
