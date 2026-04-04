#!/usr/bin/env python3
import datetime
import json
import os
import re
import time
from pathlib import Path

from typing import Literal

from pydantic import BaseModel, Field


class ArticleSummary(BaseModel):
    rank: int
    title: str
    publisher: str
    date: str
    impact: str
    category: str = Field(description="新聞主題分類，例如：產品發布、財報、法規、市場動態")
    reason: str = Field(description="判斷該新聞影響方向與強度的關鍵理由")


class SummaryObj(BaseModel):
    total_articles: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    overall_sentiment: Literal['strongly_bullish', 'bullish', 'neutral', 'mixed', 'bearish', 'strongly_bearish']
    key_theme: str = Field(description="一句話總結近期消息面的主要驅動因素")


class AnalysisSchema(BaseModel):
    ticker: str
    company: str
    analysis_date: str
    source_file: str
    summary: SummaryObj
    bullish: list[ArticleSummary]
    bearish: list[ArticleSummary]
    neutral: list[ArticleSummary]


NEWS_ANALYSIS_PROMPT_TEMPLATE = """
你是一位專業的股票新聞情緒分析師。

給定以下股票代碼 {ticker} 的新聞 JSON，請逐篇分析每篇新聞對該股價的影響方向與情緒。

## 分析規則
1. 如果有新聞重複主題或內容，選一個涵蓋面較廣的新聞作為代表，並在 reason 中彙整細節，並說明為何選這篇作為代表。
2. 影響力方向：bullish（利多）、bearish（利空）、neutral（中性），每類最多列出 8 篇新聞，請針對該公司本身的股價影響判斷。
3. 影響力分級：high / medium / low。
4. 繁體中文分類 (category)：你必須將 category 的回傳內容寫成「繁體中文」，例如：「高層異動」、「財報公布」、「市場擴張」等。絕對不能是純英文。
5. reason 與 key_theme 必須使用「繁體中文」撰寫，並盡可能提供財務分析師會關注的細節（人名、金額、因果鏈）。
6. 在中文字與英文字母或數字之間，必須加一個半形空格。例如：「Google 宣布與 Microsoft 合作」，而不是「Google宣布與Microsoft合作」。
7. overall_sentiment 必須從以下六個選項中選一個，不得使用其他值：
   - strongly_bullish：重大正面催化劑（財報大幅超預期、多家上調目標價、重大合約/併購）
   - bullish：正面消息占多數，無顯著利空
   - neutral：無重大消息，或正負小幅抵銷，方向不明確
   - mixed：同時存在顯著利多與利空，多空並陳
   - bearish：負面消息占多數
   - strongly_bearish：重大負面催化劑（財報大幅低於預期、重大訴訟/監管制裁、高層異動/醜聞）

## 輸入資料
{news_data}
"""


def extract_json_text(text):
    if not text:
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def analyze_news_with_gemini_v1(*, symbol, articles, cache_dir, scope="holdings", company_name="", env_get=os.environ.get, sleep_fn=time.sleep, print_fn=print, genai_module=None, genai_types_module=None, today=None):  # pragma: no cover
    if not articles:
        return

    today_date = today or datetime.date.today()
    analysis_dir = Path(cache_dir) / today_date.isoformat() / scope / "news"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    output_path = analysis_dir / f"{symbol}_analysis.json"
    if output_path.exists():
        return

    api_key = env_get("GEMINI_API_KEY")
    if not api_key:
        return

    if genai_module is None or genai_types_module is None:
        try:
            from google import genai as _genai
            from google.genai import types as _types
        except ImportError:
            print_fn("    [News Analysis] 跳過：缺少 google-genai 套件")
            return
        genai_module = _genai
        genai_types_module = _types

    news_subset = []
    for a in articles[:80]:
        news_subset.append(
            {
                "title": a.get("title", ""),
                "link": a.get("link", ""),
                "publisher": a.get("publisher", ""),
                "date": a.get("date", ""),
            }
        )

    news_json = json.dumps({"ticker": symbol, "articles": news_subset}, ensure_ascii=False, indent=2)
    prompt = NEWS_ANALYSIS_PROMPT_TEMPLATE.format(ticker=symbol, news_data=news_json)
    model_name = "gemini-3.1-flash-lite-preview"
    try:
        client = genai_module.Client(api_key=api_key)
    except Exception as e:
        print_fn(f"    [News Analysis] 跳過：Gemini 初始化失敗 ({e})")
        return
    today_str = today_date.isoformat()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print_fn(f"    [News Analysis] {symbol}")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types_module.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AnalysisSchema,
                    temperature=0.2,
                ),
            )
            parsed_result = json.loads(extract_json_text(response.text))
            parsed_result["_schema_version"] = "1.1"
            parsed_result["ticker"] = symbol
            parsed_result["company"] = company_name or parsed_result.get("company", symbol)
            parsed_result["analysis_date"] = today_str
            parsed_result["source_file"] = f"cache/{today_str}/{scope}/news/{symbol}.json"

            output_path.write_text(
                json.dumps(parsed_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print_fn(f"    [News Analysis] 完成: {output_path.name}")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                print_fn(f"    [News Analysis] {symbol} 嘗試 {attempt + 1} 失敗: {e}，正在重試...")
                sleep_fn(2)
            else:
                print_fn(f"    [News Analysis] {symbol} 失敗: {e}")


def analyze_news_with_gemini(*args, **kwargs):
    return analyze_news_with_gemini_v1(*args, **kwargs)
