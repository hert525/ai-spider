"""Fetch finance/quant spider code from GitHub and append to seeds.py."""
from __future__ import annotations

import sys
import os
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx
from src.engine.adapters import CodeAdapter

FINANCE_REPOS = [
    {
        "name": "Yahoo Finance行情(yfinance)",
        "repo": "ranaroussi/yfinance",
        "files": ["yfinance/ticker.py", "yfinance/base.py", "yfinance/scrapers/quote.py"],
        "category": "finance",
        "icon": "📈",
        "target_url": "https://finance.yahoo.com",
        "tags": ["Yahoo Finance", "美股", "行情", "海外"],
        "difficulty": "easy",
    },
    {
        "name": "Investing.com全球市场(investpy)",
        "repo": "alvarobartt/investpy",
        "files": ["investpy/stocks.py", "investpy/crypto.py", "investpy/indices.py"],
        "category": "finance",
        "icon": "🌍",
        "target_url": "https://www.investing.com",
        "tags": ["Investing.com", "全球", "股票", "指数", "海外"],
        "difficulty": "medium",
    },
    {
        "name": "Finviz美股筛选器",
        "repo": "lit26/finvizfinance",
        "files": ["finvizfinance/screener/overview.py", "finvizfinance/quote.py"],
        "category": "finance",
        "icon": "🔍",
        "target_url": "https://finviz.com",
        "tags": ["Finviz", "美股", "筛选", "Screener"],
        "difficulty": "medium",
    },
    {
        "name": "CME期货期权数据",
        "repo": "sallamy2580/python-web-scrapping",
        "files": ["CME/CME Futures.py", "CME/cme_futures.py", "CME Futures.py"],
        "category": "finance",
        "icon": "📊",
        "target_url": "https://www.cmegroup.com",
        "tags": ["CME", "期货", "期权", "海外"],
        "difficulty": "medium",
    },
    {
        "name": "美国国债数据",
        "repo": "sallamy2580/python-web-scrapping",
        "files": ["US Treasury/US Treasury.py", "US Treasury.py"],
        "category": "finance",
        "icon": "🏛️",
        "target_url": "https://www.treasury.gov",
        "tags": ["美债", "国债", "Treasury", "海外"],
        "difficulty": "easy",
    },
    {
        "name": "WallStreetBets舆情",
        "repo": "sallamy2580/python-web-scrapping",
        "files": ["Reddit WallStreetBets/wallstreetbets.py", "Reddit WallStreetBets.py", "WallStreetBets.py"],
        "category": "finance",
        "icon": "🦍",
        "target_url": "https://www.reddit.com/r/wallstreetbets",
        "tags": ["Reddit", "WSB", "舆情", "美股"],
        "difficulty": "medium",
        "proxy_required": 1,
    },
    {
        "name": "MacroTrends宏观数据",
        "repo": "sallamy2580/python-web-scrapping",
        "files": ["MacroTrends/macrotrends.py", "MacroTrends.py"],
        "category": "finance",
        "icon": "📉",
        "target_url": "https://www.macrotrends.net",
        "tags": ["宏观", "历史数据", "MacroTrends"],
        "difficulty": "medium",
    },
    {
        "name": "Reuters路透社新闻",
        "repo": "sallamy2580/python-web-scrapping",
        "files": ["Reuters/reuters.py", "Reuters.py"],
        "category": "finance",
        "icon": "📰",
        "target_url": "https://www.reuters.com",
        "tags": ["路透社", "新闻", "财经", "海外"],
        "difficulty": "medium",
        "proxy_required": 1,
    },
    {
        "name": "Bloomberg彭博新闻",
        "repo": "sallamy2580/python-web-scrapping",
        "files": ["Bloomberg/bloomberg.py", "Bloomberg.py"],
        "category": "finance",
        "icon": "📰",
        "target_url": "https://www.bloomberg.com",
        "tags": ["彭博", "Bloomberg", "新闻", "海外"],
        "difficulty": "hard",
        "proxy_required": 1,
    },
    {
        "name": "Financial Times金融时报",
        "repo": "sallamy2580/python-web-scrapping",
        "files": ["Financial Times/financial_times.py", "Financial Times.py"],
        "category": "finance",
        "icon": "📰",
        "target_url": "https://www.ft.com",
        "tags": ["FT", "金融时报", "新闻", "海外"],
        "difficulty": "hard",
        "proxy_required": 1,
    },
    {
        "name": "SEC EDGAR财报(XBRL)",
        "repo": "eliangcs/pystock-crawler",
        "files": ["pystock_crawler/edgar.py", "pystock_crawler/loaders/edgar.py"],
        "category": "finance",
        "icon": "🏦",
        "target_url": "https://www.sec.gov/cgi-bin/browse-edgar",
        "tags": ["SEC", "EDGAR", "财报", "美股"],
        "difficulty": "medium",
    },
    {
        "name": "股票新闻情感分析",
        "repo": "dwallach1/Stocker",
        "files": ["stocker/stocker.py", "stocker/scraper.py", "stocker.py"],
        "category": "finance",
        "icon": "😊",
        "target_url": "",
        "tags": ["情感分析", "新闻", "Bloomberg", "SeekingAlpha"],
        "difficulty": "medium",
    },
    {
        "name": "加密货币交易所(ccxt)",
        "repo": "ccxt/ccxt",
        "files": ["python/ccxt/async_support/binance.py", "python/ccxt/base/exchange.py"],
        "category": "finance",
        "icon": "₿",
        "target_url": "https://www.binance.com",
        "tags": ["加密货币", "交易所", "Binance", "API"],
        "difficulty": "easy",
        "max_lines": 200,
    },
    {
        "name": "SEC基金持仓(13F)",
        "repo": "cpackard/fundholdings",
        "files": ["fundholdings/scraper.py", "fundholdings/fund_holdings.py"],
        "category": "finance",
        "icon": "📋",
        "target_url": "https://www.sec.gov/cgi-bin/browse-edgar",
        "tags": ["SEC", "13F", "基金持仓", "对冲基金"],
        "difficulty": "medium",
    },
]

