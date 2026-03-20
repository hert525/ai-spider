"""Fetch community spider code from GitHub repos and append to seeds.py."""
from __future__ import annotations

import sys
import os
import re
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from src.engine.adapters import CodeAdapter

NEW_REPOS = [
    {
        "name": "小红书笔记爬虫",
        "repo": "NanmiCoder/MediaCrawler",
        "files": ["media_platform/xhs/core.py", "media_platform/xhs/client.py"],
        "category": "social",
        "icon": "📕",
        "target_url": "https://www.xiaohongshu.com",
        "tags": ["小红书", "社交", "笔记", "中文"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "抖音视频爬虫",
        "repo": "NanmiCoder/MediaCrawler",
        "files": ["media_platform/douyin/core.py", "media_platform/douyin/client.py"],
        "category": "social",
        "icon": "🎵",
        "target_url": "https://www.douyin.com",
        "tags": ["抖音", "短视频", "中文"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "快手视频爬虫",
        "repo": "NanmiCoder/MediaCrawler",
        "files": ["media_platform/kuaishou/core.py", "media_platform/kuaishou/client.py"],
        "category": "social",
        "icon": "🎬",
        "target_url": "https://www.kuaishou.com",
        "tags": ["快手", "短视频", "中文"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "百度贴吧爬虫",
        "repo": "NanmiCoder/MediaCrawler",
        "files": ["media_platform/tieba/core.py", "media_platform/tieba/client.py"],
        "category": "social",
        "icon": "💬",
        "target_url": "https://tieba.baidu.com",
        "tags": ["贴吧", "社区", "中文"],
        "difficulty": "medium",
        "use_browser": 1,
    },
    {
        "name": "淘宝商品爬虫",
        "repo": "Jack-Cherish/python-spider",
        "files": ["taobao/taobao.py", "taobao/main.py"],
        "category": "ecommerce",
        "icon": "🛍️",
        "target_url": "https://www.taobao.com",
        "tags": ["淘宝", "电商", "中文"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "12306余票查询",
        "repo": "Jack-Cherish/python-spider",
        "files": ["12306/12306.py", "12306/main.py"],
        "category": "life",
        "icon": "🚄",
        "target_url": "https://www.12306.cn",
        "tags": ["12306", "火车票", "出行"],
        "difficulty": "medium",
    },
    {
        "name": "抖音视频下载",
        "repo": "Jack-Cherish/python-spider",
        "files": ["douyin/douyin.py", "douyin/main.py"],
        "category": "social",
        "icon": "📱",
        "target_url": "https://www.douyin.com",
        "tags": ["抖音", "下载", "视频"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "小红书数据采集",
        "repo": "cv-cat/Spider_XHS",
        "files": ["spider_xhs.py", "main.py", "xhs.py", "core.py", "spider.py"],
        "category": "social",
        "icon": "📕",
        "target_url": "https://www.xiaohongshu.com",
        "tags": ["小红书", "采集", "运营"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "V2EX热帖",
        "repo": "Nyloner/Nyspider",
        "files": ["v2ex/spider.py", "v2ex/v2ex.py", "v2ex/main.py"],
        "category": "social",
        "icon": "💻",
        "target_url": "https://www.v2ex.com",
        "tags": ["V2EX", "社区", "技术"],
        "difficulty": "easy",
    },
    {
        "name": "微博用户爬虫",
        "repo": "dataabc/weiboSpider",
        "files": ["weibo_spider/spider.py", "weibo.py", "main.py"],
        "category": "social",
        "icon": "📱",
        "target_url": "https://weibo.com",
        "tags": ["微博", "用户", "社交"],
        "difficulty": "medium",
    },
    {
        "name": "个人数据采集工具",
        "repo": "kangvcar/InfoSpider",
        "files": ["Spiders/weibo.py", "Spiders/zhihu.py", "Spiders/bilibili.py"],
        "category": "tools",
        "icon": "🔍",
        "target_url": "",
        "tags": ["个人数据", "多平台", "采集"],
        "difficulty": "medium",
    },
    {
        "name": "微博登录",
        "repo": "Kr1s77/awesome-python-login-model",
        "files": ["weibo/weibo.py", "weibo/login.py"],
        "category": "tools",
        "icon": "🔐",
        "target_url": "https://weibo.com",
        "tags": ["登录", "微博", "Cookie"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "知乎登录",
        "repo": "Kr1s77/awesome-python-login-model",
        "files": ["zhihu/zhihu.py", "zhihu/login.py"],
        "category": "tools",
        "icon": "🔐",
        "target_url": "https://www.zhihu.com",
        "tags": ["登录", "知乎", "Cookie"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "TuShare金融数据",
        "repo": "waditu/tushare",
        "files": ["tushare/stock/trading.py", "tushare/stock/fundamental.py"],
        "category": "finance",
        "icon": "📊",
        "target_url": "",
        "tags": ["金融", "股票", "数据", "A股"],
        "difficulty": "easy",
    },
    {
        "name": "抖音用户信息",
        "repo": "xuelangZF/DouYinSpider",
        "files": ["douyin.py", "spider.py", "main.py"],
        "category": "social",
        "icon": "🎵",
        "target_url": "https://www.douyin.com",
        "tags": ["抖音", "用户", "分析"],
        "difficulty": "hard",
        "use_browser": 1,
    },
    {
        "name": "微信公众号文章",
        "repo": "wnma3mz/wechat_articles_spider",
        "files": ["wechat_articles_spider/spider.py", "main.py"],
        "category": "social",
        "icon": "💚",
        "target_url": "https://mp.weixin.qq.com",
        "tags": ["微信", "公众号", "文章"],
        "difficulty": "hard",
    },
    {
        "name": "猫眼电影票房",
        "repo": "Ehco1996/Python-crawler",
        "files": ["maoyan/spider.py", "maoyan/maoyan.py", "猫眼/maoyan.py"],
        "category": "life",
        "icon": "🎬",
        "target_url": "https://www.maoyan.com",
        "tags": ["猫眼", "电影", "票房"],
        "difficulty": "easy",
    },
    {
        "name": "糗事百科",
        "repo": "Ehco1996/Python-crawler",
        "files": ["qiushibaike/spider.py", "糗事百科/qiushibaike.py"],
        "category": "life",
        "icon": "😂",
        "target_url": "https://www.qiushibaike.com",
        "tags": ["糗事百科", "段子", "搞笑"],
        "difficulty": "easy",
    },
]


def fetch_file(client: httpx.Client, repo: str, filepath: str) -> str | None:
    """Download a file from GitHub raw."""
    # Try main branch first, then master
    for branch in ["main", "master"]:
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{filepath}"
        try:
            resp = client.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
    return None


def get_existing_names(seeds_path: str) -> set[str]:
    """Extract existing template names from seeds.py."""
    with open(seeds_path, "r") as f:
        content = f.read()
    return set(re.findall(r'"name":\s*"([^"]*)"', content))


def make_seed_entry(info: dict, code: str) -> str:
    """Generate a seed template dict as string."""
    fmt = CodeAdapter.detect_format(code)
    wrapped = CodeAdapter.wrap(code, fmt)
    
    # Escape for triple-quoted string
    escaped_code = wrapped.replace("\\", "\\\\").replace("'''", "'\\'\\''")
    
    tags_str = repr(info["tags"])
    use_browser = info.get("use_browser", 0)
    
    entry = f'''    {{
        "name": "{info['name']}",
        "description": "社区爬虫 - 来自 {info['repo']} (GitHub高星项目)",
        "category": "{info['category']}",
        "icon": "{info['icon']}",
        "target_url": "{info['target_url']}",
        "mode": "code_generator",
        "code": \x27\x27\x27{escaped_code}\x27\x27\x27,
        "tags": {tags_str},
        "difficulty": "{info['difficulty']}",
        "author": "community",
        "source_url": "https://github.com/{info['repo']}",'''
    
    if use_browser:
        entry += f'\n        "use_browser": {use_browser},'
    
    entry += "\n    }"
    return entry


def main():
    seeds_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "core", "seeds.py")
    existing = get_existing_names(seeds_path)
    print(f"Existing templates: {len(existing)}")
    
    new_entries = []
    skipped = []
    failed = []
    
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    )
    
    for info in NEW_REPOS:
        name = info["name"]
        if name in existing:
            skipped.append(name)
            print(f"  SKIP (exists): {name}")
            continue
        
        # Try to download files, use first successful one
        code_parts = []
        for filepath in info["files"]:
            content = fetch_file(client, info["repo"], filepath)
            if content:
                code_parts.append(f"# === {filepath} ===\n{content}")
                print(f"  OK: {info['repo']}/{filepath}")
            else:
                print(f"  MISS: {info['repo']}/{filepath}")
        
        if not code_parts:
            failed.append(name)
            print(f"  FAILED (no files): {name}")
            continue
        
        combined_code = "\n\n".join(code_parts)
        # Truncate if too long (keep first 8000 chars)
        if len(combined_code) > 8000:
            combined_code = combined_code[:8000] + "\n# ... (truncated)"
        
        entry = make_seed_entry(info, combined_code)
        new_entries.append(entry)
        print(f"  ADDED: {name} ({len(combined_code)} chars)")
        
        time.sleep(0.3)  # Rate limit
    
    client.close()
    
    if new_entries:
        # Read seeds.py, insert before the closing ]
        with open(seeds_path, "r") as f:
            content = f.read()
        
        # Find the last ] of SEED_TEMPLATES
        # Pattern: find the ]\n\n# Category label line
        insert_pos = content.rfind("\n]\n")
        if insert_pos == -1:
            print("ERROR: Could not find end of SEED_TEMPLATES list")
            return
        
        new_block = "\n\n    # ═══════════════════════════════════════\n    # Community Seeds (auto-fetched from GitHub)\n    # ═══════════════════════════════════════\n"
        new_block += ",\n".join(new_entries) + ","
        
        content = content[:insert_pos] + new_block + content[insert_pos:]
        
        with open(seeds_path, "w") as f:
            f.write(content)
        
        print(f"\n=== Summary ===")
        print(f"Added: {len(new_entries)}")
        print(f"Skipped (duplicate): {len(skipped)} - {skipped}")
        print(f"Failed (no files): {len(failed)} - {failed}")
    else:
        print("No new entries to add.")


if __name__ == "__main__":
    main()
