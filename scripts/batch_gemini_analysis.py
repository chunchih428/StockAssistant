import os
import sys
import json
import time
from pathlib import Path
from datetime import date
from pydantic import BaseModel, Field

# Ensure we load the .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# 設定 Gemini Model
# 依照使用者需求填寫 gemini 3.1 pro，若 Google 實際 API 端點名稱不同 (如 gemini-2.5-pro 或 gemini-1.5-pro)，請自行修改此變數。
MODEL_NAME = "gemini-3.1-flash-lite-preview" # 改用 flash 以避免超時與卡死的問題

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("❌ 請設定環境變數 GEMINI_API_KEY (可加至 .env 檔案中)")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("❌ 請先安裝套件: pip install google-genai pydantic")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# ==========================================
# 定義 Structured Output 的 Pydantic Schema
# ==========================================
class ArticleSummary(BaseModel):
    rank: int
    title: str
    publisher: str
    date: str
    impact: str
    category: str = Field(description="[重要] 分類名稱必須翻譯成『繁體中文』，例如：'雲端與人工智慧'、'財報分析'、'併購擴張' 等")
    reason: str = Field(description="詳細分析段落，包含具體人名、金額等，必須使用繁體中文")

class SummaryObj(BaseModel):
    total_articles: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    overall_sentiment: str
    key_theme: str = Field(description="一句話概括最重要的主題，必須使用繁體中文")

class AnalysisSchema(BaseModel):
    ticker: str
    company: str
    analysis_date: str
    source_file: str
    summary: SummaryObj
    bullish: list[ArticleSummary]
    bearish: list[ArticleSummary]
    neutral: list[ArticleSummary]

# ==========================================
# 分析邏輯
# ==========================================
PROMPT_TEMPLATE = """
你是一位專業的股票新聞情緒分析師。

給定以下股票代碼 {ticker} 的新聞 JSON，請逐篇分析每篇新聞對該股價的影響方向與情緒。

## 分析規則
1. 如果有新聞重複主題或內容重覆，選一個涵蓋面較廣的新聞作為代表，並在 reason 中說明為何選這篇作為代表。
2. 影響力方向：bullish（利多）、bearish（利空）、neutral（中性），每類最多列出 8 篇新聞，請針對該公司本身的股價影響判斷。
3. 影響力分級：high / medium / low。
4. 繁體中文分類 (category)：你必須將 category 的回傳內容寫成「繁體中文」，例如：「高層異動」、「財報公布」、「市場擴張」等。絕對不能是純英文。
5. reason 與 key_theme 必須使用「繁體中文」撰寫，並盡可能提供財務分析師會關注的細節（人名、金額、因果鏈）。
6. 在中文字與英文字母或數字之間，必須加一個半形空格。例如：「Google 宣布與 Microsoft 合作」，而不是「Google宣布與Microsoft合作」。

## 輸入資料
{news_data}
"""

def process_file(file_path: Path):
    ticker = file_path.stem
    print(f"處理: {ticker}...")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    if not articles:
        print(f"  [{ticker}] ⚠️ 無新聞，跳過")
        return False

    today_str = date.today().isoformat()
    # 取前 80 篇新聞避免 context token 太長
    news_subset = articles[:80]
    news_json = json.dumps({"ticker": ticker, "articles": news_subset}, ensure_ascii=False, indent=2)
    prompt = PROMPT_TEMPLATE.format(ticker=ticker, news_data=news_json)
    output_path = file_path.parent / f"{ticker}_analysis.json"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AnalysisSchema,
                    temperature=0.2, # 較低的溫度確保結構嚴謹
                )
            )

            parsed_result = json.loads(response.text)
            # 固定寫入必要的額外欄位或修正
            parsed_result["_schema_version"] = "1.1"
            parsed_result["source_file"] = f"cache/{today_str}/competitors/news/{ticker}.json"

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed_result, f, ensure_ascii=False, indent=2)

            print(f"  ✅ {ticker} 分析完成, 保存在 {output_path.name}")
            return True
        except Exception as e:
            print(f"  ⚠️ {ticker} 發生錯誤 (嘗試 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5) # 發生錯誤時退避一下
            else:
                print(f"  ❌ {ticker} 最終失敗")
                return False

def main():
    today_str = date.today().isoformat()
    # 我們設定為巡覽 holdings 的新聞目錄
    target_dir = Path("cache") / today_str / "holdings" / "news"
    if not target_dir.exists():
        print(f"❌ 找不到目錄: {target_dir}")
        return

    jsons = list(target_dir.glob("*.json"))
    # 只挑選尚未分析過的新聞檔案
    raw_files = [f for f in jsons if not f.name.endswith("_analysis.json")]

    # 我們設定為巡覽 competitor 的新聞目錄
    target_dir = Path("cache") / today_str / "competitors" / "news"
    if not target_dir.exists():
        print(f"❌ 找不到目錄: {target_dir}")
        return

    jsons = list(target_dir.glob("*.json"))
    # 只挑選尚未分析過的新聞檔案
    raw_files += [f for f in jsons if not f.name.endswith("_analysis.json")]

    missing_count = 0
    for f in raw_files:
        analysis_file = target_dir / f"{f.stem}_analysis.json"
        if not analysis_file.exists():
            missing_count += 1

    print(f"發現 {len(raw_files)} 個新聞檔案，其中 {missing_count} 個尚未分析。")
    if missing_count == 0:
        print("沒有需要分析的檔案。")
        return

    done_count = 0
    for f in raw_files:
        analysis_file = target_dir / f"{f.stem}_analysis.json"
        if not analysis_file.exists():
            if process_file(f):
                done_count += 1
            # 避免 API Rate Limit (依您的 tier 調整)
            time.sleep(2)

    print(f"\n批次處理完畢！本次成功處理了 {done_count} 筆資料。")

if __name__ == "__main__":
    main()