BRANCHES = ["main", "master"]

def download_file(client: httpx.Client, repo: str, filepath: str, max_lines: int = 0) -> str | None:
    """Try downloading a file from GitHub raw, trying main then master."""
    encoded_path = urllib.parse.quote(filepath)
    for branch in BRANCHES:
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{encoded_path}"
        try:
            resp = client.get(url, follow_redirects=True, timeout=30)
            if resp.status_code == 200:
                text = resp.text
                if max_lines > 0:
                    lines = text.split('\n')
                    if len(lines) > max_lines:
                        text = '\n'.join(lines[:max_lines]) + '\n# ... truncated ...\n'
                print(f"  ✓ Downloaded {repo}/{filepath} ({branch})")
                return text
        except Exception as e:
            pass
    return None


def main():
    seeds_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'core', 'seeds.py')
    
    # Read existing seeds to get existing names
    with open(seeds_path, 'r') as f:
        seeds_content = f.read()
    
    # Extract existing names
    import re
    existing_names = set(re.findall(r'"name":\s*"([^"]+)"', seeds_content))
    print(f"Existing templates: {len(existing_names)}")
    
    new_entries = []
    
    with httpx.Client() as client:
        for item in FINANCE_REPOS:
            name = item["name"]
            if name in existing_names:
                print(f"⏭ Skipping {name} (already exists)")
                continue
            
            repo = item["repo"]
            max_lines = item.get("max_lines", 0)
            
            # Try each file, use first successful one
            code = None
            for filepath in item["files"]:
                code = download_file(client, repo, filepath, max_lines)
                if code:
                    break
            
            if not code:
                print(f"  ✗ Failed to download any file for {name}")
                continue
            
            # Detect format and wrap
            fmt = CodeAdapter.detect_format(code)
            wrapped = CodeAdapter.wrap(code, fmt)
            print(f"  Format: {fmt}, wrapped length: {len(wrapped)}")
            
            # Build description
            desc = f"基于 {repo} 项目的爬虫代码，自动适配为标准格式"
            
            entry = {
                "name": name,
                "description": desc,
                "category": item["category"],
                "icon": item["icon"],
                "target_url": item["target_url"],
                "mode": "code_generator",
                "code": wrapped,
                "tags": item["tags"],
                "difficulty": item["difficulty"],
                "author": "community",
                "source_url": f"https://github.com/{repo}",
            }
            if item.get("proxy_required"):
                entry["proxy_required"] = 1
            
            new_entries.append(entry)
            existing_names.add(name)
    
    if not new_entries:
        print("No new entries to add.")
        return
    
    print(f"\n{'='*50}")
    print(f"Adding {len(new_entries)} new templates...")
    
    # Build the text to append
    # Find the closing bracket of SEED_TEMPLATES
    # Insert before the final ']'
    insert_pos = seeds_content.rstrip().rfind(']')
    if insert_pos == -1:
        print("ERROR: Could not find end of SEED_TEMPLATES list")
        return
    
    # Check if there's content before the ]
    before = seeds_content[:insert_pos].rstrip()
    if not before.endswith(','):
        before += ','
    
    # Build new entries as text
    parts = []
    for entry in new_entries:
        code_repr = repr(entry["code"])
        tags_repr = repr(entry["tags"])
        lines = []
        lines.append('')
        lines.append(f'    # ═══════════════════════════════════════')
        lines.append(f'    # {entry["name"]}')
        lines.append(f'    # ═══════════════════════════════════════')
        lines.append(f'    {{')
        lines.append(f'        "name": {repr(entry["name"])},')
        lines.append(f'        "description": {repr(entry["description"])},')
        lines.append(f'        "category": {repr(entry["category"])},')
        lines.append(f'        "icon": {repr(entry["icon"])},')
        lines.append(f'        "target_url": {repr(entry["target_url"])},')
        lines.append(f'        "mode": "code_generator",')
        lines.append(f'        "code": {code_repr},')
        lines.append(f'        "tags": {tags_repr},')
        lines.append(f'        "difficulty": {repr(entry["difficulty"])},')
        lines.append(f'        "author": "community",')
        lines.append(f'        "source_url": {repr(entry["source_url"])},')
        if entry.get("proxy_required"):
            lines.append(f'        "proxy_required": 1,')
        lines.append(f'    }},')
        parts.append('\n'.join(lines))
    
    new_text = before + ''.join(parts) + '\n' + seeds_content[insert_pos:]
    
    with open(seeds_path, 'w') as f:
        f.write(new_text)
    
    print(f"Done! Added {len(new_entries)} templates.")


if __name__ == '__main__':
    main()
