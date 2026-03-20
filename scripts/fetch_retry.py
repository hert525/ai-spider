"""Retry failed repos by listing repo contents via GitHub API."""
from __future__ import annotations
import httpx
import asyncio
import json
import sys

sys.path.insert(0, '/root/.openclaw/workspace/ai-spider')
from src.engine.adapters import CodeAdapter

FAILED_REPOS = [
    {"name": "拉勾招聘", "repo": "hk029/LagouSpider", "category": "jobs", "icon": "💼", "target_url": "https://www.lagou.com"},
    {"name": "Bilibili视频", "repo": "airingursb/bilibili-video", "category": "social", "icon": "📺", "target_url": "https://www.bilibili.com"},
    {"name": "网易云音乐", "repo": "RitterHou/music-163", "category": "life", "icon": "🎵", "target_url": "https://music.163.com"},
    {"name": "前程无忧招聘", "repo": "chenjiandongx/51job", "category": "jobs", "icon": "💼", "target_url": "https://search.51job.com"},
    {"name": "知乎话题", "repo": "LiuRoy/zhihu_spider", "category": "social", "icon": "💬", "target_url": "https://www.zhihu.com"},
    {"name": "京东商品", "repo": "taizilongxu/scrapy_jingdong", "category": "ecommerce", "icon": "🛒", "target_url": "https://www.jd.com"},
    {"name": "新浪微博", "repo": "LiuXingMing/SinaSpider", "category": "social", "icon": "📱", "target_url": "https://weibo.com"},
    {"name": "去哪儿旅行", "repo": "lining0806/QunarSpider", "category": "life", "icon": "✈️", "target_url": "https://www.qunar.com"},
    {"name": "QQ空间", "repo": "LiuXingMing/QQSpider", "category": "social", "icon": "👥", "target_url": "https://qzone.qq.com"},
    {"name": "Bilibili用户", "repo": "airingursb/bilibili-user", "category": "social", "icon": "👤", "target_url": "https://www.bilibili.com"},
    {"name": "煎蛋妹纸图", "repo": "kulovecc/jandan_spider", "category": "life", "icon": "🥚", "target_url": "https://jandan.net/ooxx"},
    {"name": "百度云盘", "repo": "gudegg/yunSpider", "category": "tools", "icon": "☁️", "target_url": "https://pan.baidu.com"},
    {"name": "网易新闻", "repo": "armysheng/tech163newsSpider", "category": "news", "icon": "📰", "target_url": "https://news.163.com"},
    {"name": "漫画下载", "repo": "miaoerduo/cartoon-cat", "category": "life", "icon": "📖", "target_url": ""},
]

async def find_py_files(client: httpx.AsyncClient, repo: str) -> list[str]:
    """List .py files in repo root via GitHub API."""
    url = f"https://api.github.com/repos/{repo}/contents/"
    for branch in ['master', 'main']:
        try:
            resp = await client.get(url, params={"ref": branch})
            if resp.status_code == 200:
                data = resp.json()
                py_files = [item["path"] for item in data if item["name"].endswith(".py") and item["type"] == "file"]
                if py_files:
                    return [(f, branch) for f in py_files]
        except:
            pass
    # Try subdirs
    for branch in ['master', 'main']:
        try:
            resp = await client.get(url, params={"ref": branch})
            if resp.status_code == 200:
                data = resp.json()
                dirs = [item["path"] for item in data if item["type"] == "dir"]
                results = []
                for d in dirs[:3]:
                    try:
                        resp2 = await client.get(f"https://api.github.com/repos/{repo}/contents/{d}", params={"ref": branch})
                        if resp2.status_code == 200:
                            for item in resp2.json():
                                if item["name"].endswith(".py") and item["type"] == "file":
                                    results.append((item["path"], branch))
                    except:
                        pass
                if results:
                    return results
        except:
            pass
    return []

async def fetch_raw(client: httpx.AsyncClient, repo: str, path: str, branch: str) -> str:
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200 and len(resp.text) > 50:
            return resp.text
    except:
        pass
    return ""

async def main():
    # Load existing results
    with open('/root/.openclaw/workspace/ai-spider/scripts/community_codes.json') as f:
        results = json.load(f)
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"Accept": "application/vnd.github.v3+json"}) as client:
        for item in FAILED_REPOS:
            py_files = await find_py_files(client, item["repo"])
            if not py_files:
                print(f"❌ {item['name']}: repo not found or no .py files")
                continue
            
            # Pick the best .py file (prefer spider/crawl/main keywords, largest file)
            best_code = ""
            best_path = ""
            for path, branch in py_files:
                code = await fetch_raw(client, item["repo"], path, branch)
                if len(code) > len(best_code):
                    best_code = code
                    best_path = path
            
            if best_code:
                fmt = CodeAdapter.detect_format(best_code)
                wrapped = CodeAdapter.wrap(best_code, fmt)
                results.append({
                    "name": item["name"],
                    "repo": item["repo"],
                    "filename": best_path,
                    "original_format": fmt,
                    "code_length": len(best_code),
                    "wrapped_length": len(wrapped),
                    "category": item["category"],
                    "icon": item["icon"],
                    "target_url": item["target_url"],
                    "code": best_code,
                    "wrapped_code": wrapped,
                })
                print(f"✅ {item['name']}: {best_path} ({fmt}, {len(best_code)} chars)")
            else:
                print(f"❌ {item['name']}: no code downloaded")
            
            await asyncio.sleep(1)  # rate limit
    
    with open('/root/.openclaw/workspace/ai-spider/scripts/community_codes.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n总计: {len(results)} 成功")

asyncio.run(main())
