#!/usr/bin/env python3
import datetime
import json
import os
import re
import time
import urllib.request
from pathlib import Path

import yfinance as yf

from .information_ai import analyze_news_with_gemini as _analyze_news_with_gemini_impl


def analyze_news_with_gemini(
    *,
    symbol,
    articles,
    cache_dir,
    scope="holdings",
    company_name="",
    env_get=os.environ.get,
    sleep_fn=time.sleep,
    print_fn=print,
):
    return _analyze_news_with_gemini_impl(
        symbol=symbol,
        articles=articles,
        cache_dir=cache_dir,
        scope=scope,
        company_name=company_name,
        env_get=env_get,
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )


def parse_yf_news(item):
    if not isinstance(item, dict):
        return None
    if "content" in item and isinstance(item.get("content"), dict):
        c = item["content"]
        url = ""
        if isinstance(c.get("canonicalUrl"), dict):
            url = c["canonicalUrl"].get("url", "")
        publisher = ""
        if isinstance(c.get("provider"), dict):
            publisher = c["provider"].get("displayName", "")
        title = c.get("title", "")
        if title:
            return {
                "title": title,
                "link": url,
                "publisher": publisher,
                "date": c.get("pubDate", ""),
                "_source": "yfinance",
            }

    title = item.get("title", "")
    if not title:
        return None
    pub_time = item.get("providerPublishTime")
    date_str = ""
    if pub_time:
        try:
            date_str = datetime.datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return {
        "title": title,
        "link": item.get("link", ""),
        "publisher": item.get("publisher", ""),
        "date": date_str,
        "_source": "yfinance",
    }


