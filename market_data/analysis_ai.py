#!/usr/bin/env python3
import datetime
import re
import sys

import anthropic

from dashboard import REC_INFO


def format_user_message(stock_info, stock_data, news):
    """格式化送給 Claude 的分析請求。"""
    symbol = stock_info['symbol']
    cost = stock_info['cost_basis']
    shares = stock_info['shares']
    category = stock_info.get('category', '')
    fund = stock_data.get('fundamental', {})
    tech = stock_data.get('technical', {})
    price = fund.get('current_price')

    pnl_str = 'N/A'
    if price and cost:
        pnl_pct = (price - cost) / cost * 100
        pnl_usd = (price - cost) * shares
        pnl_str = f"{pnl_pct:+.2f}% (${pnl_usd:+,.2f})"

    def fv(v, fmt='.2f', pre='', suf=''):
        if v is None:
            return 'N/A'
        try:
            return f"{pre}{v:{fmt}}{suf}"
        except (ValueError, TypeError):
            return str(v)

    def fp(v):
        if v is None:
            return 'N/A'
        return f"{v * 100:.1f}%"

    def fl(v):
        if v is None:
            return 'N/A'
        av = abs(v)
        sign = '-' if v < 0 else ''
        if av >= 1e12:
            return f"{sign}${av / 1e12:.2f}T"
        if av >= 1e9:
            return f"{sign}${av / 1e9:.2f}B"
        if av >= 1e6:
            return f"{sign}${av / 1e6:.2f}M"
        return f"{sign}${av:,.0f}"

    msg = f"""請分析以下股票持倉：

## 持倉資訊
- Ticker: {symbol} ({fund.get('company_name', 'N/A')})
- 成本: ${cost:.2f} | 股數: {shares:.0f} | 現價: {fv(price, pre='$')} | 未實現損益: {pnl_str}
- 產業: {fund.get('sector', 'N/A')} / {fund.get('industry', 'N/A')}
{f'- 持倉分類: {category}' if category else ''}

## 估值指標（{stock_data.get('fetch_time', '')}）
| 指標 | 數值 |
|------|------|
| 市值 | {fl(fund.get('marketCap'))} |
| EV | {fl(fund.get('enterpriseValue'))} |
| Trailing P/E | {fv(fund.get('trailingPE'))} |
| Forward P/E | {fv(fund.get('forwardPE'))} |
| P/S (TTM) | {fv(fund.get('priceToSalesTrailing12Months'))} |
| PEG | {fv(fund.get('pegRatio'))} |
| P/B | {fv(fund.get('priceToBook'))} |
| Beta | {fv(fund.get('beta'))} |
| 股息殖利率 | {fp(fund.get('dividendYield'))} |

## 成長與獲利
| 指標 | 數值 |
|------|------|
| 營收成長 YoY | {fp(fund.get('revenueGrowth'))} |
| 盈餘成長 YoY | {fp(fund.get('earningsGrowth'))} |
| 總營收 TTM | {fl(fund.get('totalRevenue'))} |
| 毛利率 | {fp(fund.get('grossMargins'))} |
| 營業利益率 | {fp(fund.get('operatingMargins'))} |
| 淨利率 | {fp(fund.get('profitMargins'))} |
| EPS Trailing | {fv(fund.get('trailingEps'))} |
| EPS Forward | {fv(fund.get('forwardEps'))} |
| ROE | {fp(fund.get('returnOnEquity'))} |
| ROA | {fp(fund.get('returnOnAssets'))} |

## 現金流與負債
| 指標 | 數值 |
|------|------|
| FCF TTM | {fl(fund.get('freeCashflow'))} |
| FCF Margin | {fv(fund.get('fcf_margin'), suf='%')} |
| 營業現金流 | {fl(fund.get('operatingCashflow'))} |
| 總負債 | {fl(fund.get('totalDebt'))} |
| 現金 | {fl(fund.get('totalCash'))} |
| Net Debt | {fl(fund.get('net_debt'))} |
| D/E | {fv(fund.get('debtToEquity'))} |
| 流動比率 | {fv(fund.get('currentRatio'))} |

## 技術面數據
| 指標 | 數值 |
|------|------|
| 現價 | {fv(price, pre='$')} |
| 50日均線 | {fv(tech.get('ma50'), pre='$')} |
| 200日均線 | {fv(tech.get('ma200'), pre='$')} |
| 52週高點 | {fv(tech.get('high_52w'), pre='$')} |
| 52週低點 | {fv(tech.get('low_52w'), pre='$')} |
| 近3月漲跌 | {fv(tech.get('change_3mo_pct'), suf='%')} |
| 20日均量 | {fv(tech.get('avg_vol_20d'), ',.0f')} |
| 今日量 | {fv(tech.get('current_vol'), ',.0f')} |
"""

    if news:
        msg += "\n## 近期消息（請特別區分利多與利空）\n"
        for i, n in enumerate(news, 1):
            msg += (
                f"\n{i}. **{n['title']}**\n"
                f"   來源: {n.get('publisher', 'N/A')} | {n.get('date', '')}\n"
            )
    else:
        msg += "\n## 近期消息\n暫無最新消息。\n"

    msg += (
        "\n\n請依照你的分析框架，輸出完整的投資評估報告。"
        "請特別標註利多與利空消息，並評估其對股價的潛在影響。"
    )
    return msg


