"""Preset seed templates for the template marketplace."""
from __future__ import annotations

SEED_TEMPLATES = [
    # === 新闻资讯 ===
    {
        "name": "Hacker News",
        "description": "提取HN首页新闻标题、链接、分数和评论数",
        "category": "news",
        "icon": "📰",
        "target_url": "https://news.ycombinator.com",
        "mode": "smart_scraper",
        "extract_schema": {"fields": ["title", "url", "score", "comments"]},
        "tags": ["新闻", "科技", "英文"],
        "difficulty": "easy",
    },
    {
        "name": "知乎热榜",
        "description": "提取知乎热榜话题标题、热度和链接",
        "category": "news",
        "icon": "🔥",
        "target_url": "https://www.zhihu.com/hot",
        "mode": "smart_scraper",
        "use_browser": 1,
        "extract_schema": {"fields": ["title", "heat", "url", "excerpt"]},
        "tags": ["知乎", "热榜", "中文"],
        "difficulty": "medium",
    },
    {
        "name": "微博热搜",
        "description": "提取微博实时热搜榜",
        "category": "news",
        "icon": "🔥",
        "target_url": "https://s.weibo.com/top/summary",
        "mode": "smart_scraper",
        "use_browser": 1,
        "tags": ["微博", "热搜", "中文"],
        "difficulty": "medium",
    },
    {
        "name": "Reddit首页",
        "description": "提取Reddit热帖标题、分数、评论数和subreddit",
        "category": "news",
        "icon": "🤖",
        "target_url": "https://old.reddit.com",
        "mode": "smart_scraper",
        "tags": ["Reddit", "社区", "英文"],
        "difficulty": "easy",
    },

    # === 电商价格 ===
    {
        "name": "Amazon商品",
        "description": "搜索并提取Amazon商品名称、价格、评分和评论数",
        "category": "ecommerce",
        "icon": "🛒",
        "target_url": "https://www.amazon.com/s?k={keyword}",
        "mode": "code_generator",
        "proxy_required": 1,
        "tags": ["电商", "价格", "英文"],
        "difficulty": "hard",
    },
    {
        "name": "淘宝商品搜索",
        "description": "搜索淘宝商品标题、价格、销量",
        "category": "ecommerce",
        "icon": "🛍️",
        "target_url": "https://s.taobao.com/search?q={keyword}",
        "mode": "code_generator",
        "use_browser": 1,
        "proxy_required": 1,
        "tags": ["电商", "淘宝", "中文"],
        "difficulty": "hard",
    },
    {
        "name": "京东商品",
        "description": "提取京东商品信息、价格和评价",
        "category": "ecommerce",
        "icon": "🏪",
        "target_url": "https://search.jd.com/Search?keyword={keyword}",
        "mode": "code_generator",
        "use_browser": 1,
        "tags": ["电商", "京东", "中文"],
        "difficulty": "hard",
    },

    # === 社交媒体 ===
    {
        "name": "Twitter/X用户推文",
        "description": "提取指定用户的最新推文",
        "category": "social",
        "icon": "🐦",
        "target_url": "https://x.com/{username}",
        "mode": "code_generator",
        "use_browser": 1,
        "proxy_required": 1,
        "tags": ["Twitter", "社交", "英文"],
        "difficulty": "hard",
    },
    {
        "name": "GitHub Trending",
        "description": "提取GitHub今日热门仓库",
        "category": "social",
        "icon": "⭐",
        "target_url": "https://github.com/trending",
        "mode": "smart_scraper",
        "extract_schema": {"fields": ["repo", "description", "language", "stars_today"]},
        "tags": ["GitHub", "开源", "开发"],
        "difficulty": "easy",
    },
    {
        "name": "Product Hunt",
        "description": "提取今日新产品排行",
        "category": "social",
        "icon": "🚀",
        "target_url": "https://www.producthunt.com",
        "mode": "smart_scraper",
        "use_browser": 1,
        "tags": ["产品", "创业", "英文"],
        "difficulty": "medium",
    },

    # === 学术/数据 ===
    {
        "name": "Google Scholar",
        "description": "搜索学术论文标题、作者、引用数",
        "category": "academic",
        "icon": "📚",
        "target_url": "https://scholar.google.com/scholar?q={keyword}",
        "mode": "smart_scraper",
        "proxy_required": 1,
        "tags": ["学术", "论文", "搜索"],
        "difficulty": "medium",
    },
    {
        "name": "ArXiv最新论文",
        "description": "提取ArXiv某领域最新论文",
        "category": "academic",
        "icon": "📄",
        "target_url": "https://arxiv.org/list/cs.AI/recent",
        "mode": "smart_scraper",
        "tags": ["学术", "AI", "论文"],
        "difficulty": "easy",
    },
    {
        "name": "维基百科",
        "description": "提取维基百科词条内容摘要",
        "category": "academic",
        "icon": "📖",
        "target_url": "https://zh.wikipedia.org/wiki/{title}",
        "mode": "smart_scraper",
        "tags": ["百科", "知识", "中文"],
        "difficulty": "easy",
    },

    # === 招聘/职位 ===
    {
        "name": "Boss直聘",
        "description": "搜索职位名称、薪资、公司、要求",
        "category": "jobs",
        "icon": "💼",
        "target_url": "https://www.zhipin.com/web/geek/job?query={keyword}",
        "mode": "code_generator",
        "use_browser": 1,
        "tags": ["招聘", "职位", "中文"],
        "difficulty": "hard",
    },
    {
        "name": "LinkedIn Jobs",
        "description": "提取LinkedIn职位列表",
        "category": "jobs",
        "icon": "👔",
        "target_url": "https://www.linkedin.com/jobs/search/?keywords={keyword}",
        "mode": "code_generator",
        "use_browser": 1,
        "proxy_required": 1,
        "tags": ["招聘", "LinkedIn", "英文"],
        "difficulty": "hard",
    },

    # === 天气/生活 ===
    {
        "name": "天气预报",
        "description": "提取城市未来7天天气预报",
        "category": "life",
        "icon": "🌤️",
        "target_url": "https://www.weather.com.cn/weather/{city_code}.shtml",
        "mode": "smart_scraper",
        "tags": ["天气", "生活", "中文"],
        "difficulty": "easy",
    },
    {
        "name": "豆瓣电影Top250",
        "description": "提取豆瓣电影Top250列表",
        "category": "life",
        "icon": "🎬",
        "target_url": "https://movie.douban.com/top250",
        "mode": "smart_scraper",
        "extract_schema": {"fields": ["title", "rating", "quote", "year", "director"]},
        "tags": ["电影", "豆瓣", "排行"],
        "difficulty": "easy",
    },
    {
        "name": "大众点评",
        "description": "搜索餐厅评分、人均消费、地址",
        "category": "life",
        "icon": "🍜",
        "target_url": "https://www.dianping.com/search/keyword/{city}/{keyword}",
        "mode": "code_generator",
        "use_browser": 1,
        "tags": ["美食", "点评", "中文"],
        "difficulty": "hard",
    },

    # === 金融/股票 ===
    {
        "name": "东方财富股票行情",
        "description": "提取A股行情数据",
        "category": "finance",
        "icon": "📈",
        "target_url": "https://quote.eastmoney.com/center/gridlist.html",
        "mode": "code_generator",
        "tags": ["股票", "行情", "金融"],
        "difficulty": "medium",
    },
    {
        "name": "雪球热帖",
        "description": "提取雪球社区热门讨论",
        "category": "finance",
        "icon": "⛷️",
        "target_url": "https://xueqiu.com",
        "mode": "smart_scraper",
        "use_browser": 1,
        "tags": ["金融", "社区", "中文"],
        "difficulty": "medium",
    },

    # === 房产 ===
    {
        "name": "链家二手房",
        "description": "搜索链家二手房源信息",
        "category": "realestate",
        "icon": "🏠",
        "target_url": "https://bj.lianjia.com/ershoufang/",
        "mode": "smart_scraper",
        "extract_schema": {"fields": ["title", "price_total", "price_unit", "area", "layout", "location"]},
        "tags": ["房产", "链家", "中文"],
        "difficulty": "medium",
    },
    {
        "name": "贝壳找房",
        "description": "提取新房楼盘信息和价格",
        "category": "realestate",
        "icon": "🏗️",
        "target_url": "https://bj.ke.com/loupan/",
        "mode": "smart_scraper",
        "tags": ["房产", "新房", "中文"],
        "difficulty": "medium",
    },

    # === 通用工具 ===
    {
        "name": "RSS Feed解析",
        "description": "解析任意RSS/Atom Feed",
        "category": "tools",
        "icon": "📡",
        "target_url": "",
        "mode": "code_generator",
        "code": """import httpx
import xml.etree.ElementTree as ET

async def crawl(url: str, config: dict) -> list[dict]:
    \"\"\"解析RSS/Atom Feed\"\"\"
    proxy = config.get("proxy")
    async with httpx.AsyncClient(proxies={"http://": proxy, "https://": proxy} if proxy else None, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    items = []

    # RSS 2.0
    for item in root.findall(".//item"):
        items.append({
            "title": item.findtext("title", ""),
            "link": item.findtext("link", ""),
            "description": item.findtext("description", ""),
            "pubDate": item.findtext("pubDate", ""),
        })

    # Atom
    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        link = entry.find("{http://www.w3.org/2005/Atom}link")
        items.append({
            "title": entry.findtext("{http://www.w3.org/2005/Atom}title", ""),
            "link": link.get("href", "") if link is not None else "",
            "description": entry.findtext("{http://www.w3.org/2005/Atom}summary", ""),
            "pubDate": entry.findtext("{http://www.w3.org/2005/Atom}updated", ""),
        })

    return items
""",
        "tags": ["RSS", "Feed", "通用"],
        "difficulty": "easy",
    },
    {
        "name": "网站Sitemap提取",
        "description": "解析网站sitemap.xml获取所有URL",
        "category": "tools",
        "icon": "🗺️",
        "target_url": "",
        "mode": "code_generator",
        "code": """import httpx
import xml.etree.ElementTree as ET

async def crawl(url: str, config: dict) -> list[dict]:
    \"\"\"解析sitemap.xml\"\"\"
    sitemap_url = url.rstrip('/') + '/sitemap.xml' if not url.endswith('.xml') else url
    proxy = config.get("proxy")
    async with httpx.AsyncClient(proxies={"http://": proxy, "https://": proxy} if proxy else None, timeout=30) as client:
        resp = await client.get(sitemap_url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    items = []

    for url_el in root.findall('.//sm:url', ns):
        items.append({
            "loc": url_el.findtext('sm:loc', '', ns),
            "lastmod": url_el.findtext('sm:lastmod', '', ns),
            "priority": url_el.findtext('sm:priority', '', ns),
        })

    return items
""",
        "tags": ["sitemap", "SEO", "通用"],
        "difficulty": "easy",
    },
]

# Category label mapping
CATEGORY_LABELS = {
    "news": "📰 新闻资讯",
    "ecommerce": "🛒 电商价格",
    "social": "💬 社交媒体",
    "academic": "📚 学术数据",
    "jobs": "💼 招聘职位",
    "life": "🌤️ 生活服务",
    "finance": "📈 金融投资",
    "realestate": "🏠 房产",
    "tools": "🔧 通用工具",
}