def fetch_finnhub_news(symbol, api_key, *, today=None):
    base_day = today or datetime.date.today()
    from_date = (base_day - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    to_date = base_day.strftime("%Y-%m-%d")
    url = (
        f"https://finnhub.io/api/v1/company-news"
        f"?symbol={symbol}&from={from_date}&to={to_date}&token={api_key}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode("utf-8"))

    results = []
    for item in data:
        dt = item.get("datetime", 0)
        date_str = ""
        if dt:
            try:
                date_str = datetime.datetime.fromtimestamp(dt).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        headline = item.get("headline", "")
        summary = item.get("summary", "")
        title = headline
        if summary and summary != headline:
            title = f"{headline} — {summary[:120]}"
        if headline:
            results.append(
                {
                    "title": title,
                    "link": item.get("url", ""),
                    "publisher": item.get("source", ""),
                    "date": date_str,
                    "_source": "finnhub",
                }
            )
    return results


def parse_news_date(date_str):
    if not date_str:
        return None
    if isinstance(date_str, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(date_str)
        except Exception:
            return None
    if not isinstance(date_str, str):
        return None

    for fmt in (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ):
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    return None


_SOURCE_TIER1 = {
    "reuters",
    "bloomberg",
    "wsj",
    "wall street journal",
    "cnbc",
    "financial times",
    "ft",
    "barrons",
    "barron's",
    "the economist",
    "associated press",
    "ap news",
    "marketwatch",
    "nytimes",
    "new york times",
    "washington post",
}
_SOURCE_TIER2 = {
    "yahoo finance",
    "yahoo",
    "seeking alpha",
    "benzinga",
    "investopedia",
    "motley fool",
    "the motley fool",
    "investor place",
    "investorplace",
    "tipranks",
    "zacks",
    "morningstar",
    "thestreet",
}


def score_news(articles, symbol, company_name=""):
    now = datetime.datetime.now()
    symbol_upper = symbol.upper()
    company_lower = company_name.lower().strip() if company_name else ""
    company_short = re.sub(
        r"\s*[,.]?\s*(inc|corp|ltd|llc|plc|co|company|group|holdings?)\.?\s*$",
        "",
        company_lower,
        flags=re.IGNORECASE,
    ).strip()

    for art in articles:
        score = 1
        title = art.get("title", "")
        title_lower = title.lower()
        publisher = art.get("publisher", "").lower().strip()

        ticker_pat = re.compile(r"(?:^|[\s($])" + re.escape(symbol_upper) + r"(?:[\s),:;.!?]|$)")
        if ticker_pat.search(title):
            score *= 2
        elif company_short and company_short in title_lower:
            score *= 1.8
        else:
            score *= 0

        if any(t in publisher for t in _SOURCE_TIER1):
            score *= 3
        elif any(t in publisher for t in _SOURCE_TIER2):
            score *= 2
        elif publisher:
            score *= 1
        else:
            score *= 0.8

        dt = parse_news_date(art.get("date", ""))
        if dt:
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            age_hours = max(0, (now - dt).total_seconds()) / 3600
            score *= max(2 - age_hours // 24 * 0.2, 0)
        else:
            score *= 0.4

        src = art.get("_source", "")
        if src == "finnhub":
            score *= 2
        elif src == "yfinance":
            score *= 1.5
        else:
            score *= 1.2

        art["_score"] = score

    articles.sort(key=lambda a: a.get("_score", 0.0), reverse=True)
    return [a for a in articles if a.get("_score", 0.0) > 0]


def fetch_news(
    symbol,
    count=1000,
    cache_mgr=None,
    company_name="",
    *,
    cache_dir=None,
    env_get=os.environ.get,
    ticker_factory=yf.Ticker,
    fetch_finnhub_news_fn=fetch_finnhub_news,
    parse_yf_news_fn=parse_yf_news,
    score_news_fn=score_news,
    analyze_news_fn=analyze_news_with_gemini,
    print_fn=print,
):
    if cache_mgr:
        cached = cache_mgr.get("news", symbol)
        if cached and "articles" in cached:
            print_fn(f"    [Cache HIT] {symbol} 新聞 ({len(cached['articles'])} 則)")
            analyze_news_fn(
                symbol=symbol,
                articles=cached["articles"],
                scope=cache_mgr.scope,
                cache_dir=cache_dir or Path("cache"),
                company_name=company_name,
                env_get=env_get,
                print_fn=print_fn,
            )
            return cached["articles"]

    news = []
    finnhub_key = env_get("FINNHUB_API_KEY")
    if finnhub_key:
        try:
            fh = fetch_finnhub_news_fn(symbol, finnhub_key)
            news.extend(fh)
            print_fn(f"    [News] Finnhub: {len(fh)} 則")
        except Exception as e:
            print_fn(f"    [News] Finnhub 失敗: {e}")
    else:
        print_fn("    [News] Finnhub 未設定 (可在 .env 加入 FINNHUB_API_KEY)")

    try:
        stock = ticker_factory(symbol)
        raw = stock.news or []
        yf_count = 0
        for item in raw[:count]:
            parsed = parse_yf_news_fn(item)
            if parsed:
                news.append(parsed)
                yf_count += 1
        if yf_count:
            print_fn(f"    [News] yfinance: {yf_count} 則")
    except Exception:
        pass

    seen = set()
    unique = []
    for item in news:
        key = item.get("title", "")[:60].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    print_fn(f"    [News] {symbol} 合計: {len(unique)} 則（去重後）")

    unique = score_news_fn(unique, symbol, company_name)
    result = unique[:count]
    for art in result:
        art["symbol"] = symbol

    if cache_mgr and result:
        cache_mgr.set("news", symbol, {"articles": result})
        print_fn(f"    [Cache SAVE] {symbol} 新聞")
        analyze_news_fn(
            symbol=symbol,
            articles=result,
            scope=cache_mgr.scope,
            cache_dir=cache_dir or Path("cache"),
            company_name=company_name,
            env_get=env_get,
            print_fn=print_fn,
        )
    elif len(result) == 0:
        print_fn(f"    [Cache] {symbol} 沒有新聞可供快取")

    return result
