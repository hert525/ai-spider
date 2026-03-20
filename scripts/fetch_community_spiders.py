"""Fetch community spider code from GitHub repos."""
from __future__ import annotations
import httpx
import asyncio
import json
import sys

sys.path.insert(0, '/root/.openclaw/workspace/ai-spider')
from src.engine.adapters import CodeAdapter

REPOS = [
    {"name": "豆瓣电影Top250", "repo": "lanbing510/DouBanSpider", "files": ["doubanSpider.py", "douban_spider.py", "spider.py"], "category": "life", "icon": "🎬", "target_url": "https://movie.douban.com/top250"},
    {"name": "GitHub Trending", "repo": "bonfy/github-trending", "files": ["scraper.py", "github_trending.py"], "category": "social", "icon": "⭐", "target_url": "https://github.com/trending"},
    {"name": "链家二手房", "repo": "lanbing510/LianJiaSpider", "files": ["spider.py", "lianjia.py", "LianJiaSpider.py"], "category": "realestate", "icon": "🏠", "target_url": "https://bj.lianjia.com/ershoufang/"},
    {"name": "拉勾招聘", "repo": "hk029/LagouSpider", "files": ["lagou.py", "spider.py"], "category": "jobs", "icon": "💼", "target_url": "https://www.lagou.com"},
    {"name": "Bilibili视频", "repo": "airingursb/bilibili-video", "files": ["bilibili.py", "spider.py", "main.py"], "category": "social", "icon": "📺", "target_url": "https://www.bilibili.com"},
    {"name": "网易云音乐", "repo": "RitterHou/music-163", "files": ["music163.py", "spider.py", "main.py", "netease.py"], "category": "life", "icon": "🎵", "target_url": "https://music.163.com"},
    {"name": "前程无忧招聘", "repo": "chenjiandongx/51job", "files": ["crawl_51job.py", "spider.py", "main.py"], "category": "jobs", "icon": "💼", "target_url": "https://search.51job.com"},
    {"name": "知乎话题", "repo": "LiuRoy/zhihu_spider", "files": ["zhihu/spiders/zhihu_spider.py", "spider.py"], "category": "social", "icon": "💬", "target_url": "https://www.zhihu.com"},
    {"name": "京东商品", "repo": "taizilongxu/scrapy_jingdong", "files": ["jingdong/spiders/jd.py", "spider.py", "jd.py"], "category": "ecommerce", "icon": "🛒", "target_url": "https://www.jd.com"},
    {"name": "新浪微博", "repo": "LiuXingMing/SinaSpider", "files": ["spider.py", "SinaSpider.py", "weibo.py", "main.py"], "category": "social", "icon": "📱", "target_url": "https://weibo.com"},
    {"name": "去哪儿旅行", "repo": "lining0806/QunarSpider", "files": ["qunar.py", "QunarSpider.py", "spider.py", "main.py"], "category": "life", "icon": "✈️", "target_url": "https://www.qunar.com"},
    {"name": "QQ空间", "repo": "LiuXingMing/QQSpider", "files": ["QQSpider.py", "spider.py", "main.py"], "category": "social", "icon": "👥", "target_url": "https://qzone.qq.com"},
    {"name": "Bilibili用户", "repo": "airingursb/bilibili-user", "files": ["bilibili.py", "spider.py", "main.py"], "category": "social", "icon": "👤", "target_url": "https://www.bilibili.com"},
    {"name": "豆瓣读书", "repo": "lanbing510/DouBanSpider", "files": ["doubanSpider.py"], "category": "life", "icon": "📚", "target_url": "https://book.douban.com/top250"},
    {"name": "煎蛋妹纸图", "repo": "kulovecc/jandan_spider", "files": ["jandan.py", "spider.py", "main.py"], "category": "life", "icon": "🥚", "target_url": "https://jandan.net/ooxx"},
    {"name": "百度云盘", "repo": "gudegg/yunSpider", "files": ["yunSpider.py", "spider.py", "main.py"], "category": "tools", "icon": "☁️", "target_url": "https://pan.baidu.com"},
    {"name": "网易新闻", "repo": "armysheng/tech163newsSpider", "files": ["tech163newsSpider.py", "spider.py", "main.py"], "category": "news", "icon": "📰", "target_url": "https://news.163.com"},
    {"name": "漫画下载", "repo": "miaoerduo/cartoon-cat", "files": ["cartoon_cat.py", "main.py", "spider.py"], "category": "life", "icon": "📖", "target_url": ""},
]


async def fetch_code(repo: str, files: list[str]) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for branch in ['master', 'main']:
            for f in files:
                url = f"https://raw.githubusercontent.com/{repo}/{branch}/{f}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.text) > 50:
                        return resp.text, f
                except:
                    continue
    return "", ""


async def main():
    results = []
    for item in REPOS:
        code, filename = await fetch_code(item["repo"], item["files"])
        if code:
            fmt = CodeAdapter.detect_format(code)
            wrapped = CodeAdapter.wrap(code, fmt)
            results.append({
                "name": item["name"],
                "repo": item["repo"],
                "filename": filename,
                "original_format": fmt,
                "code_length": len(code),
                "wrapped_length": len(wrapped),
                "category": item["category"],
                "icon": item["icon"],
                "target_url": item["target_url"],
                "code": code,
                "wrapped_code": wrapped,
            })
            print(f"✅ {item['name']}: {filename} ({fmt}, {len(code)} chars)")
        else:
            print(f"❌ {item['name']}: 未找到代码")

    with open('/root/.openclaw/workspace/ai-spider/scripts/community_codes.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n总计: {len(results)}/{len(REPOS)} 成功")

asyncio.run(main())
