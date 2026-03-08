#!/usr/bin/env python3
import os

import requests


def translate_summary_with_gemini_v1(
    text,
    *,
    env_get=os.environ.get,
    requests_post=requests.post,
    print_fn=print,
):
    if not text:
        return text

    gemini_key = env_get("GEMINI_API_KEY")
    if not gemini_key:
        return text

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={gemini_key}"
    prompt = f"請將這段公司營運概況翻譯成精煉、流暢的繁體中文，保留專業術語，不要有其他多餘的寒暄或解釋內容：\n\n{text}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    try:
        res = requests_post(url, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if "candidates" in data and data["candidates"]:
                translated = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if translated:
                    return translated
        else:
            print_fn(f"    [翻譯失敗] HTTP {res.status_code}: {res.text[:100]}")
    except Exception as e:
        print_fn(f"    [翻譯錯誤] {e}")

    return text


def translate_summary_with_gemini(*args, **kwargs):
    return translate_summary_with_gemini_v1(*args, **kwargs)
