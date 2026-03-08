# 项目结构说明

## 📁 目录结构

```
PersonalFinanceCC/
├── stock_assistant.py       # 主程序入口
├── dashboard.py             # 仪表板生成模块
├── requirements.txt         # Python 依赖
├── .env                     # 环境变量（API keys）
│
├── config/                  # 配置文件
│   ├── config.json         # 主配置文件
│   ├── competitors.json    # 竞品配置
│   └── company_names.json  # 公司名称映射
│
├── data/                    # 数据文件
│   ├── holdings.csv            # 用户持股数据
│   ├── ANALYSIS_SUMMARY.txt        # 新闻分析报告
│   └── COMPETITORS_SUMMARY.txt     # 竞品分析报告
│
├── scripts/                 # 工具脚本
│   ├── daily_news_analysis.py      # 新闻分析脚本
│   ├── generate_competitors.py     # 竞品生成工具
│   └── update_analysis.py          # 更新分析工具
│
├── cache/                   # 数据缓存
│   ├── fundamental/        # 基本面数据缓存
│   ├── technical/          # 技术面数据缓存
│   └── news/              # 新闻数据缓存
│
├── output/                  # 输出文件
│   ├── index.html          # 生成的仪表板
│   └── results.json        # 分析结果
│
├── news-analyzer-skill/     # 新闻分析技能
│   ├── SKILL.md
│   ├── references/
│   └── scripts/
│
└── competitor-analyzer-skill/  # 竞品分析技能
    ├── SKILL.md
    └── scripts/
```

## 🚀 使用说明

### 主程序
```bash
# 分析所有持股
python stock_assistant.py

# 只分析指定股票
python stock_assistant.py AAPL TSLA

# 打开上次生成的报告
python stock_assistant.py --open

# 强制刷新所有数据
python stock_assistant.py --fresh
```

### 工具脚本
```bash
# 生成新闻分析
python scripts/daily_news_analysis.py

# 生成竞品配置
python scripts/generate_competitors.py

# 更新分析文件
python scripts/update_analysis.py
```

## ⚙️ 配置文件

### config/config.json
主配置文件，包含：
- API 设置
- 缓存 TTL 设置
- 模型选择

### config/competitors.json
竞品映射配置，格式：
```json
{
  "AAPL": ["MSFT", "GOOGL", "AMZN"],
  "TSLA": ["F", "GM", "NIO"]
}
```

### data/holdings.csv
用户持股数据，格式：
```csv
股名,股數,買價,類別
AAPL,100,150.00,長期霸主
TSLA,50,200.00,中期題材(股票)
```

## 📊 输出文件

- `index.html` - 交互式仪表板
- `output/results.json` - 完整分析结果
- `data/ANALYSIS_SUMMARY.txt` - 新闻分析摘要
- `data/COMPETITORS_SUMMARY.txt` - 竞品分析摘要