def analyze_with_claude(stock_info, stock_data, news, system_prompt, config):
    """呼叫 Claude API 分析股票。"""
    symbol = stock_info['symbol']
    model = config.get('model', 'claude-sonnet-4-6')
    max_tokens = config.get('max_tokens', 4096)

    print(f"    [AI]   Claude 分析 {symbol} ...")
    client = anthropic.Anthropic()
    user_msg = format_user_message(stock_info, stock_data, news)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_msg}],
        )
        text = response.content[0].text
        summary = extract_summary(text)
        print(f"           -> {REC_INFO.get(summary['recommendation'], {}).get('label', '?')} "
              f"(tokens: {response.usage.input_tokens}+{response.usage.output_tokens})")
        return {
            'analysis': text,
            'recommendation': summary['recommendation'],
            'confidence': summary['confidence'],
            'scores': summary['scores'],
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens,
            'analysis_time': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        }

    except anthropic.AuthenticationError:
        _api_error(
            "API 金鑰無效！\n"
            "  請至 https://console.anthropic.com/ 確認你的 API 金鑰是否正確。\n"
            "  檢查 .env 檔案中的 ANTHROPIC_API_KEY 值。"
        )
    except anthropic.PermissionDeniedError:
        _api_error(
            "API 金鑰權限不足。\n"
            "  可能原因:\n"
            "  1. 金鑰尚未啟用\n"
            "  2. 帳號額度已用完\n"
            "  3. 該金鑰無權使用此模型\n"
            "  請至 https://console.anthropic.com/ 確認。"
        )
    except anthropic.NotFoundError:
        _api_error(
            f"找不到模型 '{model}'。\n"
            "  請在 config.json 中更新 model 欄位。\n"
            "  可用模型: claude-sonnet-4-6, claude-haiku-4-5-20251001"
        )
    except anthropic.RateLimitError:
        _api_error(
            "API 呼叫頻率超限！\n"
            "  請等待 1-2 分鐘後重試。\n"
            "  或在 config.json 中改用較便宜的模型 (claude-haiku-4-5-20251001)。"
        )
    except anthropic.BadRequestError as e:
        _api_error(
            f"請求格式錯誤: {e.message}\n"
            "  可能原因: 輸入資料太長。\n"
            "  解決: 在 config.json 中減少 news_count 值。"
        )
    except anthropic.APIConnectionError:
        _api_error(
            "無法連接 Anthropic API。\n"
            "  請確認:\n"
            "  1. 網路連線正常\n"
            "  2. 沒有防火牆/VPN 阻擋\n"
            "  3. https://api.anthropic.com 可正常存取"
        )
    except anthropic.APIStatusError as e:
        _api_error(
            f"API 伺服器錯誤 (HTTP {e.status_code})\n"
            f"  訊息: {e.message}\n"
            "  請至 https://status.anthropic.com/ 確認服務狀態。"
        )
    return None  # unreachable, _api_error exits


def _api_error(msg):
    """顯示 API 錯誤並退出。"""
    print(f"\n{'=' * 50}")
    print("  API 錯誤")
    print(f"{'=' * 50}\n")
    print(f"  {msg}\n")
    sys.exit(1)


def extract_summary(text):
    """從 Claude 回覆中解析推薦、信心與評分。"""
    rec = 'unknown'
    first_500 = text[:500]
    if '加倉' in first_500 or '加碼' in first_500:
        rec = 'add'
    elif '平倉' in first_500:
        rec = 'close'
    elif '減倉' in first_500 or '減碼' in first_500:
        rec = 'reduce'
    elif '持有' in first_500 or '維持' in first_500:
        rec = 'hold'

    conf = 'medium'
    if re.search(r'信心[^高低中]{0,5}高', first_500):
        conf = 'high'
    elif re.search(r'信心[^高低中]{0,5}低', first_500):
        conf = 'low'

    scores = {}
    for label, key in [('基本面', 'fundamental'), ('技術面', 'technical'), ('風險', 'risk')]:
        m = re.search(rf'{label}[^0-9]{{0,10}}(\d)\s*[/／]\s*5', text)
        if m:
            scores[key] = int(m.group(1))

    return {'recommendation': rec, 'confidence': conf, 'scores': scores}
