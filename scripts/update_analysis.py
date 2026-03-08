#!/usr/bin/env python3
"""
更新现有的 analysis 文件：添加 link 并清理标题
不需要重新调用 API，直接处理现有文件
"""

import json
from pathlib import Path
from datetime import date


def clean_title(title: str) -> str:
    """清理標題：移除 dash/破折號之後的內容。"""
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


def update_analysis_file(ticker: str, today_str: str, scope: str = "holdings") -> bool:
    """更新單一 ticker 的 analysis 文件。"""
    cache_dir = Path("cache")
    today_dir = cache_dir / today_str / scope / "news"

    analysis_path = today_dir / f"{ticker}_analysis.json"
    news_path = today_dir / f"{ticker}.json"

    if not analysis_path.exists():
        print(f"  [{ticker}] ❌ 找不到 analysis 文件: {analysis_path}")
        return False

    if not news_path.exists():
        print(f"  [{ticker}] ❌ 找不到原始新聞文件: {news_path}")
        return False

    # 讀取文件
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    with open(news_path, encoding="utf-8") as f:
        news_data = json.load(f)

    articles = news_data.get("articles", [])

    # 更新
    enrich_analysis_with_links(analysis, articles)

    # 寫回
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    bull_count = len(analysis.get("bullish", []))
    bear_count = len(analysis.get("bearish", []))
    neut_count = len(analysis.get("neutral", []))

    print(f"  [{ticker}] ✅ 已更新 (bull={bull_count}, bear={bear_count}, neut={neut_count})")
    return True


def main():
    import sys

    today_str = date.today().isoformat()
    cache_dir = Path("cache") / today_str
    
    # 支援 holdings 和 competitors 兩個目錄
    scopes = ["holdings", "competitors"]
    
    total_success = 0
    total_files = 0

    # 如果有指定 ticker，只更新指定的
    if len(sys.argv) > 1:
        tickers = sys.argv[1:]
        print(f"\n更新 {len(tickers)} 個指定 Ticker 的 analysis 文件...\n")
        files_to_process = []
        for ticker in tickers:
            for scope in scopes:
                if (cache_dir / scope / "news" / f"{ticker}_analysis.json").exists():
                    files_to_process.append((ticker, scope))
                    break
        
        for ticker, scope in files_to_process:
            total_files += 1
            if update_analysis_file(ticker, today_str, scope):
                total_success += 1
    else:
        # 自動掃描所有 _analysis.json 文件
        files_to_process = []
        for scope in scopes:
            news_dir = cache_dir / scope / "news"
            if news_dir.exists():
                analysis_files = list(news_dir.glob("*_analysis.json"))
                for f in analysis_files:
                    ticker = f.stem.replace("_analysis", "")
                    files_to_process.append((ticker, scope))
                    
        total_files = len(files_to_process)
        if total_files == 0:
            print("❌ 沒有找到任何 analysis 文件")
            return
            
        print(f"\n更新 {total_files} 個 analysis 文件...\n")
        
        for ticker, scope in files_to_process:
            if update_analysis_file(ticker, today_str, scope):
                total_success += 1

    print(f"\n✅ 完成！成功更新 {total_success}/{total_files} 個文件")

if __name__ == "__main__":
    main()
