"""Preset seed templates for the template marketplace."""
from __future__ import annotations

SEED_TEMPLATES = [
    # ═══════════════════════════════════════
    # 1. 豆瓣电影Top250
    # ═══════════════════════════════════════
    {
        "name": "豆瓣电影Top250",
        "description": "爬取豆瓣电影Top250榜单，提取电影名、评分、短评等信息",
        "category": "life",
        "icon": "🎬",
        "target_url": "https://movie.douban.com/top250",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """豆瓣电影Top250爬虫"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://movie.douban.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    results = []

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        # 爬取前几页（每页25部）
        for start in range(0, 50, 25):
            page_url = f"{url}?start={start}&filter="
            resp = await client.get(page_url)
            resp.raise_for_status()
            sel = Selector(text=resp.text)

            for item in sel.css("ol.grid_view li"):
                title = item.css(".title::text").get("").strip()
                rating = item.css(".rating_num::text").get("").strip()
                quote = item.css(".inq::text").get("").strip()
                link = item.css(".hd a::attr(href)").get("")
                info = item.css(".bd p:first-child::text").getall()
                year = ""
                for line in info:
                    line = line.strip()
                    if line and line[0].isdigit():
                        year = line.split("/")[0].strip()
                        break
                if title:
                    results.append({
                        "title": title,
                        "rating": rating,
                        "quote": quote,
                        "link": link,
                        "year": year,
                    })

    return results
''',
        "tags": ["豆瓣", "电影", "榜单", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 2. GitHub Trending
    # ═══════════════════════════════════════
    {
        "name": "GitHub Trending",
        "description": "获取GitHub每日/每周热门项目，包括星标数、语言等",
        "category": "social",
        "icon": "⭐",
        "target_url": "https://github.com/trending",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """GitHub Trending 热门项目爬虫"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for row in sel.css("article.Box-row"):
        repo_link = row.css("h2 a::attr(href)").get("")
        repo = repo_link.strip("/") if repo_link else ""
        description = row.css("p.col-9::text").get("").strip()
        language = row.css("[itemprop=programmingLanguage]::text").get("").strip()
        # 今日星标
        stars_today_text = row.css("span.d-inline-block.float-sm-right::text").get("").strip()
        stars_today = stars_today_text.replace(",", "").replace("stars today", "").replace("stars this week", "").strip()
        # 总星标
        total_stars_el = row.css("a.Link--muted:first-of-type::text").getall()
        total_stars = "".join(total_stars_el).strip().replace(",", "")

        if repo:
            results.append({
                "repo": repo,
                "description": description,
                "language": language,
                "stars_today": stars_today,
                "total_stars": total_stars,
                "url": f"https://github.com{repo_link}",
            })

    return results
''',
        "tags": ["GitHub", "开源", "趋势", "英文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 3. Hacker News
    # ═══════════════════════════════════════
    {
        "name": "Hacker News",
        "description": "提取HN首页新闻标题、链接、分数和评论数",
        "category": "news",
        "icon": "📰",
        "target_url": "https://news.ycombinator.com",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """Hacker News 首页爬虫"""
    headers = {"User-Agent": "Mozilla/5.0"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for item in sel.css("tr.athing"):
        item_id = item.attrib.get("id", "")
        title_el = item.css(".titleline > a")
        title = title_el.css("::text").get("").strip()
        link = title_el.attrib.get("href", "")

        # 下一行是subtext
        subtext = item.xpath("following-sibling::tr[1]")
        score = subtext.css(".score::text").get("").replace(" points", "").strip()
        author = subtext.css(".hnuser::text").get("").strip()
        comments_text = subtext.css("a:last-child::text").get("")
        comments = comments_text.replace("\\xa0comments", "").replace("\\xa0comment", "").strip() if "comment" in comments_text else "0"

        if title:
            results.append({
                "title": title,
                "url": link if link.startswith("http") else f"https://news.ycombinator.com/{link}",
                "score": score,
                "author": author,
                "comments": comments,
            })

    return results
''',
        "tags": ["新闻", "科技", "英文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 4. ArXiv最新论文
    # ═══════════════════════════════════════
    {
        "name": "ArXiv最新论文",
        "description": "获取ArXiv指定分类下的最新论文标题、作者和摘要",
        "category": "academic",
        "icon": "📄",
        "target_url": "https://arxiv.org/list/cs.AI/recent",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """ArXiv最新论文爬虫"""
    headers = {"User-Agent": "Mozilla/5.0"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    # ArXiv API方式更稳定
    api_url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&start=0&max_results=20&sortBy=submittedDate&sortOrder=descending"
    if "arxiv.org/list/" in url:
        # 从URL提取分类
        parts = url.rstrip("/").split("/")
        cat = parts[-2] if parts[-1] == "recent" else parts[-1]
        api_url = f"http://export.arxiv.org/api/query?search_query=cat:{cat}&start=0&max_results=20&sortBy=submittedDate&sortOrder=descending"

    async with httpx.AsyncClient(proxies=proxies, timeout=30) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    from xml.etree import ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)

    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", "", ns) or "").strip().replace("\\n", " ")
        authors = [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)]
        abstract = (entry.findtext("a:summary", "", ns) or "").strip()[:300]
        link = entry.find("a:id", ns)
        link_text = link.text if link is not None else ""

        results.append({
            "title": title,
            "authors": ", ".join(authors[:5]),
            "abstract": abstract,
            "link": link_text,
        })

    return results
''',
        "tags": ["论文", "学术", "AI", "英文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 5. 链家二手房
    # ═══════════════════════════════════════
    {
        "name": "链家二手房",
        "description": "爬取链家二手房列表，提取房源标题、价格、面积等",
        "category": "realestate",
        "icon": "🏠",
        "target_url": "https://bj.lianjia.com/ershoufang/",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """链家二手房爬虫"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://lianjia.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for li in sel.css(".sellListContent li.clear"):
        title = li.css(".title a::text").get("").strip()
        price_total = li.css(".totalPrice span::text").get("").strip()
        price_unit = li.css(".unitPrice span::text").get("").strip()
        house_info = li.css(".houseInfo::text").get("").strip()
        position_info = li.css(".positionInfo::text").get("").strip()
        link = li.css(".title a::attr(href)").get("")

        # 解析户型和面积
        parts = house_info.split("|") if house_info else []
        layout = parts[0].strip() if len(parts) > 0 else ""
        area = parts[1].strip() if len(parts) > 1 else ""

        if title:
            results.append({
                "title": title,
                "price_total": f"{price_total}万",
                "price_unit": price_unit,
                "layout": layout,
                "area": area,
                "location": position_info,
                "link": link,
            })

    return results
''',
        "tags": ["链家", "房产", "二手房", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 6. V2EX热帖
    # ═══════════════════════════════════════
    {
        "name": "V2EX热帖",
        "description": "获取V2EX社区当前热门帖子",
        "category": "social",
        "icon": "💻",
        "target_url": "https://www.v2ex.com/?tab=hot",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """V2EX热帖爬虫"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.v2ex.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for item in sel.css(".cell.item"):
        title = item.css(".item_title a::text").get("").strip()
        link = item.css(".item_title a::attr(href)").get("")
        node = item.css(".node::text").get("").strip()
        author = item.css("strong a::text").get("").strip()
        replies = item.css("a.count_livid::text").get("0").strip()

        if title:
            results.append({
                "title": title,
                "url": f"https://www.v2ex.com{link}" if link.startswith("/") else link,
                "node": node,
                "author": author,
                "replies": replies,
            })

    return results
''',
        "tags": ["V2EX", "社区", "技术", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 7. 豆瓣读书Top250
    # ═══════════════════════════════════════
    {
        "name": "豆瓣读书Top250",
        "description": "爬取豆瓣读书Top250榜单",
        "category": "life",
        "icon": "📚",
        "target_url": "https://book.douban.com/top250",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """豆瓣读书Top250爬虫"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://book.douban.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    results = []

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        for start in range(0, 50, 25):
            page_url = f"{url}?start={start}"
            resp = await client.get(page_url)
            resp.raise_for_status()
            sel = Selector(text=resp.text)

            for item in sel.css("tr.item"):
                title = item.css("div.pl2 a::attr(title)").get("").strip()
                rating = item.css(".rating_nums::text").get("").strip()
                info = item.css("p.pl::text").get("").strip()
                quote = item.css(".inq::text").get("").strip()
                link = item.css("div.pl2 a::attr(href)").get("")

                if title:
                    results.append({
                        "title": title,
                        "rating": rating,
                        "info": info,
                        "quote": quote,
                        "link": link,
                    })

    return results
''',
        "tags": ["豆瓣", "读书", "榜单", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 8. 天气预报
    # ═══════════════════════════════════════
    {
        "name": "天气预报",
        "description": "通过wttr.in获取指定城市的天气预报（JSON API，无需密钥）",
        "category": "life",
        "icon": "🌤️",
        "target_url": "https://wttr.in/Beijing?format=j1",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """天气预报爬虫（wttr.in API）"""
    # 从URL提取城市名，或默认北京
    if "wttr.in/" in url:
        city = url.split("wttr.in/")[1].split("?")[0].split("/")[0]
    else:
        city = "Beijing"

    api_url = f"https://wttr.in/{city}?format=j1"
    headers = {"User-Agent": "curl/7.68.0"}  # wttr.in对curl友好
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    data = resp.json()
    results = []

    # 当前天气
    current = data.get("current_condition", [{}])[0]
    results.append({
        "type": "当前天气",
        "date": "now",
        "temp": f"{current.get('temp_C', '')}°C",
        "feels_like": f"{current.get('FeelsLikeC', '')}°C",
        "description": current.get("weatherDesc", [{}])[0].get("value", ""),
        "humidity": f"{current.get('humidity', '')}%",
        "wind": f"{current.get('windspeedKmph', '')}km/h",
    })

    # 未来几天
    for day in data.get("weather", []):
        results.append({
            "type": "预报",
            "date": day.get("date", ""),
            "temp_max": f"{day.get('maxtempC', '')}°C",
            "temp_min": f"{day.get('mintempC', '')}°C",
            "description": day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "") if day.get("hourly") else "",
        })

    return results
''',
        "tags": ["天气", "API", "生活"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 9. 汇率查询
    # ═══════════════════════════════════════
    {
        "name": "汇率查询",
        "description": "通过免费API获取实时汇率（基于USD）",
        "category": "finance",
        "icon": "💱",
        "target_url": "https://open.er-api.com/v6/latest/USD",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """汇率查询爬虫（免费API，无需密钥）"""
    # 默认查USD汇率
    base = "USD"
    if "latest/" in url:
        base = url.split("latest/")[-1].split("?")[0].strip("/") or "USD"

    api_url = f"https://open.er-api.com/v6/latest/{base}"
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    data = resp.json()
    rates = data.get("rates", {})

    # 只返回常用货币
    common = ["CNY", "EUR", "GBP", "JPY", "KRW", "HKD", "TWD", "SGD", "AUD", "CAD", "CHF", "RUB", "INR", "BRL"]
    results = []

    for currency in common:
        if currency in rates:
            results.append({
                "base": base,
                "currency": currency,
                "rate": rates[currency],
            })

    return results
''',
        "tags": ["汇率", "金融", "API"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 10. RSS Feed解析
    # ═══════════════════════════════════════
    {
        "name": "RSS Feed解析",
        "description": "通用RSS/Atom订阅源解析器，提取文章列表",
        "category": "tools",
        "icon": "📡",
        "target_url": "",
        "mode": "code_generator",
        "code": '''import httpx
from xml.etree import ElementTree as ET

async def crawl(url: str, config: dict) -> list[dict]:
    """通用RSS/Atom解析爬虫"""
    headers = {"User-Agent": "Mozilla/5.0"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    results = []

    # 尝试RSS 2.0格式
    for item in root.findall(".//item"):
        results.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "description": (item.findtext("description") or "").strip()[:200],
            "pub_date": (item.findtext("pubDate") or "").strip(),
            "author": (item.findtext("author") or item.findtext("{http://purl.org/dc/elements/1.1/}creator") or "").strip(),
        })

    # 如果没找到item，尝试Atom格式
    if not results:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//a:entry", ns):
            link_el = entry.find("a:link", ns)
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            results.append({
                "title": (entry.findtext("a:title", "", ns) or "").strip(),
                "link": link,
                "description": (entry.findtext("a:summary", "", ns) or "").strip()[:200],
                "pub_date": (entry.findtext("a:updated", "", ns) or "").strip(),
                "author": (entry.findtext("a:author/a:name", "", ns) or "").strip(),
            })

    return results
''',
        "tags": ["RSS", "Atom", "通用", "订阅"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 11. Reddit热帖
    # ═══════════════════════════════════════
    {
        "name": "Reddit热帖",
        "description": "获取Reddit热门帖子（old.reddit.com，无需JS）",
        "category": "social",
        "icon": "🤖",
        "target_url": "https://old.reddit.com",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """Reddit热帖爬虫（old.reddit.com）"""
    if "old.reddit" not in url:
        url = url.replace("www.reddit.com", "old.reddit.com").replace("reddit.com", "old.reddit.com")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for thing in sel.css("#siteTable .thing"):
        title = thing.css("a.title::text").get("").strip()
        link = thing.css("a.title::attr(href)").get("")
        score = thing.css(".score.unvoted::attr(title)").get("0")
        comments = thing.css(".comments::text").get("0").split()[0]
        subreddit = thing.css(".subreddit::text").get("").strip()
        author = thing.css(".author::text").get("").strip()

        if title:
            results.append({
                "title": title,
                "url": link if link.startswith("http") else f"https://old.reddit.com{link}",
                "score": score,
                "comments": comments,
                "subreddit": subreddit,
                "author": author,
            })

    return results
''',
        "tags": ["Reddit", "社区", "英文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 12. Wikipedia摘要
    # ═══════════════════════════════════════
    {
        "name": "Wikipedia摘要",
        "description": "通过Wikipedia API获取词条摘要（支持多语言）",
        "category": "tools",
        "icon": "📖",
        "target_url": "https://zh.wikipedia.org/wiki/Python",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """Wikipedia摘要爬虫（REST API）"""
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    # 从URL提取语言和词条
    lang = "zh"
    title = "Python"
    if "wikipedia.org" in url:
        parts = url.split("//")[1].split("/")
        lang = parts[0].split(".")[0]  # zh, en, ja...
        if "wiki/" in url:
            title = url.split("wiki/")[-1]
    else:
        title = url  # 直接传词条名

    api_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

    async with httpx.AsyncClient(proxies=proxies, timeout=30) as client:
        resp = await client.get(api_url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    data = resp.json()
    results = [{
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "extract": data.get("extract", ""),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "thumbnail": data.get("thumbnail", {}).get("source", ""),
    }]

    return results
''',
        "tags": ["Wikipedia", "百科", "API"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 13. Product Hunt
    # ═══════════════════════════════════════
    {
        "name": "Product Hunt今日热门",
        "description": "获取Product Hunt每日热门产品（解析页面）",
        "category": "social",
        "icon": "🚀",
        "target_url": "https://www.producthunt.com",
        "mode": "code_generator",
        "use_browser": 1,
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """Product Hunt爬虫（需要浏览器渲染）"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    # PH的结构经常变，尝试多种选择器
    for item in sel.css("[data-test=post-item], .styles_item__Dk_nz, section div[class*=item]"):
        title = item.css("a strong::text, h3::text, [data-test=post-name]::text").get("").strip()
        tagline = item.css("a span::text, p::text").get("").strip()
        link = item.css("a::attr(href)").get("")
        votes = item.css("button span::text, [class*=vote]::text").get("0").strip()

        if title:
            results.append({
                "title": title,
                "tagline": tagline,
                "url": f"https://www.producthunt.com{link}" if link.startswith("/") else link,
                "votes": votes,
            })

    return results
''',
        "tags": ["ProductHunt", "产品", "创业", "英文"],
        "difficulty": "medium",
    },

    # ═══════════════════════════════════════
    # 14. 拉勾招聘
    # ═══════════════════════════════════════
    {
        "name": "拉勾招聘",
        "description": "搜索拉勾网职位信息（需要浏览器渲染）",
        "category": "jobs",
        "icon": "💼",
        "target_url": "https://www.lagou.com/wn/zhaopin?kd=Python",
        "mode": "code_generator",
        "use_browser": 1,
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """拉勾招聘爬虫（需要浏览器渲染）
    注意：拉勾反爬严格，建议开启浏览器模式
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.lagou.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for item in sel.css(".itemBox__2XGPB, .item__10RTO, [class*=position-list] li"):
        title = item.css("a.position_link::text, .p-top a::text, a[class*=name]::text").get("").strip()
        company = item.css(".company_name a::text, [class*=company]::text").get("").strip()
        salary = item.css(".money::text, [class*=salary]::text, .p-bom span::text").get("").strip()
        city = item.css(".add em::text, [class*=city]::text").get("").strip()
        experience = item.css(".li_b_l::text, [class*=experience]::text").get("").strip()

        if title:
            results.append({
                "title": title,
                "company": company,
                "salary": salary,
                "city": city,
                "experience": experience,
            })

    return results
''',
        "tags": ["拉勾", "招聘", "求职", "中文"],
        "difficulty": "medium",
    },

    # ═══════════════════════════════════════
    # 15. Bilibili热门视频
    # ═══════════════════════════════════════
    {
        "name": "Bilibili热门视频",
        "description": "通过B站API获取热门视频列表（稳定API接口）",
        "category": "social",
        "icon": "📺",
        "target_url": "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """Bilibili热门视频爬虫（官方API）"""
    api_url = "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    data = resp.json()
    results = []

    for item in data.get("data", {}).get("list", []):
        stat = item.get("stat", {})
        owner = item.get("owner", {})
        results.append({
            "title": item.get("title", ""),
            "author": owner.get("name", ""),
            "bvid": item.get("bvid", ""),
            "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
            "play": stat.get("view", 0),
            "danmaku": stat.get("danmaku", 0),
            "like": stat.get("like", 0),
            "description": item.get("desc", "")[:100],
            "duration": item.get("duration", 0),
        })

    return results
''',
        "tags": ["B站", "视频", "API", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 16. 微博热搜
    # ═══════════════════════════════════════
    {
        "name": "微博热搜",
        "description": "获取微博实时热搜榜（需浏览器渲染）",
        "category": "news",
        "icon": "🔥",
        "target_url": "https://s.weibo.com/top/summary",
        "mode": "code_generator",
        "use_browser": 1,
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """微博热搜爬虫
    注意：微博需要cookie/登录，建议开启浏览器模式
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://s.weibo.com/",
        "Cookie": config.get("cookie", ""),
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for tr in sel.css("table tbody tr"):
        rank = tr.css("td.td-01.ranktop::text").get("").strip()
        keyword = tr.css("td.td-02 a::text").get("").strip()
        hot_value = tr.css("td.td-02 span::text").get("").strip()
        tag = tr.css("td.td-03 i::text").get("").strip()
        link = tr.css("td.td-02 a::attr(href)").get("")

        if keyword:
            results.append({
                "rank": rank,
                "keyword": keyword,
                "hot_value": hot_value,
                "tag": tag,
                "url": f"https://s.weibo.com{link}" if link.startswith("/") else link,
            })

    return results
''',
        "tags": ["微博", "热搜", "中文"],
        "difficulty": "medium",
    },

    # ═══════════════════════════════════════
    # 17. 东方财富行情
    # ═══════════════════════════════════════
    {
        "name": "东方财富行情",
        "description": "通过东方财富API获取A股实时行情数据",
        "category": "finance",
        "icon": "📈",
        "target_url": "https://push2.eastmoney.com/api/qt/clist/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """东方财富A股行情爬虫（官方API）"""
    # 沪深A股列表API
    api_url = (
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=20&po=1&np=1&fltt=2&invt=2&ut=b2884a393a59ad64002292a3e90d46a5"
        "&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        "&fields=f2,f3,f4,f5,f6,f7,f12,f14,f15,f16,f17,f18"
    )
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    data = resp.json()
    results = []

    for item in data.get("data", {}).get("diff", []):
        results.append({
            "code": item.get("f12", ""),           # 股票代码
            "name": item.get("f14", ""),            # 股票名称
            "price": item.get("f2", 0),             # 最新价
            "change_pct": item.get("f3", 0),        # 涨跌幅%
            "change_amt": item.get("f4", 0),        # 涨跌额
            "volume": item.get("f5", 0),            # 成交量（手）
            "turnover": item.get("f6", 0),          # 成交额
            "amplitude": item.get("f7", 0),         # 振幅%
            "high": item.get("f15", 0),             # 最高
            "low": item.get("f16", 0),              # 最低
            "open": item.get("f17", 0),             # 今开
            "yesterday_close": item.get("f18", 0),  # 昨收
        })

    return results
''',
        "tags": ["股票", "A股", "东方财富", "API"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 18. 网易新闻
    # ═══════════════════════════════════════
    {
        "name": "网易新闻热点",
        "description": "获取网易新闻热点头条",
        "category": "news",
        "icon": "📰",
        "target_url": "https://news.163.com",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """网易新闻爬虫"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    # 用网易新闻API获取热点
    api_url = "https://m.163.com/nc/article/headline/T1348647853363/0-20.html"

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    data = resp.json()
    results = []

    items = data.get("T1348647853363", [])
    for item in items:
        results.append({
            "title": item.get("title", ""),
            "digest": item.get("digest", ""),
            "source": item.get("source", ""),
            "ptime": item.get("ptime", ""),
            "url": item.get("url", ""),
            "comment_count": item.get("commentCount", 0),
        })

    return results
''',
        "tags": ["网易", "新闻", "热点", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 19. 前程无忧
    # ═══════════════════════════════════════
    {
        "name": "前程无忧招聘",
        "description": "搜索前程无忧(51job)职位信息",
        "category": "jobs",
        "icon": "💼",
        "target_url": "https://search.51job.com/list/000000,000000,0000,00,9,99,python,2,1.html",
        "mode": "code_generator",
        "use_browser": 1,
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """前程无忧招聘爬虫
    注意：51job反爬较严格，建议使用浏览器模式
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.51job.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    # 51job页面结构
    for item in sel.css(".j_joblist .e, .joblist-box .el, [class*=job-card]"):
        title = item.css("a.jname::text, .t1 a::text, [class*=name] a::text").get("").strip()
        company = item.css(".cname a::text, .t2 a::text, [class*=company]::text").get("").strip()
        salary = item.css(".sal::text, .t4::text, [class*=salary]::text").get("").strip()
        area = item.css(".d.at::text, .t3::text, [class*=area]::text").get("").strip()
        link = item.css("a.jname::attr(href), .t1 a::attr(href)").get("")

        if title:
            results.append({
                "title": title,
                "company": company,
                "salary": salary,
                "area": area,
                "link": link,
            })

    return results
''',
        "tags": ["51job", "招聘", "求职", "中文"],
        "difficulty": "medium",
    },

    # ═══════════════════════════════════════
    # 20. IMDB Top250
    # ═══════════════════════════════════════
    {
        "name": "IMDB Top250",
        "description": "获取IMDB电影Top250榜单",
        "category": "life",
        "icon": "🎥",
        "target_url": "https://www.imdb.com/chart/top/",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector
import json

async def crawl(url: str, config: dict) -> list[dict]:
    """IMDB Top250爬虫"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    # IMDB现在用JSON-LD
    ld_json = sel.css("script[type=\\"application/ld+json\\"]::text").get("")
    if ld_json:
        try:
            data = json.loads(ld_json)
            for i, item in enumerate(data.get("itemListElement", [])[:50], 1):
                movie = item.get("item", {})
                results.append({
                    "rank": i,
                    "title": movie.get("name", ""),
                    "url": movie.get("url", ""),
                    "rating": movie.get("aggregateRating", {}).get("ratingValue", ""),
                    "year": movie.get("datePublished", "")[:4] if movie.get("datePublished") else "",
                })
        except json.JSONDecodeError:
            pass

    # 回退到HTML解析
    if not results:
        for i, item in enumerate(sel.css(".ipc-metadata-list li, .lister-list tr"), 1):
            title = item.css("h3::text, .titleColumn a::text").get("").strip()
            rating = item.css("[class*=rating]::text, .ratingColumn strong::text").get("").strip()
            link = item.css("a::attr(href)").get("")
            if title and i <= 50:
                results.append({
                    "rank": i,
                    "title": title,
                    "rating": rating,
                    "url": f"https://www.imdb.com{link}" if link.startswith("/") else link,
                })

    return results
''',
        "tags": ["IMDB", "电影", "榜单", "英文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 21. 知乎热榜
    # ═══════════════════════════════════════
    {
        "name": "知乎热榜",
        "description": "获取知乎热榜话题（需浏览器渲染）",
        "category": "social",
        "icon": "💬",
        "target_url": "https://www.zhihu.com/hot",
        "mode": "code_generator",
        "use_browser": 1,
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """知乎热榜爬虫
    注意：知乎反爬严格，建议开启浏览器模式
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.zhihu.com/",
        "Cookie": config.get("cookie", ""),
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for item in sel.css(".HotList-item, .HotItem"):
        rank = item.css(".HotItem-rank::text, .HotItem-index::text").get("").strip()
        title = item.css(".HotItem-content a::text, h2::text").get("").strip()
        excerpt = item.css(".HotItem-excerpt::text, p.HotItem-excerpt::text").get("").strip()
        heat = item.css(".HotItem-metrics::text, .hot-item-metrics::text").get("").strip()
        link = item.css(".HotItem-content a::attr(href), a::attr(href)").get("")

        if title:
            results.append({
                "rank": rank,
                "title": title,
                "excerpt": excerpt,
                "heat": heat,
                "url": f"https://www.zhihu.com{link}" if link.startswith("/") else link,
            })

    return results
''',
        "tags": ["知乎", "热榜", "中文"],
        "difficulty": "medium",
    },

    # ═══════════════════════════════════════
    # 22. 网站Sitemap提取
    # ═══════════════════════════════════════
    {
        "name": "网站Sitemap提取",
        "description": "解析网站sitemap.xml获取所有URL",
        "category": "tools",
        "icon": "🗺️",
        "target_url": "",
        "mode": "code_generator",
        "code": '''import httpx
import xml.etree.ElementTree as ET

async def crawl(url: str, config: dict) -> list[dict]:
    """解析sitemap.xml"""
    sitemap_url = url.rstrip("/") + "/sitemap.xml" if not url.endswith(".xml") else url
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30) as client:
        resp = await client.get(sitemap_url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    results = []

    for url_el in root.findall(".//sm:url", ns):
        results.append({
            "loc": url_el.findtext("sm:loc", "", ns),
            "lastmod": url_el.findtext("sm:lastmod", "", ns),
            "priority": url_el.findtext("sm:priority", "", ns),
        })

    return results
''',
        "tags": ["sitemap", "SEO", "通用"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 23. 网易云音乐热歌榜
    # ═══════════════════════════════════════
    {
        "name": "网易云音乐热歌榜",
        "description": "通过网易云音乐API获取热歌榜数据",
        "category": "life",
        "icon": "🎵",
        "target_url": "https://music.163.com/api/playlist/detail?id=3778678",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """网易云音乐热歌榜爬虫（API方式）"""
    # 3778678 是热歌榜的歌单ID
    api_url = "https://music.163.com/api/playlist/detail?id=3778678"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://music.163.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    data = resp.json()
    results = []

    tracks = data.get("result", {}).get("tracks", [])
    for i, track in enumerate(tracks[:30], 1):
        artists = ", ".join(a.get("name", "") for a in track.get("artists", []))
        album = track.get("album", {}).get("name", "")
        results.append({
            "rank": i,
            "name": track.get("name", ""),
            "artists": artists,
            "album": album,
            "duration_ms": track.get("duration", 0),
            "popularity": track.get("popularity", 0),
        })

    return results
''',
        "tags": ["网易云", "音乐", "API", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 24. 36氪快讯
    # ═══════════════════════════════════════
    {
        "name": "36氪快讯",
        "description": "获取36氪最新快讯/科技新闻",
        "category": "news",
        "icon": "⚡",
        "target_url": "https://36kr.com/newsflashes",
        "mode": "code_generator",
        "code": '''import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    """36氪快讯爬虫"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    # 36氪有API可用
    api_url = "https://gateway.36kr.com/api/missive/flow/listFlash?per_page=20"

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    sel = Selector(text=resp.text)
    results = []

    for item in sel.css(".newsflash-item, article.item-main"):
        title = item.css("a.item-title::text, .title::text").get("").strip()
        desc = item.css(".item-desc::text, .description::text").get("").strip()
        time_str = item.css(".time::text, time::text").get("").strip()
        link = item.css("a.item-title::attr(href), a::attr(href)").get("")

        if title:
            results.append({
                "title": title,
                "description": desc[:200],
                "time": time_str,
                "url": f"https://36kr.com{link}" if link.startswith("/") else link,
            })

    return results
''',
        "tags": ["36氪", "科技", "快讯", "中文"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # 25. CoinGecko加密货币行情
    # ═══════════════════════════════════════
    {
        "name": "加密货币行情",
        "description": "通过CoinGecko免费API获取加密货币价格",
        "category": "finance",
        "icon": "₿",
        "target_url": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=20",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """加密货币行情爬虫（CoinGecko API，免费无需密钥）"""
    api_url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=20&page=1&sparkline=false"
    headers = {"User-Agent": "Mozilla/5.0"}
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()

    data = resp.json()
    results = []

    for coin in data:
        results.append({
            "rank": coin.get("market_cap_rank", ""),
            "name": coin.get("name", ""),
            "symbol": coin.get("symbol", "").upper(),
            "price_usd": coin.get("current_price", 0),
            "change_24h": round(coin.get("price_change_percentage_24h", 0) or 0, 2),
            "market_cap": coin.get("market_cap", 0),
            "volume_24h": coin.get("total_volume", 0),
        })

    return results
''',
        "tags": ["加密货币", "比特币", "API", "金融"],
        "difficulty": "easy",
    },
    # ═══════════════════════════════════════
    # 社区: 豆瓣读书
    # ═══════════════════════════════════════
    {
        "name": '豆瓣读书',
        "description": '社区爬虫 - 豆瓣读书（来自 GitHub lanbing510/DouBanSpider）',
        "category": 'life',
        "icon": '📚',
        "target_url": 'https://book.douban.com/top250',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n#-*- coding: UTF-8 -*-\n\nimport sys\nimport time\nimport urllib\nimport urllib2\nimport requests\nimport numpy as np\nfrom bs4 import BeautifulSoup\nfrom openpyxl import Workbook\n\nreload(sys)\nsys.setdefaultencoding(\'utf8\')\n\n\n\n#Some User Agents\nhds=[{\'User-Agent\':\'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6\'},\\\n{\'User-Agent\':\'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11\'},\\\n{\'User-Agent\': \'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)\'}]\n\n\ndef book_spider(book_tag):\n    page_num=0;\n    book_list=[]\n    try_times=0\n    \n    while(1):\n        #url=\'http://www.douban.com/tag/%E5%B0%8F%E8%AF%B4/book?start=0\' # For Test\n        url=\'http://www.douban.com/tag/\'+urllib.quote(book_tag)+\'/book?start=\'+str(page_num*15)\n        time.sleep(np.random.rand()*5)\n        \n        #Last Version\n        try:\n            req = urllib2.Request(url, headers=hds[page_num%len(hds)])\n            source_code = urllib2.urlopen(req).read()\n            plain_text=str(source_code)   \n        except (urllib2.HTTPError, urllib2.URLError), e:\n            print e\n            continue\n  \n        ##Previous Version, IP is easy to be Forbidden\n        #source_code = requests.get(url) \n        #plain_text = source_code.text  \n        \n        soup = BeautifulSoup(plain_text)\n        list_soup = soup.find(\'div\', {\'class\': \'mod book-list\'})\n        \n        try_times+=1;\n        if list_soup==None and try_times<200:\n            continue\n        elif list_soup==None or len(list_soup)<=1:\n            break # Break when no informatoin got after 200 times requesting\n        \n        for book_info in list_soup.findAll(\'dd\'):\n            title = book_info.find(\'a\', {\'class\':\'title\'}).string.strip()\n            desc = book_info.find(\'div\', {\'class\':\'desc\'}).string.strip()\n            desc_list = desc.split(\'/\')\n            book_url = book_info.find(\'a\', {\'class\':\'title\'}).get(\'href\')\n            \n            try:\n                author_info = \'作者/译者： \' + \'/\'.join(desc_list[0:-3])\n            except:\n                author_info =\'作者/译者： 暂无\'\n            try:\n                pub_info = \'出版信息： \' + \'/\'.join(desc_list[-3:])\n            except:\n                pub_info = \'出版信息： 暂无\'\n            try:\n                rating = book_info.find(\'span\', {\'class\':\'rating_nums\'}).string.strip()\n            except:\n                rating=\'0.0\'\n            try:\n                #people_num = book_info.findAll(\'span\')[2].string.strip()\n                people_num = get_people_num(book_url)\n                people_num = people_num.strip(\'人评价\')\n            except:\n                people_num =\'0\'\n            \n            book_list.append([title,rating,people_num,author_info,pub_info])\n            try_times=0 #set 0 when got valid information\n        page_num+=1\n        print \'Downloading Information From Page %d\' % page_num\n    return book_list\n\n\ndef get_people_num(url):\n    #url=\'http://book.douban.com/subject/6082808/?from=tag_all\' # For Test\n    try:\n        req = urllib2.Request(url, headers=hds[np.random.randint(0,len(hds))])\n        source_code = urllib2.urlopen(req).read()\n        plain_text=str(source_code)   \n    except (urllib2.HTTPError, urllib2.URLError), e:\n        print e\n    soup = BeautifulSoup(plain_text)\n    people_num=soup.find(\'div\',{\'class\':\'rating_sum\'}).findAll(\'span\')[1].string.strip()\n    return people_num\n\n\ndef do_spider(book_tag_lists):\n    book_lists=[]\n    for book_tag in book_tag_lists:\n        book_list=book_spider(book_tag)\n        book_list=sorted(book_list,key=lambda x:x[1],reverse=True)\n        book_lists.append(book_list)\n    return book_lists\n\n\ndef print_book_lists_excel(book_lists,book_tag_lists):\n    wb=Workbook(optimized_write=True)\n    ws=[]\n    for i in range(len(book_tag_lists)):\n        ws.append(wb.create_sheet(title=book_tag_lists[i].decode())) #utf8->unicode\n    for i in range(len(book_tag_lists)): \n        ws[i].append([\'序号\',\'书名\',\'评分\',\'评价人数\',\'作者\',\'出版社\'])\n        count=1\n        for bl in book_lists[i]:\n            ws[i].append([count,bl[0],float(bl[1]),int(bl[2]),bl[3],bl[4]])\n            count+=1\n    save_path=\'book_list\'\n    for i in range(len(book_tag_lists)):\n        save_path+=(\'-\'+book_tag_lists[i].decode())\n    save_path+=\'.xlsx\'\n    wb.save(save_path)\n\n\n\n\nif __name__==\'__main__\':\n    #book_tag_lists = [\'心理\',\'判断与决策\',\'算法\',\'数据结构\',\'经济\',\'历史\']\n    #book_tag_lists = [\'传记\',\'哲学\',\'编程\',\'创业\',\'理财\',\'社会学\',\'佛教\']\n    #book_tag_lists = [\'思想\',\'科技\',\'科学\',\'web\',\'股票\',\'爱情\',\'两性\']\n    #book_tag_lists = [\'计算机\',\'机器学习\',\'linux\',\'android\',\'数据库\',\'互联网\']\n    #book_tag_lists = [\'数学\']\n    #book_tag_lists = [\'摄影\',\'设计\',\'音乐\',\'旅行\',\'教育\',\'成长\',\'情感\',\'育儿\',\'健康\',\'养生\']\n    #book_tag_lists = [\'商业\',\'理财\',\'管理\']  \n    #book_tag_lists = [\'名著\']\n    #book_tag_lists = [\'科普\',\'经典\',\'生活\',\'心灵\',\'文学\']\n    #book_tag_lists = [\'科幻\',\'思维\',\'金融\']\n    book_tag_lists = [\'个人管理\',\'时间管理\',\'投资\',\'文化\',\'宗教\']\n    book_lists=do_spider(book_tag_lists)\n    print_book_lists_excel(book_lists,book_tag_lists)\n    \n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": "#-*- coding: UTF-8 -*-\n\nimport sys\nimport time\nimport urllib\nimport urllib2\nimport requests\nimport numpy as np\nfrom bs4 import BeautifulSoup\nfrom openpyxl import Workbook\n\nreload(sys)\nsys.setdefaultencoding('utf8')\n\n\n\n#Some User Agents\nhds=[{'User-Agent':'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6'},\\\n{'User-Agent':'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11'},\\\n{'User-Agent': 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)'}]\n\n\ndef book_spider(book_tag):\n    page_num=0;\n    book_list=[]\n    try_times=0\n    \n    while(1):\n        #url='http://www.douban.com/tag/%E5%B0%8F%E8%AF%B4/book?start=0' # For Test\n        url='http://www.douban.com/tag/'+urllib.quote(book_tag)+'/book?start='+str(page_num*15)\n        time.sleep(np.random.rand()*5)\n        \n        #Last Version\n        try:\n            req = urllib2.Request(url, headers=hds[page_num%len(hds)])\n            source_code = urllib2.urlopen(req).read()\n            plain_text=str(source_code)   \n        except (urllib2.HTTPError, urllib2.URLError), e:\n            print e\n            continue\n  \n        ##Previous Version, IP is easy to be Forbidden\n        #source_code = requests.get(url) \n        #plain_text = source_code.text  \n        \n        soup = BeautifulSoup(plain_text)\n        list_soup = soup.find('div', {'class': 'mod book-list'})\n        \n        try_times+=1;\n        if list_soup==None and try_times<200:\n            continue\n        elif list_soup==None or len(list_soup)<=1:\n            break # Break when no informatoin got after 200 times requesting\n        \n        for book_info in list_soup.findAll('dd'):\n            title = book_info.find('a', {'class':'title'}).string.strip()\n            desc = book_info.find('div', {'class':'desc'}).string.strip()\n            desc_list = desc.split('/')\n            book_url = book_info.find('a', {'class':'title'}).get('href')\n            \n            try:\n                author_info = '作者/译者： ' + '/'.join(desc_list[0:-3])\n            except:\n                author_info ='作者/译者： 暂无'\n            try:\n                pub_info = '出版信息： ' + '/'.join(desc_list[-3:])\n            except:\n                pub_info = '出版信息： 暂无'\n            try:\n                rating = book_info.find('span', {'class':'rating_nums'}).string.strip()\n            except:\n                rating='0.0'\n            try:\n                #people_num = book_info.findAll('span')[2].string.strip()\n                people_num = get_people_num(book_url)\n                people_num = people_num.strip('人评价')\n            except:\n                people_num ='0'\n            \n            book_list.append([title,rating,people_num,author_info,pub_info])\n            try_times=0 #set 0 when got valid information\n        page_num+=1\n        print 'Downloading Information From Page %d' % page_num\n    return book_list\n\n\ndef get_people_num(url):\n    #url='http://book.douban.com/subject/6082808/?from=tag_all' # For Test\n    try:\n        req = urllib2.Request(url, headers=hds[np.random.randint(0,len(hds))])\n        source_code = urllib2.urlopen(req).read()\n        plain_text=str(source_code)   \n    except (urllib2.HTTPError, urllib2.URLError), e:\n        print e\n    soup = BeautifulSoup(plain_text)\n    people_num=soup.find('div',{'class':'rating_sum'}).findAll('span')[1].string.strip()\n    return people_num\n\n\ndef do_spider(book_tag_lists):\n    book_lists=[]\n    for book_tag in book_tag_lists:\n        book_list=book_spider(book_tag)\n        book_list=sorted(book_list,key=lambda x:x[1],reverse=True)\n        book_lists.append(book_list)\n    return book_lists\n\n\ndef print_book_lists_excel(book_lists,book_tag_lists):\n    wb=Workbook(optimized_write=True)\n    ws=[]\n    for i in range(len(book_tag_lists)):\n        ws.append(wb.create_sheet(title=book_tag_lists[i].decode())) #utf8->unicode\n    for i in range(len(book_tag_lists)): \n        ws[i].append(['序号','书名','评分','评价人数','作者','出版社'])\n        count=1\n        for bl in book_lists[i]:\n            ws[i].append([count,bl[0],float(bl[1]),int(bl[2]),bl[3],bl[4]])\n            count+=1\n    save_path='book_list'\n    for i in range(len(book_tag_lists)):\n        save_path+=('-'+book_tag_lists[i].decode())\n    save_path+='.xlsx'\n    wb.save(save_path)\n\n\n\n\nif __name__=='__main__':\n    #book_tag_lists = ['心理','判断与决策','算法','数据结构','经济','历史']\n    #book_tag_lists = ['传记','哲学','编程','创业','理财','社会学','佛教']\n    #book_tag_lists = ['思想','科技','科学','web','股票','爱情','两性']\n    #book_tag_lists = ['计算机','机器学习','linux','android','数据库','互联网']\n    #book_tag_lists = ['数学']\n    #book_tag_lists = ['摄影','设计','音乐','旅行','教育','成长','情感','育儿','健康','养生']\n    #book_tag_lists = ['商业','理财','管理']  \n    #book_tag_lists = ['名著']\n    #book_tag_lists = ['科普','经典','生活','心灵','文学']\n    #book_tag_lists = ['科幻','思维','金融']\n    book_tag_lists = ['个人管理','时间管理','投资','文化','宗教']\n    book_lists=do_spider(book_tag_lists)\n    print_book_lists_excel(book_lists,book_tag_lists)\n    \n",
        "original_format": 'requests',
        "source_url": 'https://github.com/lanbing510/DouBanSpider',
        "author": "community",
        "tags": ['豆瓣读书', 'requests', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: Bilibili视频
    # ═══════════════════════════════════════
    {
        "name": 'Bilibili视频',
        "description": '社区爬虫 - Bilibili视频（来自 GitHub airingursb/bilibili-video）',
        "category": 'social',
        "icon": '📺',
        "target_url": 'https://www.bilibili.com',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n# -*-coding:utf8-*-\n\nfrom lxml import etree\nfrom multiprocessing.dummy import Pool as ThreadPool\nimport requests\nimport time\nimport sys\nimport re\nimport json\nimport MySQLdb\n\nreload(sys)\n\nsys.setdefaultencoding(\'utf-8\')\n\n# id av cid title tminfo time click danmu coins favourites duration honor_click honor_coins honor_favourites\n# mid name article fans tags[3] common\n\nurls = []\n\nhead = {\n    \'User-Agent\': \'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.130 Safari/537.36\'\n}\n\ntime1 = time.time()\n\nfor i in range(17501, 100000):\n    url = \'http://bilibili.com/video/av\' + str(i)\n    urls.append(url)\n\n\ndef spider(url):\n    html = requests.get(url, headers=head)\n    selector = etree.HTML(html.text)\n    content = selector.xpath("//html")\n    for each in content:\n        title = each.xpath(\'//div[@class="v-title"]/h1/@title\')\n        if title:\n            av = url.replace("http://bilibili.com/video/av", "")\n            title = title[0]\n            tminfo1_log = each.xpath(\'//div[@class="tminfo"]/a/text()\')\n            tminfo2_log = each.xpath(\'//div[@class="tminfo"]/span[1]/a/text()\')\n            tminfo3_log = each.xpath(\'//div[@class="tminfo"]/span[2]/a/text()\')\n            if tminfo1_log:\n                tminfo1 = tminfo1_log[0]\n            else:\n                tminfo1 = ""\n            if tminfo2_log:\n                tminfo2 = tminfo2_log[0]\n            else:\n                tminfo2 = ""\n            if tminfo3_log:\n                tminfo3 = tminfo3_log[0]\n            else:\n                tminfo3 = ""\n            tminfo = tminfo1 + \'-\' + tminfo2 + \'-\' + tminfo3\n            time_log = each.xpath(\'//div[@class="tminfo"]/time/i/text()\')\n            mid_log = each.xpath(\'//div[@class="b-btn f hide"]/@mid\')\n            name_log = each.xpath(\'//div[@class="usname"]/a/@title\')\n            article_log = each.xpath(\'//div[@class="up-video-message"]/div[1]/text()\')\n            fans_log = each.xpath(\'//div[@class="up-video-message"]/div[2]/text()\')\n\n            if time_log:\n                time = time_log[0]\n            else:\n                time = ""\n            if mid_log:\n                mid = mid_log[0]\n            else:\n                mid = ""\n            if name_log:\n                name = name_log[0]\n            else:\n                name = ""\n            if article_log:\n                article = article_log[0].replace(u"投稿：","")\n            else:\n                article = "-1"\n            if fans_log:\n                fans = fans_log[0].replace(u"粉丝：","")\n            else:\n                fans = "-1"\n\n            tag1_log = each.xpath(\'//ul[@class="tag-list"]/li[1]/a/text()\')\n            tag2_log = each.xpath(\'//ul[@class="tag-list"]/li[2]/a/text()\')\n            tag3_log = each.xpath(\'//ul[@class="tag-list"]/li[3]/a/text()\')\n            if tag1_log:\n                tag1 = tag1_log[0]\n            else:\n                tag1 = ""\n            if tag2_log:\n                tag2 = tag2_log[0]\n            else:\n                tag2 = ""\n            if tag3_log:\n                tag3 = tag3_log[0]\n            else:\n                tag3 = ""\n\n            cid_html_1 = each.xpath(\'//div[@class="scontent"]/iframe/@src\')\n            cid_html_2 = each.xpath(\'//div[@class="scontent"]/script/text()\')\n            if cid_html_1 or cid_html_2:\n                if cid_html_1:\n                    cid_html = cid_html_1[0]\n                else:\n                    cid_html = cid_html_2[0]\n\n                cids = re.findall(r\'cid=.+&aid\', cid_html)\n                cid = cids[0].replace("cid=", "").replace("&aid", "")\n                info_url = "http://interface.bilibili.com/player?id=cid:" + str(cid) + "&aid=" + av\n                video_info = requests.get(info_url)\n                video_selector = etree.HTML(video_info.text)\n                for video_each in video_selector:\n                    click_log = video_each.xpath(\'//click/text()\')\n                    danmu_log = video_each.xpath(\'//danmu/text()\')\n                    coins_log = video_each.xpath(\'//coins/text()\')\n                    favourites_log = video_each.xpath(\'//favourites/text()\')\n                    duration_log = video_each.xpath(\'//duration/text()\')\n                    honor_click_log = video_each.xpath(\'//honor[@t="click"]/text()\')\n                    honor_coins_log = video_each.xpath(\'//honor[@t="coins"]/text()\')\n                    honor_favourites_log = video_each.xpath(\'//honor[@t="favourites"]/text()\')\n\n                    if honor_click_log:\n                        honor_click = honor_click_log[0]\n                    else:\n                        honor_click = 0\n                    if honor_coins_log:\n                        honor_coins = honor_coins_log[0]\n                    else:\n                        honor_coins = 0\n                    if honor_favourites_log:\n                        honor_favourites = honor_favourites_log[0]\n                    else:\n                        honor_favourites = 0\n\n                    if click_log:\n                        click = click_log[0]\n                    else:\n                        click = -1\n                    if danmu_log:\n                        danmu = danmu_log[0]\n                    else:\n                        danmu = -1\n                    if coins_log:\n                        coins = coins_log[0]\n                    else:\n                        coins = -1\n                    if favourites_log:\n                        favourites = favourites_log[0]\n                    else:\n                        favourites = -1\n                    if duration_log:\n                        duration = duration_log[0]\n                    else:\n                        duration = ""\n\n                    json_url = "http://api.bilibili.com/x/reply?jsonp=jsonp&type=1&sort=0&pn=1&nohot=1&oid=" + av\n                    jsoncontent = requests.get(json_url, headers=head).content\n                    jsDict = json.loads(jsoncontent)\n                    if jsDict[\'code\'] == 0:\n                        jsData = jsDict[\'data\']\n                        jsPages = jsData[\'page\']\n                        common = jsPages[\'acount\']\n                        try:\n                            conn = MySQLdb.connect(host=\'localhost\', user=\'root\', passwd=\'\', port=3306, charset=\'utf8\')\n                            cur = conn.cursor()\n                            conn.select_db(\'python\')\n                            cur.execute(\'INSERT INTO video VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)\',\n                                                [str(av), str(av), cid, title, tminfo, time, click, danmu, coins, favourites, duration,\n                                                 mid, name, article, fans, tag1, tag2, tag3, str(common), honor_click, honor_coins, honor_favourites])\n\n                            print "Succeed: av" + str(av)\n                        except MySQLdb.Error, e:\n                            print "Mysql Error %d: %s" % (e.args[0], e.args[1])\n                    else:\n                        print "Error_Json: " + url\n            else:\n                print "Error_noCid:" + url\n        else:\n            print "Error_404: " + url\n\n\npool = ThreadPool(10)\n# results = pool.map(spider, urls)\ntry:\n    results = pool.map(spider, urls)\nexcept Exception, e:\n    # print \'ConnectionError\'\n    print e\n    time.sleep(300)\n    results = pool.map(spider, urls)\n\npool.close()\npool.join()\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": '# -*-coding:utf8-*-\n\nfrom lxml import etree\nfrom multiprocessing.dummy import Pool as ThreadPool\nimport requests\nimport time\nimport sys\nimport re\nimport json\nimport MySQLdb\n\nreload(sys)\n\nsys.setdefaultencoding(\'utf-8\')\n\n# id av cid title tminfo time click danmu coins favourites duration honor_click honor_coins honor_favourites\n# mid name article fans tags[3] common\n\nurls = []\n\nhead = {\n    \'User-Agent\': \'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.130 Safari/537.36\'\n}\n\ntime1 = time.time()\n\nfor i in range(17501, 100000):\n    url = \'http://bilibili.com/video/av\' + str(i)\n    urls.append(url)\n\n\ndef spider(url):\n    html = requests.get(url, headers=head)\n    selector = etree.HTML(html.text)\n    content = selector.xpath("//html")\n    for each in content:\n        title = each.xpath(\'//div[@class="v-title"]/h1/@title\')\n        if title:\n            av = url.replace("http://bilibili.com/video/av", "")\n            title = title[0]\n            tminfo1_log = each.xpath(\'//div[@class="tminfo"]/a/text()\')\n            tminfo2_log = each.xpath(\'//div[@class="tminfo"]/span[1]/a/text()\')\n            tminfo3_log = each.xpath(\'//div[@class="tminfo"]/span[2]/a/text()\')\n            if tminfo1_log:\n                tminfo1 = tminfo1_log[0]\n            else:\n                tminfo1 = ""\n            if tminfo2_log:\n                tminfo2 = tminfo2_log[0]\n            else:\n                tminfo2 = ""\n            if tminfo3_log:\n                tminfo3 = tminfo3_log[0]\n            else:\n                tminfo3 = ""\n            tminfo = tminfo1 + \'-\' + tminfo2 + \'-\' + tminfo3\n            time_log = each.xpath(\'//div[@class="tminfo"]/time/i/text()\')\n            mid_log = each.xpath(\'//div[@class="b-btn f hide"]/@mid\')\n            name_log = each.xpath(\'//div[@class="usname"]/a/@title\')\n            article_log = each.xpath(\'//div[@class="up-video-message"]/div[1]/text()\')\n            fans_log = each.xpath(\'//div[@class="up-video-message"]/div[2]/text()\')\n\n            if time_log:\n                time = time_log[0]\n            else:\n                time = ""\n            if mid_log:\n                mid = mid_log[0]\n            else:\n                mid = ""\n            if name_log:\n                name = name_log[0]\n            else:\n                name = ""\n            if article_log:\n                article = article_log[0].replace(u"投稿：","")\n            else:\n                article = "-1"\n            if fans_log:\n                fans = fans_log[0].replace(u"粉丝：","")\n            else:\n                fans = "-1"\n\n            tag1_log = each.xpath(\'//ul[@class="tag-list"]/li[1]/a/text()\')\n            tag2_log = each.xpath(\'//ul[@class="tag-list"]/li[2]/a/text()\')\n            tag3_log = each.xpath(\'//ul[@class="tag-list"]/li[3]/a/text()\')\n            if tag1_log:\n                tag1 = tag1_log[0]\n            else:\n                tag1 = ""\n            if tag2_log:\n                tag2 = tag2_log[0]\n            else:\n                tag2 = ""\n            if tag3_log:\n                tag3 = tag3_log[0]\n            else:\n                tag3 = ""\n\n            cid_html_1 = each.xpath(\'//div[@class="scontent"]/iframe/@src\')\n            cid_html_2 = each.xpath(\'//div[@class="scontent"]/script/text()\')\n            if cid_html_1 or cid_html_2:\n                if cid_html_1:\n                    cid_html = cid_html_1[0]\n                else:\n                    cid_html = cid_html_2[0]\n\n                cids = re.findall(r\'cid=.+&aid\', cid_html)\n                cid = cids[0].replace("cid=", "").replace("&aid", "")\n                info_url = "http://interface.bilibili.com/player?id=cid:" + str(cid) + "&aid=" + av\n                video_info = requests.get(info_url)\n                video_selector = etree.HTML(video_info.text)\n                for video_each in video_selector:\n                    click_log = video_each.xpath(\'//click/text()\')\n                    danmu_log = video_each.xpath(\'//danmu/text()\')\n                    coins_log = video_each.xpath(\'//coins/text()\')\n                    favourites_log = video_each.xpath(\'//favourites/text()\')\n                    duration_log = video_each.xpath(\'//duration/text()\')\n                    honor_click_log = video_each.xpath(\'//honor[@t="click"]/text()\')\n                    honor_coins_log = video_each.xpath(\'//honor[@t="coins"]/text()\')\n                    honor_favourites_log = video_each.xpath(\'//honor[@t="favourites"]/text()\')\n\n                    if honor_click_log:\n                        honor_click = honor_click_log[0]\n                    else:\n                        honor_click = 0\n                    if honor_coins_log:\n                        honor_coins = honor_coins_log[0]\n                    else:\n                        honor_coins = 0\n                    if honor_favourites_log:\n                        honor_favourites = honor_favourites_log[0]\n                    else:\n                        honor_favourites = 0\n\n                    if click_log:\n                        click = click_log[0]\n                    else:\n                        click = -1\n                    if danmu_log:\n                        danmu = danmu_log[0]\n                    else:\n                        danmu = -1\n                    if coins_log:\n                        coins = coins_log[0]\n                    else:\n                        coins = -1\n                    if favourites_log:\n                        favourites = favourites_log[0]\n                    else:\n                        favourites = -1\n                    if duration_log:\n                        duration = duration_log[0]\n                    else:\n                        duration = ""\n\n                    json_url = "http://api.bilibili.com/x/reply?jsonp=jsonp&type=1&sort=0&pn=1&nohot=1&oid=" + av\n                    jsoncontent = requests.get(json_url, headers=head).content\n                    jsDict = json.loads(jsoncontent)\n                    if jsDict[\'code\'] == 0:\n                        jsData = jsDict[\'data\']\n                        jsPages = jsData[\'page\']\n                        common = jsPages[\'acount\']\n                        try:\n                            conn = MySQLdb.connect(host=\'localhost\', user=\'root\', passwd=\'\', port=3306, charset=\'utf8\')\n                            cur = conn.cursor()\n                            conn.select_db(\'python\')\n                            cur.execute(\'INSERT INTO video VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)\',\n                                                [str(av), str(av), cid, title, tminfo, time, click, danmu, coins, favourites, duration,\n                                                 mid, name, article, fans, tag1, tag2, tag3, str(common), honor_click, honor_coins, honor_favourites])\n\n                            print "Succeed: av" + str(av)\n                        except MySQLdb.Error, e:\n                            print "Mysql Error %d: %s" % (e.args[0], e.args[1])\n                    else:\n                        print "Error_Json: " + url\n            else:\n                print "Error_noCid:" + url\n        else:\n            print "Error_404: " + url\n\n\npool = ThreadPool(10)\n# results = pool.map(spider, urls)\ntry:\n    results = pool.map(spider, urls)\nexcept Exception, e:\n    # print \'ConnectionError\'\n    print e\n    time.sleep(300)\n    results = pool.map(spider, urls)\n\npool.close()\npool.join()\n',
        "original_format": 'requests',
        "source_url": 'https://github.com/airingursb/bilibili-video',
        "author": "community",
        "tags": ['Bilibili视频', 'requests', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: 网易云音乐
    # ═══════════════════════════════════════
    {
        "name": '网易云音乐',
        "description": '社区爬虫 - 网易云音乐（来自 GitHub RitterHou/music-163）',
        "category": 'life',
        "icon": '🎵',
        "target_url": 'https://music.163.com',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n"""\n根据歌曲 ID 获得所有的歌曲所对应的评论信息\n"""\n\nimport requests\nfrom music_163 import sql\nimport time\nimport threading\nimport pymysql.cursors\n\n\nclass Comments(object):\n    headers = {\n        \'Host\': \'music.163.com\',\n        \'Connection\': \'keep-alive\',\n        \'Content-Length\': \'484\',\n        \'Cache-Control\': \'max-age=0\',\n        \'Origin\': \'http://music.163.com\',\n        \'User-Agent\': \'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36\',\n        \'Content-Type\': \'application/x-www-form-urlencoded\',\n        \'Accept\': \'*/*\',\n        \'DNT\': \'1\',\n        \'Accept-Encoding\': \'gzip, deflate\',\n        \'Accept-Language\': \'zh-CN,zh;q=0.8,en;q=0.6,zh-TW;q=0.4\',\n        \'Cookie\': \'JSESSIONID-WYYY=b66d89ed74ae9e94ead89b16e475556e763dd34f95e6ca357d06830a210abc7b685e82318b9d1d5b52ac4f4b9a55024c7a34024fddaee852404ed410933db994dcc0e398f61e670bfeea81105cbe098294e39ac566e1d5aa7232df741870ba1fe96e5cede8372ca587275d35c1a5d1b23a11e274a4c249afba03e20fa2dafb7a16eebdf6%3A1476373826753; _iuqxldmzr_=25; _ntes_nnid=7fa73e96706f26f3ada99abba6c4a6b2,1476372027128; _ntes_nuid=7fa73e96706f26f3ada99abba6c4a6b2; __utma=94650624.748605760.1476372027.1476372027.1476372027.1; __utmb=94650624.4.10.1476372027; __utmc=94650624; __utmz=94650624.1476372027.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none)\',\n    }\n\n    params = {\n        \'csrf_token\': \'\'\n    }\n\n    data = {\n        \'params\': \'Ak2s0LoP1GRJYqE3XxJUZVYK9uPEXSTttmAS+8uVLnYRoUt/Xgqdrt/13nr6OYhi75QSTlQ9FcZaWElIwE+oz9qXAu87t2DHj6Auu+2yBJDr+arG+irBbjIvKJGfjgBac+kSm2ePwf4rfuHSKVgQu1cYMdqFVnB+ojBsWopHcexbvLylDIMPulPljAWK6MR8\',\n        \'encSecKey\': \'8c85d1b6f53bfebaf5258d171f3526c06980cbcaf490d759eac82145ee27198297c152dd95e7ea0f08cfb7281588cdab305946e01b9d84f0b49700f9c2eb6eeced8624b16ce378bccd24341b1b5ad3d84ebd707dbbd18a4f01c2a007cd47de32f28ca395c9715afa134ed9ee321caa7f28ec82b94307d75144f6b5b134a9ce1a\'\n    }\n\n    proxies = {\'http\': \'http://127.0.0.1:10800\'}\n\n    def get_comments(self, music_id, flag):\n        self.headers[\'Referer\'] = \'http://music.163.com/playlist?id=\' + str(music_id)\n        if flag:\n            r = requests.post(\'http://music.163.com/weapi/v1/resource/comments/R_SO_4_\' + str(music_id),\n                              headers=self.headers, params=self.params, data=self.data, proxies=self.proxies)\n        else:\n            r = requests.post(\'http://music.163.com/weapi/v1/resource/comments/R_SO_4_\' + str(music_id),\n                              headers=self.headers, params=self.params, data=self.data)\n        return r.json()\n\n\nif __name__ == \'__main__\':\n    my_comment = Comments()\n\n\n    def save_comments(musics, flag, connection0):\n        for i in musics:\n            my_music_id = i[\'MUSIC_ID\']\n            try:\n                comments = my_comment.get_comments(my_music_id, flag)\n                if comments[\'total\'] > 0:\n                    sql.insert_comments(my_music_id, comments[\'total\'], str(comments), connection0)\n            except Exception as e:\n                # 打印错误日志\n                print(my_music_id)\n                print(e)\n                time.sleep(5)\n\n\n    music_before = sql.get_before_music()\n    music_after = sql.get_after_music()\n\n    # pymysql 链接不是线程安全的\n    connection1 = pymysql.connect(host=\'localhost\',\n                                  user=\'root\',\n                                  password=\'1234\',\n                                  db=\'test\',\n                                  charset=\'utf8mb4\',\n                                  cursorclass=pymysql.cursors.DictCursor)\n\n    connection2 = pymysql.connect(host=\'localhost\',\n                                  user=\'root\',\n                                  password=\'1234\',\n                                  db=\'test\',\n                                  charset=\'utf8mb4\',\n                                  cursorclass=pymysql.cursors.DictCursor)\n\n    t1 = threading.Thread(target=save_comments, args=(music_before, True, connection1))\n    t2 = threading.Thread(target=save_comments, args=(music_after, False, connection2))\n    t1.start()\n    t2.start()\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": '"""\n根据歌曲 ID 获得所有的歌曲所对应的评论信息\n"""\n\nimport requests\nfrom music_163 import sql\nimport time\nimport threading\nimport pymysql.cursors\n\n\nclass Comments(object):\n    headers = {\n        \'Host\': \'music.163.com\',\n        \'Connection\': \'keep-alive\',\n        \'Content-Length\': \'484\',\n        \'Cache-Control\': \'max-age=0\',\n        \'Origin\': \'http://music.163.com\',\n        \'User-Agent\': \'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36\',\n        \'Content-Type\': \'application/x-www-form-urlencoded\',\n        \'Accept\': \'*/*\',\n        \'DNT\': \'1\',\n        \'Accept-Encoding\': \'gzip, deflate\',\n        \'Accept-Language\': \'zh-CN,zh;q=0.8,en;q=0.6,zh-TW;q=0.4\',\n        \'Cookie\': \'JSESSIONID-WYYY=b66d89ed74ae9e94ead89b16e475556e763dd34f95e6ca357d06830a210abc7b685e82318b9d1d5b52ac4f4b9a55024c7a34024fddaee852404ed410933db994dcc0e398f61e670bfeea81105cbe098294e39ac566e1d5aa7232df741870ba1fe96e5cede8372ca587275d35c1a5d1b23a11e274a4c249afba03e20fa2dafb7a16eebdf6%3A1476373826753; _iuqxldmzr_=25; _ntes_nnid=7fa73e96706f26f3ada99abba6c4a6b2,1476372027128; _ntes_nuid=7fa73e96706f26f3ada99abba6c4a6b2; __utma=94650624.748605760.1476372027.1476372027.1476372027.1; __utmb=94650624.4.10.1476372027; __utmc=94650624; __utmz=94650624.1476372027.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none)\',\n    }\n\n    params = {\n        \'csrf_token\': \'\'\n    }\n\n    data = {\n        \'params\': \'Ak2s0LoP1GRJYqE3XxJUZVYK9uPEXSTttmAS+8uVLnYRoUt/Xgqdrt/13nr6OYhi75QSTlQ9FcZaWElIwE+oz9qXAu87t2DHj6Auu+2yBJDr+arG+irBbjIvKJGfjgBac+kSm2ePwf4rfuHSKVgQu1cYMdqFVnB+ojBsWopHcexbvLylDIMPulPljAWK6MR8\',\n        \'encSecKey\': \'8c85d1b6f53bfebaf5258d171f3526c06980cbcaf490d759eac82145ee27198297c152dd95e7ea0f08cfb7281588cdab305946e01b9d84f0b49700f9c2eb6eeced8624b16ce378bccd24341b1b5ad3d84ebd707dbbd18a4f01c2a007cd47de32f28ca395c9715afa134ed9ee321caa7f28ec82b94307d75144f6b5b134a9ce1a\'\n    }\n\n    proxies = {\'http\': \'http://127.0.0.1:10800\'}\n\n    def get_comments(self, music_id, flag):\n        self.headers[\'Referer\'] = \'http://music.163.com/playlist?id=\' + str(music_id)\n        if flag:\n            r = requests.post(\'http://music.163.com/weapi/v1/resource/comments/R_SO_4_\' + str(music_id),\n                              headers=self.headers, params=self.params, data=self.data, proxies=self.proxies)\n        else:\n            r = requests.post(\'http://music.163.com/weapi/v1/resource/comments/R_SO_4_\' + str(music_id),\n                              headers=self.headers, params=self.params, data=self.data)\n        return r.json()\n\n\nif __name__ == \'__main__\':\n    my_comment = Comments()\n\n\n    def save_comments(musics, flag, connection0):\n        for i in musics:\n            my_music_id = i[\'MUSIC_ID\']\n            try:\n                comments = my_comment.get_comments(my_music_id, flag)\n                if comments[\'total\'] > 0:\n                    sql.insert_comments(my_music_id, comments[\'total\'], str(comments), connection0)\n            except Exception as e:\n                # 打印错误日志\n                print(my_music_id)\n                print(e)\n                time.sleep(5)\n\n\n    music_before = sql.get_before_music()\n    music_after = sql.get_after_music()\n\n    # pymysql 链接不是线程安全的\n    connection1 = pymysql.connect(host=\'localhost\',\n                                  user=\'root\',\n                                  password=\'1234\',\n                                  db=\'test\',\n                                  charset=\'utf8mb4\',\n                                  cursorclass=pymysql.cursors.DictCursor)\n\n    connection2 = pymysql.connect(host=\'localhost\',\n                                  user=\'root\',\n                                  password=\'1234\',\n                                  db=\'test\',\n                                  charset=\'utf8mb4\',\n                                  cursorclass=pymysql.cursors.DictCursor)\n\n    t1 = threading.Thread(target=save_comments, args=(music_before, True, connection1))\n    t2 = threading.Thread(target=save_comments, args=(music_after, False, connection2))\n    t1.start()\n    t2.start()\n',
        "original_format": 'requests',
        "source_url": 'https://github.com/RitterHou/music-163',
        "author": "community",
        "tags": ['网易云音乐', 'requests', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: 知乎话题
    # ═══════════════════════════════════════
    {
        "name": '知乎话题',
        "description": '社区爬虫 - 知乎话题（来自 GitHub LiuRoy/zhihu_spider）',
        "category": 'social',
        "icon": '💬',
        "target_url": 'https://www.zhihu.com',
        "mode": "code_generator",
        "code": '# Auto-adapted from Scrapy spider\nimport asyncio\n\ntry:\n    from scrapy.crawler import CrawlerRunner\n    from scrapy.utils.project import get_project_settings\n    from scrapy import signals\n    import scrapy\n    _HAS_SCRAPY = True\nexcept ImportError:\n    _HAS_SCRAPY = False\n\n# --- Original Scrapy Code ---\n# -*- coding=utf8 -*-\nfrom scrapy import cmdline\n\ncmdline.execute("scrapy crawl zhihu".split())\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs Scrapy spider and collects items."""\n    if not _HAS_SCRAPY:\n        return [{"error": "scrapy not installed. Run: pip install scrapy"}]\n\n    items = []\n    import inspect\n    spider_classes = [obj for name, obj in globals().items()\n                     if inspect.isclass(obj) and issubclass(obj, scrapy.Spider) and obj is not scrapy.Spider]\n\n    if not spider_classes:\n        return [{"error": "No Spider class found in code"}]\n\n    SpiderClass = spider_classes[0]\n    if url:\n        SpiderClass.start_urls = [url]\n\n    from scrapy.utils.log import configure_logging\n    configure_logging({"LOG_ENABLED": False})\n\n    settings = get_project_settings()\n    settings.update({\n        "LOG_ENABLED": False,\n        "ROBOTSTXT_OBEY": False,\n    })\n\n    runner = CrawlerRunner(settings)\n\n    def item_scraped(item, **kwargs):\n        items.append(dict(item))\n\n    crawler = runner.create_crawler(SpiderClass)\n    crawler.signals.connect(item_scraped, signal=signals.item_scraped)\n\n    await runner.crawl(crawler)\n    return items\n',
        "original_code": '# -*- coding=utf8 -*-\nfrom scrapy import cmdline\n\ncmdline.execute("scrapy crawl zhihu".split())\n',
        "original_format": 'scrapy',
        "source_url": 'https://github.com/LiuRoy/zhihu_spider',
        "author": "community",
        "tags": ['知乎话题', 'scrapy', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: 京东商品
    # ═══════════════════════════════════════
    {
        "name": '京东商品',
        "description": '社区爬虫 - 京东商品（来自 GitHub taizilongxu/scrapy_jingdong）',
        "category": 'ecommerce',
        "icon": '🛒',
        "target_url": 'https://www.jd.com',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n# -*- coding: utf-8 -*-\n\n# Scrapy settings for tutorial project\n#\n# For simplicity, this file contains only the most important settings by\n# default. All the other settings are documented here:\n#\n#     http://doc.scrapy.org/en/latest/topics/settings.html\n#\n\nBOT_NAME = \'tutorial\'\n\nSPIDER_MODULES = [\'tutorial.spiders\']\nNEWSPIDER_MODULE = \'tutorial.spiders\'\n\n# Crawl responsibly by identifying yourself (and your website) on the user-agent\n#USER_AGENT = \'tutorial (+http://www.yourdomain.com)\'\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": "# -*- coding: utf-8 -*-\n\n# Scrapy settings for tutorial project\n#\n# For simplicity, this file contains only the most important settings by\n# default. All the other settings are documented here:\n#\n#     http://doc.scrapy.org/en/latest/topics/settings.html\n#\n\nBOT_NAME = 'tutorial'\n\nSPIDER_MODULES = ['tutorial.spiders']\nNEWSPIDER_MODULE = 'tutorial.spiders'\n\n# Crawl responsibly by identifying yourself (and your website) on the user-agent\n#USER_AGENT = 'tutorial (+http://www.yourdomain.com)'\n",
        "original_format": 'unknown',
        "source_url": 'https://github.com/taizilongxu/scrapy_jingdong',
        "author": "community",
        "tags": ['京东商品', 'unknown', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: 新浪微博
    # ═══════════════════════════════════════
    {
        "name": '新浪微博',
        "description": '社区爬虫 - 新浪微博（来自 GitHub LiuXingMing/SinaSpider）',
        "category": 'social',
        "icon": '📱',
        "target_url": 'https://weibo.com',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n# encoding=utf-8\n\n# __________________________________________\n#   增加了向Mysql数据库中保存pipeline\n#   需要有MysqlDB,同时修改Spider文件，增加Item类所有变量的if else的返回值，使得可以标准化存储       \n#   Updated by Charles Yan\n#   Date:2017.1.4\n#   Added Mysql insert method\n# ------------------------------------------\n\nimport pymongo\nfrom items import InformationItem, TweetsItem, RelationshipsItem\nimport MySQLdb\n\nclass MysqlDBPipleline(object):\n    def __init__(self):\n        self.count = 1\n        self.conn = MySQLdb.connect(\n                host=\'localhost\',\n                port=3306,\n                user=\'root\',\n                #这里填写密码\n                passwd=\'***\',\n                db=\'SinaWeibo\',\n                charset=\'utf8\',\n                )\n        self.cur = self.conn.cursor()\n\n    def process_item(self, item, spider):\n        """ 判断item的类型，并作相应的处理，再入数据库 """\n        if isinstance(item, RelationshipsItem):\n            try:\n                print("***********at beginning of saving**********")\n                print(dict(item))\n                sql = \'\'\n                sql+=str(\'INSERT INTO SinaWeibo.Relationship (`Host1`,`Host2`) \')\n                sql+=str(\' Values(\\\'\' )\n                sql+=str(item[\'Host1\'])\n                print(sql)\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Host2\'])\n                sql+=str(\'\\\')\')\n                print("*********** SQL SYNTAX *********** ")\n                print(\'\'.join(sql))\n                self.cur.execute(sql)\n                self.conn.commit()\n                print("saved")\n                self.count = self.count +1\n                print(self.count)\n            except Exception:\n                pass\n        elif isinstance(item, TweetsItem):\n            try:\n                print("***********at beginning of saving**********")\n                \n                sql = \'\'\n                sql+=str(\'INSERT INTO SinaWeibo.Tweets (`weibo_id`,`User_id`,`Content`,`Pubtime`,`Coordinates`,`Tools`,`Likes`,`Comments`,`Transfers`) \')\n                sql+=str(\' Values(\\\'\' )\n                sql+=str(item[\'_id\'])\n           \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'ID\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Content\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'PubTime\'])\n               \n                sql+=str(\'\\\', \\\'\')\n               \n                sql+=str(item[\'Co_oridinates\'])\n               \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Tools\'])\n                print(sql)\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Like\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Comment\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Transfer\'])\n                sql+=str(\'\\\')\')\n                print("*********** SQL SYNTAX *********** ")\n                print(\'\'.join(sql))\n                self.cur.execute(sql)\n                self.conn.commit()\n                print("saved")\n                self.count = self.count +1\n                print(self.count)\n            except Exception:\n                pass\n        elif isinstance(item, InformationItem):\n            try:\n                print("***********at beginning of saving**********")\n                \n                sql = \'\'\n                sql+=str(\'INSERT INTO SinaWeibo.Information (`User_id`,`NickName`,`Gender`,`Province`,`City`,`BriefIntroduction`,`Birthday`,`Num_Tweets`,`Num_Follows`,`Num_Fans`,`SexOrientation`,`Sentiment`,`VIPlevel`,`Authentication`,`URL`) \')\n                sql+=str(\' Values(\\\'\' )\n                sql+=str(item[\'_id\'])\n               \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'NickName\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Gender\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Province\'])\n                \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'City\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'BriefIntroduction\'])\n                sql+=str(\'\\\', \\\'\')\n                print(sql)\n                sql+=str(item[\'Birthday\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Num_Tweets\'])\n               \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Num_Follows\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Num_Fans\'])\n                sql+=str(\'\\\', \\\'\')\n                \n                sql+=str(item[\'SexOrientation\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Sentiment\'])\n                \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'VIPlevel\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Authentication\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'URL\'])\n                sql+=str(\'\\\')\')\n               \n                print("*********** SQL SYNTAX *********** ")\n                print(\'\'.join(sql))\n                self.cur.execute(sql)\n                self.conn.commit()\n                print("saved")\n                self.count = self.count +1\n                print(self.count)\n            except Exception:\n                pass\n            \n            ##在Java开发中，Dao连接会对内存溢出，需要定时断开重连，这里不清楚是否需要，先加上了\n            if self.count == 1000:\n                print("try reconnecting")\n                self.count = 0\n                self.cur.close()\n                self.conn.close()\n                self.conn = MySQLdb.connect(\n                    host=\'localhost\',\n                    port=3306,\n                    user=\'root\',\n                    passwd=\'***\',\n                    db=\'SinaWeibo\',\n                    charset=\'utf8\',\n                )\n                self.cur = self.conn.cursor()\n                print("reconnect")\n                \n        return item\n    \n\n\nclass MongoDBPipleline(object):\n    def __init__(self):\n        clinet = pymongo.MongoClient("localhost", 27017)\n        db = clinet["Sina"]\n        self.Information = db["Information"]\n        self.Tweets = db["Tweets"]\n        self.Relationships = db["Relationships"]\n\n    def process_item(self, item, spider):\n        """ 判断item的类型，并作相应的处理，再入数据库 """\n        if isinstance(item, RelationshipsItem):\n            try:\n                self.Relationships.insert(dict(item))\n            except Exception:\n                pass\n        elif isinstance(item, TweetsItem):\n            try:\n                self.Tweets.insert(dict(item))\n            except Exception:\n                pass\n        elif isinstance(item, InformationItem):\n            try:\n                self.Information.insert(dict(item))\n            except Exception:\n                pass\n        return item\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": '# encoding=utf-8\n\n# __________________________________________\n#   增加了向Mysql数据库中保存pipeline\n#   需要有MysqlDB,同时修改Spider文件，增加Item类所有变量的if else的返回值，使得可以标准化存储       \n#   Updated by Charles Yan\n#   Date:2017.1.4\n#   Added Mysql insert method\n# ------------------------------------------\n\nimport pymongo\nfrom items import InformationItem, TweetsItem, RelationshipsItem\nimport MySQLdb\n\nclass MysqlDBPipleline(object):\n    def __init__(self):\n        self.count = 1\n        self.conn = MySQLdb.connect(\n                host=\'localhost\',\n                port=3306,\n                user=\'root\',\n                #这里填写密码\n                passwd=\'***\',\n                db=\'SinaWeibo\',\n                charset=\'utf8\',\n                )\n        self.cur = self.conn.cursor()\n\n    def process_item(self, item, spider):\n        """ 判断item的类型，并作相应的处理，再入数据库 """\n        if isinstance(item, RelationshipsItem):\n            try:\n                print("***********at beginning of saving**********")\n                print(dict(item))\n                sql = \'\'\n                sql+=str(\'INSERT INTO SinaWeibo.Relationship (`Host1`,`Host2`) \')\n                sql+=str(\' Values(\\\'\' )\n                sql+=str(item[\'Host1\'])\n                print(sql)\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Host2\'])\n                sql+=str(\'\\\')\')\n                print("*********** SQL SYNTAX *********** ")\n                print(\'\'.join(sql))\n                self.cur.execute(sql)\n                self.conn.commit()\n                print("saved")\n                self.count = self.count +1\n                print(self.count)\n            except Exception:\n                pass\n        elif isinstance(item, TweetsItem):\n            try:\n                print("***********at beginning of saving**********")\n                \n                sql = \'\'\n                sql+=str(\'INSERT INTO SinaWeibo.Tweets (`weibo_id`,`User_id`,`Content`,`Pubtime`,`Coordinates`,`Tools`,`Likes`,`Comments`,`Transfers`) \')\n                sql+=str(\' Values(\\\'\' )\n                sql+=str(item[\'_id\'])\n           \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'ID\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Content\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'PubTime\'])\n               \n                sql+=str(\'\\\', \\\'\')\n               \n                sql+=str(item[\'Co_oridinates\'])\n               \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Tools\'])\n                print(sql)\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Like\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Comment\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Transfer\'])\n                sql+=str(\'\\\')\')\n                print("*********** SQL SYNTAX *********** ")\n                print(\'\'.join(sql))\n                self.cur.execute(sql)\n                self.conn.commit()\n                print("saved")\n                self.count = self.count +1\n                print(self.count)\n            except Exception:\n                pass\n        elif isinstance(item, InformationItem):\n            try:\n                print("***********at beginning of saving**********")\n                \n                sql = \'\'\n                sql+=str(\'INSERT INTO SinaWeibo.Information (`User_id`,`NickName`,`Gender`,`Province`,`City`,`BriefIntroduction`,`Birthday`,`Num_Tweets`,`Num_Follows`,`Num_Fans`,`SexOrientation`,`Sentiment`,`VIPlevel`,`Authentication`,`URL`) \')\n                sql+=str(\' Values(\\\'\' )\n                sql+=str(item[\'_id\'])\n               \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'NickName\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Gender\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Province\'])\n                \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'City\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'BriefIntroduction\'])\n                sql+=str(\'\\\', \\\'\')\n                print(sql)\n                sql+=str(item[\'Birthday\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Num_Tweets\'])\n               \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Num_Follows\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Num_Fans\'])\n                sql+=str(\'\\\', \\\'\')\n                \n                sql+=str(item[\'SexOrientation\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Sentiment\'])\n                \n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'VIPlevel\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'Authentication\'])\n                sql+=str(\'\\\', \\\'\')\n                sql+=str(item[\'URL\'])\n                sql+=str(\'\\\')\')\n               \n                print("*********** SQL SYNTAX *********** ")\n                print(\'\'.join(sql))\n                self.cur.execute(sql)\n                self.conn.commit()\n                print("saved")\n                self.count = self.count +1\n                print(self.count)\n            except Exception:\n                pass\n            \n            ##在Java开发中，Dao连接会对内存溢出，需要定时断开重连，这里不清楚是否需要，先加上了\n            if self.count == 1000:\n                print("try reconnecting")\n                self.count = 0\n                self.cur.close()\n                self.conn.close()\n                self.conn = MySQLdb.connect(\n                    host=\'localhost\',\n                    port=3306,\n                    user=\'root\',\n                    passwd=\'***\',\n                    db=\'SinaWeibo\',\n                    charset=\'utf8\',\n                )\n                self.cur = self.conn.cursor()\n                print("reconnect")\n                \n        return item\n    \n\n\nclass MongoDBPipleline(object):\n    def __init__(self):\n        clinet = pymongo.MongoClient("localhost", 27017)\n        db = clinet["Sina"]\n        self.Information = db["Information"]\n        self.Tweets = db["Tweets"]\n        self.Relationships = db["Relationships"]\n\n    def process_item(self, item, spider):\n        """ 判断item的类型，并作相应的处理，再入数据库 """\n        if isinstance(item, RelationshipsItem):\n            try:\n                self.Relationships.insert(dict(item))\n            except Exception:\n                pass\n        elif isinstance(item, TweetsItem):\n            try:\n                self.Tweets.insert(dict(item))\n            except Exception:\n                pass\n        elif isinstance(item, InformationItem):\n            try:\n                self.Information.insert(dict(item))\n            except Exception:\n                pass\n        return item\n',
        "original_format": 'unknown',
        "source_url": 'https://github.com/LiuXingMing/SinaSpider',
        "author": "community",
        "tags": ['新浪微博', 'unknown', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: QQ空间
    # ═══════════════════════════════════════
    {
        "name": 'QQ空间',
        "description": '社区爬虫 - QQ空间（来自 GitHub LiuXingMing/QQSpider）',
        "category": 'social',
        "icon": '👥',
        "target_url": 'https://qzone.qq.com',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n# encoding=utf-8\nimport re\nimport datetime\n\n\nclass InformationSpider(object):\n    """ 功能：爬取QQ个人信息（和空间信息） """\n\n    def __init__(self, spiderMessage, changer):\n        self.message = spiderMessage\n        self.changer = changer\n        self.hash_gender = {0: \'Unknown\', 1: \'男\', 2: \'女\'}\n        self.hash_constellation = {0: \'白羊座\', 1: \'金牛座\', 2: \'双子座\', 3: \'巨蟹座\', 4: \'狮子座\', 5: \'处女座\', 6: \'天秤座\', 7: \'天蝎座\',\n                                   8: \'射手座\', 9: \'魔羯座\', 10: \'水瓶座\', 11: \'双鱼座\'}\n        self.hash_bloodtype = {0: \'Unknown\', 1: \'A\', 2: \'B\', 3: \'O\', 4: \'AB\', 5: \'Others\'}\n        self.hash_marriage = {0: \'Unknown\', 1: \'单身\', 2: \'已婚\', 3: \'保密\', 4: \'恋爱中\', 5: \'已订婚\', 6: \'分居\', 7: \'离异\'}\n\n    def beginer(self):\n        failure = 0\n        while failure < self.message.fail_time:\n            myInformation = {}\n            try:\n                myInformation["_id"] = self.message.qq\n                myInformation["Blogs_WeGet"] = 0\n                myInformation["Moods_WeGet"] = 0\n                myInformation["FriendsNum"] = 0\n                result1 = self.get_personal_information(myInformation)  # 获取个人信息\n                result2 = self.get_qzone_information0(myInformation)  # 获取空间信息\n                result3 = self.get_qzone_information1(myInformation)  # 获取空间访问量\n                if not (result1 and result2 and result3):  # 如果个人信息或者空间信息获取失败\n                    return {}\n                return myInformation\n            except Exception:\n                failure += 1\n        return {}  # 如果失败次数太大\n\n    def get_personal_information(self, information):\n        """ 获取个人信息 """\n        url00 = "http://base.s2.qzone.qq.com/"  # 此请求有两种域名情况\n        url01 = "http://user.qzone.qq.com/p/base.s2/"\n        url1 = "cgi-bin/user/cgi_userinfo_get_all?uin=%s&vuin=%s&fupdate=1&g_tk=%s" % (\n            self.message.qq, self.message.account, str(self.message.gtk))\n        r = self.message.s.get(url00 + url1, timeout=self.message.timeout)\n        if r.status_code == 403:\n            r = self.message.s.get(url01 + url1, timeout=self.message.timeout)\n            if r.status_code == 403:\n                return False\n        text = r.text\n        while u\'请先登录\' in r.text:  # Cookie失效\n            try:\n                self.changer.changeCookie(self.message)\n                url1 = "cgi-bin/user/cgi_userinfo_get_all?uin=%s&vuin=%s&fupdate=1&g_tk=%s" % (\n                    self.message.qq, self.message.account, str(self.message.gtk))\n                r = self.message.s.get(url00 + url1, timeout=self.message.timeout)\n                if r.status_code == 403:\n                    r = self.message.s.get(url01 + url1, timeout=self.message.timeout)\n                    if r.status_code == 403:\n                        return False\n                text = r.text\n            except Exception, e:\n                print "InformationSpider.get_personal_information:获取Cookie失败，此线程关闭！"\n                exit()\n        gender = re.findall(\'"sex":(\\d+)\', text)  # 性别\n        age = re.findall(\'"age":(\\d+)\', text)  # 年龄\n        birthday = re.findall(\'"birthday":"(.*?)"\', text)  # 生日\n        birthyear = re.findall(\'"birthyear":(\\d+)\', text)  # 出生年\n        constellation = re.findall(\'"constellation":(\\d+)\', text)  # 星座\n        bloodtype = re.findall(\'"bloodtype":(\\d+)\', text)  # 血型\n        marriage = re.findall(\'"marriage":(\\d+)\', text)  # 婚姻状况\n        living_country = re.findall(\'"country":"(.*?)"\', text)  # 居住地（国家）\n        living_province = re.findall(\'"province":"(.*?)"\', text)  # 居住地（省份）\n        living_city = re.findall(\'"city":"(.*?)"\', text)  # 居住地（城市）\n        hometown_country = re.findall(\'"hco":"(.*?)"\', text)  # 故乡（国家）\n        hometown_provine = re.findall(\'"hp":"(.*?)"\', text)  # 故乡（省份）\n        hometown_city = re.findall(\'"hc":"(.*?)"\', text)  # 故乡（城市）\n        career = re.findall(\'"career":"(.*?)"\', text)  # 职业\n        company = re.findall(\'"company":"(.*?)"\', text)  # 公司名称\n        company_country = re.findall(\'"cco":"(.*?)"\', text)  # 公司地址（国家）\n        company_province = re.findall(\'"cp":"(.*?)"\', text)  # 公司地址（省份)\n        company_city = re.findall(\'"cc":"(.*?)"\', text)  # 公司地址（城市）\n        company_address = re.findall(\'"cb":"(.*?)"\', text)  # 公司详细地址\n\n        try:\n            information["Gender"] = self.hash_gender[int(gender[0])]\n        except Exception:\n            information["Gender"] = "Unknown"\n        try:\n            information["Age"] = int(age[0])\n        except Exception:\n            information["Age"] = -1\n        try:\n            str_birthday = str(birthyear[0]) + "-" + birthday[0]\n            information["Birthday"] = datetime.datetime.strptime(str_birthday, "%Y-%m-%d") - datetime.timedelta(\n                hours=8)\n        except Exception:\n            information["Birthday"] = datetime.datetime.strptime("1700-01-01", "%Y-%m-%d") - datetime.timedelta(\n                hours=8)\n        try:\n            information["Constellation"] = self.hash_constellation[int(constellation[0])]\n        except Exception:\n            information["Constellation"] = "Unknown"\n        try:\n            information["Bloodtype"] = self.hash_bloodtype[int(bloodtype[0])]\n        except Exception:\n            information["Bloodtype"] = "Unknown"\n        try:\n            information["Marriage"] = self.hash_marriage[int(marriage[0])]\n        except Exception:\n            information["Marriage"] = "Unknown"\n        try:\n            information["Living_country"] = living_country[0]\n        except Exception:\n            information["Living_country"] = "Unknown"\n        try:\n            information["Living_province"] = living_province[0]\n        except Exception:\n            information["Living_province"] = "Unknown"\n        try:\n            information["Living_city"] = living_city[0]\n        except Exception:\n            information["Living_city"] = "Unknown"\n        try:\n            information["Hometown_country"] = hometown_country[0]\n        except Exception:\n            information["Hometown_country"] = "Unknown"\n        try:\n            information["Hometown_provine"] = hometown_provine[0]\n        except Exception:\n            information["Hometown_provine"] = "Unknown"\n        try:\n            information["Hometown_city"] = hometown_city[0]\n        except Exception:\n            information["Hometown_city"] = "Unknown"\n        try:\n            information["Career"] = career[0]\n        except Exception:\n            information["Career"] = "Unknown"\n        try:\n            information["Company"] = company[0]\n        except Exception:\n            information["Company"] = "Unknown"\n        try:\n            information["Company_country"] = company_country[0]\n        except Exception:\n            information["Company_country"] = "Unknown"\n        try:\n            information["Company_province"] = company_province[0]\n        except Exception:\n            information["Company_province"] = "Unknown"\n        try:\n            information["Company_city"] = company_city[0]\n        except Exception:\n            information["Company_city"] = "Unknown"\n        try:\n            information["Company_address"] = company_address[0]\n        except Exception:\n            information["Company_address"] = "Unknown"\n        return True\n\n    def get_qzone_information0(self, information):\n        """ 获取空间信息 """\n        url = "http://snsapp.qzone.qq.com/cgi-bin/qzonenext/getplcount.cgi?hostuin=" + self.message.qq\n        r = self.message.s.get(url, timeout=self.message.timeout)\n        if r.status_code == 403:\n            return False\n        text = r.text\n        if "-4009" in text:\n            return False\n        rz = re.findall(\'"RZ":.*?(\\d+)\', text)  # 日志数\n        ss = re.findall(\'"SS":.*?(\\d+)\', text)  # 说说数\n        xc = re.findall(\'"XC":.*?(\\d+)\', text)  # 相册数\n        ly = re.findall(\'"LY":.*?(\\d+)\', text)  # 留言数\n        currentTime = re.findall(\'"now":(\\d+)\', text)  # 当前时间（Unix时间戳）\n\n        try:\n            information["Blog"] = int(rz[0])\n        except Exception:\n            information["Blog"] = -1\n        try:\n            information["Mood"] = int(ss[0])\n        except Exception:\n            information["Mood"] = -1\n        try:\n            information["Picture"] = int(xc[0])\n        except Exception:\n            information["Picture"] = -1\n        try:\n            information["Message"] = int(ly[0])\n        except Exception:\n            information["Message"] = -1\n        try:\n            information["CurrentTime"] = datetime.datetime.fromtimestamp(int(currentTime[0])) - datetime.timedelta(\n                hours=8)\n        except Exception:\n            information["CurrentTime"] = datetime.datetime.strptime("1700-01-01", "%Y-%m-%d") - datetime.timedelta(\n                hours=8)\n        return True\n\n    def get_qzone_information1(self, information):\n        """ 获取空间访问量 """\n        url = "http://r.qzone.qq.com/cgi-bin/main_page_cgi?uin=" + self.message.qq + "&param=3_" + self.message.qq + "_0%7C8_8_2116417293_0_1_0_0_1%7C16&g_tk=" + str(\n            self.message.gtk)\n        r = self.message.s.get(url, timeout=self.message.timeout)\n        if r.status_code == 403:\n            return False\n        text = r.text\n        if "-4009" in text:\n            return False\n        elif "module_8" not in text:\n            try:\n                self.changer.changeCookie(self.message)\n            except Exception:\n                print "InformationSpider.get_qzone_information1:获取Cookie失败，此线程关闭！"\n                exit()\n        try:\n            pageView_temp1 = re.split(\'"modvisitcount"\', text)[1]\n            pageView_temp2 = re.split(\'"mod":0\', pageView_temp1)[1]\n            pageView = re.findall(\'"totalcount":(\\d+)\', pageView_temp2)  # 空间访问量\n            information["PageView"] = pageView[0]\n        except Exception:\n            information["PageView"] = -1\n        return True\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": '# encoding=utf-8\nimport re\nimport datetime\n\n\nclass InformationSpider(object):\n    """ 功能：爬取QQ个人信息（和空间信息） """\n\n    def __init__(self, spiderMessage, changer):\n        self.message = spiderMessage\n        self.changer = changer\n        self.hash_gender = {0: \'Unknown\', 1: \'男\', 2: \'女\'}\n        self.hash_constellation = {0: \'白羊座\', 1: \'金牛座\', 2: \'双子座\', 3: \'巨蟹座\', 4: \'狮子座\', 5: \'处女座\', 6: \'天秤座\', 7: \'天蝎座\',\n                                   8: \'射手座\', 9: \'魔羯座\', 10: \'水瓶座\', 11: \'双鱼座\'}\n        self.hash_bloodtype = {0: \'Unknown\', 1: \'A\', 2: \'B\', 3: \'O\', 4: \'AB\', 5: \'Others\'}\n        self.hash_marriage = {0: \'Unknown\', 1: \'单身\', 2: \'已婚\', 3: \'保密\', 4: \'恋爱中\', 5: \'已订婚\', 6: \'分居\', 7: \'离异\'}\n\n    def beginer(self):\n        failure = 0\n        while failure < self.message.fail_time:\n            myInformation = {}\n            try:\n                myInformation["_id"] = self.message.qq\n                myInformation["Blogs_WeGet"] = 0\n                myInformation["Moods_WeGet"] = 0\n                myInformation["FriendsNum"] = 0\n                result1 = self.get_personal_information(myInformation)  # 获取个人信息\n                result2 = self.get_qzone_information0(myInformation)  # 获取空间信息\n                result3 = self.get_qzone_information1(myInformation)  # 获取空间访问量\n                if not (result1 and result2 and result3):  # 如果个人信息或者空间信息获取失败\n                    return {}\n                return myInformation\n            except Exception:\n                failure += 1\n        return {}  # 如果失败次数太大\n\n    def get_personal_information(self, information):\n        """ 获取个人信息 """\n        url00 = "http://base.s2.qzone.qq.com/"  # 此请求有两种域名情况\n        url01 = "http://user.qzone.qq.com/p/base.s2/"\n        url1 = "cgi-bin/user/cgi_userinfo_get_all?uin=%s&vuin=%s&fupdate=1&g_tk=%s" % (\n            self.message.qq, self.message.account, str(self.message.gtk))\n        r = self.message.s.get(url00 + url1, timeout=self.message.timeout)\n        if r.status_code == 403:\n            r = self.message.s.get(url01 + url1, timeout=self.message.timeout)\n            if r.status_code == 403:\n                return False\n        text = r.text\n        while u\'请先登录\' in r.text:  # Cookie失效\n            try:\n                self.changer.changeCookie(self.message)\n                url1 = "cgi-bin/user/cgi_userinfo_get_all?uin=%s&vuin=%s&fupdate=1&g_tk=%s" % (\n                    self.message.qq, self.message.account, str(self.message.gtk))\n                r = self.message.s.get(url00 + url1, timeout=self.message.timeout)\n                if r.status_code == 403:\n                    r = self.message.s.get(url01 + url1, timeout=self.message.timeout)\n                    if r.status_code == 403:\n                        return False\n                text = r.text\n            except Exception, e:\n                print "InformationSpider.get_personal_information:获取Cookie失败，此线程关闭！"\n                exit()\n        gender = re.findall(\'"sex":(\\d+)\', text)  # 性别\n        age = re.findall(\'"age":(\\d+)\', text)  # 年龄\n        birthday = re.findall(\'"birthday":"(.*?)"\', text)  # 生日\n        birthyear = re.findall(\'"birthyear":(\\d+)\', text)  # 出生年\n        constellation = re.findall(\'"constellation":(\\d+)\', text)  # 星座\n        bloodtype = re.findall(\'"bloodtype":(\\d+)\', text)  # 血型\n        marriage = re.findall(\'"marriage":(\\d+)\', text)  # 婚姻状况\n        living_country = re.findall(\'"country":"(.*?)"\', text)  # 居住地（国家）\n        living_province = re.findall(\'"province":"(.*?)"\', text)  # 居住地（省份）\n        living_city = re.findall(\'"city":"(.*?)"\', text)  # 居住地（城市）\n        hometown_country = re.findall(\'"hco":"(.*?)"\', text)  # 故乡（国家）\n        hometown_provine = re.findall(\'"hp":"(.*?)"\', text)  # 故乡（省份）\n        hometown_city = re.findall(\'"hc":"(.*?)"\', text)  # 故乡（城市）\n        career = re.findall(\'"career":"(.*?)"\', text)  # 职业\n        company = re.findall(\'"company":"(.*?)"\', text)  # 公司名称\n        company_country = re.findall(\'"cco":"(.*?)"\', text)  # 公司地址（国家）\n        company_province = re.findall(\'"cp":"(.*?)"\', text)  # 公司地址（省份)\n        company_city = re.findall(\'"cc":"(.*?)"\', text)  # 公司地址（城市）\n        company_address = re.findall(\'"cb":"(.*?)"\', text)  # 公司详细地址\n\n        try:\n            information["Gender"] = self.hash_gender[int(gender[0])]\n        except Exception:\n            information["Gender"] = "Unknown"\n        try:\n            information["Age"] = int(age[0])\n        except Exception:\n            information["Age"] = -1\n        try:\n            str_birthday = str(birthyear[0]) + "-" + birthday[0]\n            information["Birthday"] = datetime.datetime.strptime(str_birthday, "%Y-%m-%d") - datetime.timedelta(\n                hours=8)\n        except Exception:\n            information["Birthday"] = datetime.datetime.strptime("1700-01-01", "%Y-%m-%d") - datetime.timedelta(\n                hours=8)\n        try:\n            information["Constellation"] = self.hash_constellation[int(constellation[0])]\n        except Exception:\n            information["Constellation"] = "Unknown"\n        try:\n            information["Bloodtype"] = self.hash_bloodtype[int(bloodtype[0])]\n        except Exception:\n            information["Bloodtype"] = "Unknown"\n        try:\n            information["Marriage"] = self.hash_marriage[int(marriage[0])]\n        except Exception:\n            information["Marriage"] = "Unknown"\n        try:\n            information["Living_country"] = living_country[0]\n        except Exception:\n            information["Living_country"] = "Unknown"\n        try:\n            information["Living_province"] = living_province[0]\n        except Exception:\n            information["Living_province"] = "Unknown"\n        try:\n            information["Living_city"] = living_city[0]\n        except Exception:\n            information["Living_city"] = "Unknown"\n        try:\n            information["Hometown_country"] = hometown_country[0]\n        except Exception:\n            information["Hometown_country"] = "Unknown"\n        try:\n            information["Hometown_provine"] = hometown_provine[0]\n        except Exception:\n            information["Hometown_provine"] = "Unknown"\n        try:\n            information["Hometown_city"] = hometown_city[0]\n        except Exception:\n            information["Hometown_city"] = "Unknown"\n        try:\n            information["Career"] = career[0]\n        except Exception:\n            information["Career"] = "Unknown"\n        try:\n            information["Company"] = company[0]\n        except Exception:\n            information["Company"] = "Unknown"\n        try:\n            information["Company_country"] = company_country[0]\n        except Exception:\n            information["Company_country"] = "Unknown"\n        try:\n            information["Company_province"] = company_province[0]\n        except Exception:\n            information["Company_province"] = "Unknown"\n        try:\n            information["Company_city"] = company_city[0]\n        except Exception:\n            information["Company_city"] = "Unknown"\n        try:\n            information["Company_address"] = company_address[0]\n        except Exception:\n            information["Company_address"] = "Unknown"\n        return True\n\n    def get_qzone_information0(self, information):\n        """ 获取空间信息 """\n        url = "http://snsapp.qzone.qq.com/cgi-bin/qzonenext/getplcount.cgi?hostuin=" + self.message.qq\n        r = self.message.s.get(url, timeout=self.message.timeout)\n        if r.status_code == 403:\n            return False\n        text = r.text\n        if "-4009" in text:\n            return False\n        rz = re.findall(\'"RZ":.*?(\\d+)\', text)  # 日志数\n        ss = re.findall(\'"SS":.*?(\\d+)\', text)  # 说说数\n        xc = re.findall(\'"XC":.*?(\\d+)\', text)  # 相册数\n        ly = re.findall(\'"LY":.*?(\\d+)\', text)  # 留言数\n        currentTime = re.findall(\'"now":(\\d+)\', text)  # 当前时间（Unix时间戳）\n\n        try:\n            information["Blog"] = int(rz[0])\n        except Exception:\n            information["Blog"] = -1\n        try:\n            information["Mood"] = int(ss[0])\n        except Exception:\n            information["Mood"] = -1\n        try:\n            information["Picture"] = int(xc[0])\n        except Exception:\n            information["Picture"] = -1\n        try:\n            information["Message"] = int(ly[0])\n        except Exception:\n            information["Message"] = -1\n        try:\n            information["CurrentTime"] = datetime.datetime.fromtimestamp(int(currentTime[0])) - datetime.timedelta(\n                hours=8)\n        except Exception:\n            information["CurrentTime"] = datetime.datetime.strptime("1700-01-01", "%Y-%m-%d") - datetime.timedelta(\n                hours=8)\n        return True\n\n    def get_qzone_information1(self, information):\n        """ 获取空间访问量 """\n        url = "http://r.qzone.qq.com/cgi-bin/main_page_cgi?uin=" + self.message.qq + "&param=3_" + self.message.qq + "_0%7C8_8_2116417293_0_1_0_0_1%7C16&g_tk=" + str(\n            self.message.gtk)\n        r = self.message.s.get(url, timeout=self.message.timeout)\n        if r.status_code == 403:\n            return False\n        text = r.text\n        if "-4009" in text:\n            return False\n        elif "module_8" not in text:\n            try:\n                self.changer.changeCookie(self.message)\n            except Exception:\n                print "InformationSpider.get_qzone_information1:获取Cookie失败，此线程关闭！"\n                exit()\n        try:\n            pageView_temp1 = re.split(\'"modvisitcount"\', text)[1]\n            pageView_temp2 = re.split(\'"mod":0\', pageView_temp1)[1]\n            pageView = re.findall(\'"totalcount":(\\d+)\', pageView_temp2)  # 空间访问量\n            information["PageView"] = pageView[0]\n        except Exception:\n            information["PageView"] = -1\n        return True\n',
        "original_format": 'unknown',
        "source_url": 'https://github.com/LiuXingMing/QQSpider',
        "author": "community",
        "tags": ['QQ空间', 'unknown', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: Bilibili用户
    # ═══════════════════════════════════════
    {
        "name": 'Bilibili用户',
        "description": '社区爬虫 - Bilibili用户（来自 GitHub airingursb/bilibili-user）',
        "category": 'social',
        "icon": '👤',
        "target_url": 'https://www.bilibili.com',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n# -*-coding:utf8-*-\n\nimport requests\nimport json\nimport random\nimport pymysql\nimport sys\nimport datetime\nimport time\nfrom imp import reload\nfrom multiprocessing.dummy import Pool as ThreadPool\n\ndef datetime_to_timestamp_in_milliseconds(d):\n    def current_milli_time(): return int(round(time.time() * 1000))\n    return current_milli_time()\nreload(sys)\n\n\ndef LoadUserAgents(uafile):\n    uas = []\n    with open(uafile, \'rb\') as uaf:\n        for ua in uaf.readlines():\n            if ua:\n                uas.append(ua.strip()[:-1])\n    random.shuffle(uas)\n    return uas\n\n\nuas = LoadUserAgents("user_agents.txt")\nhead = {\n    \'User-Agent\': \'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36\',\n    \'X-Requested-With\': \'XMLHttpRequest\',\n    \'Referer\': \'http://space.bilibili.com/45388\',\n    \'Origin\': \'http://space.bilibili.com\',\n    \'Host\': \'space.bilibili.com\',\n    \'AlexaToolbar-ALX_NS_PH\': \'AlexaToolbar/alx-4.0\',\n    \'Accept-Language\': \'zh-CN,zh;q=0.8,en;q=0.6,ja;q=0.4\',\n    \'Accept\': \'application/json, text/javascript, */*; q=0.01\',\n}\n\n# Please replace your own proxies.\nproxies = {\n    \'http\': \'http://120.26.110.59:8080\',\n    \'http\': \'http://120.52.32.46:80\',\n    \'http\': \'http://218.85.133.62:80\',\n}\ntime1 = time.time()\n\nurls = []\n\n\n# Please change the range data by yourself.\nfor m in range(5214, 5215):\n\n    for i in range(m * 100, (m + 1) * 100):\n        url = \'https://space.bilibili.com/\' + str(i)\n        urls.append(url)\n\n\n    def getsource(url):\n        payload = {\n            \'_\': datetime_to_timestamp_in_milliseconds(datetime.datetime.now()),\n            \'mid\': url.replace(\'https://space.bilibili.com/\', \'\')\n        }\n        ua = random.choice(uas)\n        head = {\n            \'User-Agent\': ua,\n            \'Referer\': \'https://space.bilibili.com/\' + str(i) + \'?from=search&seid=\' + str(random.randint(10000, 50000))\n        }\n        mid = payload[\'mid\']\n\n        #使用post会报错 (2021/5/2)\n        jscontent = requests \\\n          .session() \\\n          .get(\'https://api.bilibili.com/x/space/acc/info?mid=%s&jsonp=jsonp\' % mid,\n                headers=head,\n                data=payload\n                ) \\\n          .text\n\n        time2 = time.time()\n        try:\n            jsDict = json.loads(jscontent)\n            status_code = jsDict[\'code\'] if \'code\' in jsDict.keys() else False\n            if status_code == 0:\n                if \'data\' in jsDict.keys():\n                    jsData = jsDict[\'data\']\n                    mid = jsData[\'mid\']\n                    name = jsData[\'name\']\n                    sex = jsData[\'sex\']\n                    rank = jsData[\'rank\']\n                    face = jsData[\'face\']\n                    regtimestamp = jsData[\'jointime\']\n                    regtime_local = time.localtime(regtimestamp)\n                    regtime = time.strftime("%Y-%m-%d %H:%M:%S", regtime_local)\n\n                    birthday = jsData[\'birthday\'] if \'birthday\' in jsData.keys() else \'nobirthday\'\n                    sign = jsData[\'sign\']\n                    level = jsData[\'level\']\n                    OfficialVerifyType = jsData[\'official\'][\'type\']\n                    OfficialVerifyDesc = jsData[\'official\'][\'desc\']\n                    vipType = jsData[\'vip\'][\'type\']\n                    vipStatus = jsData[\'vip\'][\'status\']\n                    coins = jsData[\'coins\']\n                    print("Succeed get user info: " + str(mid) + "\\t" + str(time2 - time1))\n                    try:\n                        res = requests.get(\n                            \'https://api.bilibili.com/x/relation/stat?vmid=\' + str(mid) + \'&jsonp=jsonp\').text\n                        viewinfo = requests.get(\n                            \'https://api.bilibili.com/x/space/upstat?mid=\' + str(mid) + \'&jsonp=jsonp\').text\n                        js_fans_data = json.loads(res)\n                        js_viewdata = json.loads(viewinfo)\n                        following = js_fans_data[\'data\'][\'following\']\n                        fans = js_fans_data[\'data\'][\'follower\']\n                    except:\n                        following = 0\n                        fans = 0\n\n                else:\n                    print(\'no data now\')\n                try:\n                    print(jsDict)\n                    # Please write your MySQL\'s information.\n                    conn = pymysql.connect(\n                        host=\'localhost\', user=\'root\', passwd=\'123456\', db=\'bilibili\', charset=\'utf8\')\n                    cur = conn.cursor()\n                    cur.execute(\'INSERT INTO bilibili_user_info(mid, name, sex, rank, face, regtime, \\\n                                birthday, sign, level, OfficialVerifyType, OfficialVerifyDesc, vipType, vipStatus, \\\n                                coins, following, fans) \\\n                    VALUES ("%s","%s","%s","%s","%s","%s","%s","%s",\\\n                            "%s","%s","%s","%s","%s", "%s","%s","%s")\'\n                                %\n                                (mid, name, sex, rank, face, regtime, \\\n                                 birthday, sign, level, OfficialVerifyType, OfficialVerifyDesc, vipType, vipStatus, \\\n                                 coins, following, fans))\n                    conn.commit()\n                except Exception as e:\n                    print(e)\n            else:\n                print("Error: " + url)\n        except Exception as e:\n            print(e)\n            pass\n\nif __name__ == "__main__":\n    pool = ThreadPool(1)\n    try:\n        results = pool.map(getsource, urls)\n    except Exception as e:\n        print(e)\n \n    pool.close()\n    pool.join()\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": '# -*-coding:utf8-*-\n\nimport requests\nimport json\nimport random\nimport pymysql\nimport sys\nimport datetime\nimport time\nfrom imp import reload\nfrom multiprocessing.dummy import Pool as ThreadPool\n\ndef datetime_to_timestamp_in_milliseconds(d):\n    def current_milli_time(): return int(round(time.time() * 1000))\n    return current_milli_time()\nreload(sys)\n\n\ndef LoadUserAgents(uafile):\n    uas = []\n    with open(uafile, \'rb\') as uaf:\n        for ua in uaf.readlines():\n            if ua:\n                uas.append(ua.strip()[:-1])\n    random.shuffle(uas)\n    return uas\n\n\nuas = LoadUserAgents("user_agents.txt")\nhead = {\n    \'User-Agent\': \'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36\',\n    \'X-Requested-With\': \'XMLHttpRequest\',\n    \'Referer\': \'http://space.bilibili.com/45388\',\n    \'Origin\': \'http://space.bilibili.com\',\n    \'Host\': \'space.bilibili.com\',\n    \'AlexaToolbar-ALX_NS_PH\': \'AlexaToolbar/alx-4.0\',\n    \'Accept-Language\': \'zh-CN,zh;q=0.8,en;q=0.6,ja;q=0.4\',\n    \'Accept\': \'application/json, text/javascript, */*; q=0.01\',\n}\n\n# Please replace your own proxies.\nproxies = {\n    \'http\': \'http://120.26.110.59:8080\',\n    \'http\': \'http://120.52.32.46:80\',\n    \'http\': \'http://218.85.133.62:80\',\n}\ntime1 = time.time()\n\nurls = []\n\n\n# Please change the range data by yourself.\nfor m in range(5214, 5215):\n\n    for i in range(m * 100, (m + 1) * 100):\n        url = \'https://space.bilibili.com/\' + str(i)\n        urls.append(url)\n\n\n    def getsource(url):\n        payload = {\n            \'_\': datetime_to_timestamp_in_milliseconds(datetime.datetime.now()),\n            \'mid\': url.replace(\'https://space.bilibili.com/\', \'\')\n        }\n        ua = random.choice(uas)\n        head = {\n            \'User-Agent\': ua,\n            \'Referer\': \'https://space.bilibili.com/\' + str(i) + \'?from=search&seid=\' + str(random.randint(10000, 50000))\n        }\n        mid = payload[\'mid\']\n\n        #使用post会报错 (2021/5/2)\n        jscontent = requests \\\n          .session() \\\n          .get(\'https://api.bilibili.com/x/space/acc/info?mid=%s&jsonp=jsonp\' % mid,\n                headers=head,\n                data=payload\n                ) \\\n          .text\n\n        time2 = time.time()\n        try:\n            jsDict = json.loads(jscontent)\n            status_code = jsDict[\'code\'] if \'code\' in jsDict.keys() else False\n            if status_code == 0:\n                if \'data\' in jsDict.keys():\n                    jsData = jsDict[\'data\']\n                    mid = jsData[\'mid\']\n                    name = jsData[\'name\']\n                    sex = jsData[\'sex\']\n                    rank = jsData[\'rank\']\n                    face = jsData[\'face\']\n                    regtimestamp = jsData[\'jointime\']\n                    regtime_local = time.localtime(regtimestamp)\n                    regtime = time.strftime("%Y-%m-%d %H:%M:%S", regtime_local)\n\n                    birthday = jsData[\'birthday\'] if \'birthday\' in jsData.keys() else \'nobirthday\'\n                    sign = jsData[\'sign\']\n                    level = jsData[\'level\']\n                    OfficialVerifyType = jsData[\'official\'][\'type\']\n                    OfficialVerifyDesc = jsData[\'official\'][\'desc\']\n                    vipType = jsData[\'vip\'][\'type\']\n                    vipStatus = jsData[\'vip\'][\'status\']\n                    coins = jsData[\'coins\']\n                    print("Succeed get user info: " + str(mid) + "\\t" + str(time2 - time1))\n                    try:\n                        res = requests.get(\n                            \'https://api.bilibili.com/x/relation/stat?vmid=\' + str(mid) + \'&jsonp=jsonp\').text\n                        viewinfo = requests.get(\n                            \'https://api.bilibili.com/x/space/upstat?mid=\' + str(mid) + \'&jsonp=jsonp\').text\n                        js_fans_data = json.loads(res)\n                        js_viewdata = json.loads(viewinfo)\n                        following = js_fans_data[\'data\'][\'following\']\n                        fans = js_fans_data[\'data\'][\'follower\']\n                    except:\n                        following = 0\n                        fans = 0\n\n                else:\n                    print(\'no data now\')\n                try:\n                    print(jsDict)\n                    # Please write your MySQL\'s information.\n                    conn = pymysql.connect(\n                        host=\'localhost\', user=\'root\', passwd=\'123456\', db=\'bilibili\', charset=\'utf8\')\n                    cur = conn.cursor()\n                    cur.execute(\'INSERT INTO bilibili_user_info(mid, name, sex, rank, face, regtime, \\\n                                birthday, sign, level, OfficialVerifyType, OfficialVerifyDesc, vipType, vipStatus, \\\n                                coins, following, fans) \\\n                    VALUES ("%s","%s","%s","%s","%s","%s","%s","%s",\\\n                            "%s","%s","%s","%s","%s", "%s","%s","%s")\'\n                                %\n                                (mid, name, sex, rank, face, regtime, \\\n                                 birthday, sign, level, OfficialVerifyType, OfficialVerifyDesc, vipType, vipStatus, \\\n                                 coins, following, fans))\n                    conn.commit()\n                except Exception as e:\n                    print(e)\n            else:\n                print("Error: " + url)\n        except Exception as e:\n            print(e)\n            pass\n\nif __name__ == "__main__":\n    pool = ThreadPool(1)\n    try:\n        results = pool.map(getsource, urls)\n    except Exception as e:\n        print(e)\n \n    pool.close()\n    pool.join()\n',
        "original_format": 'requests',
        "source_url": 'https://github.com/airingursb/bilibili-user',
        "author": "community",
        "tags": ['Bilibili用户', 'requests', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: 煎蛋妹纸图
    # ═══════════════════════════════════════
    {
        "name": '煎蛋妹纸图',
        "description": '社区爬虫 - 煎蛋妹纸图（来自 GitHub kulovecc/jandan_spider）',
        "category": 'life',
        "icon": '🥚',
        "target_url": 'https://jandan.net/ooxx',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\nimport os\nimport requests\nfrom bs4 import BeautifulSoup\nimport argparse\nimport ast\nimport atexit\nimport multiprocessing\n\nparser = argparse.ArgumentParser(description=\'Spider for jiandan.net\')\nparser.add_argument(\'--page\', dest=\'page\', action=\'store\', default=5, type=int, help=\'max page number\')\nparser.add_argument(\'--dir\', dest=\'dir\', action=\'store\', default=\'images\', help=\'the dir where the image save\')\nargs = parser.parse_args()\n\npage = args.page\n_dir = args.dir\nif not os.path.exists(_dir):\n    os.mkdir(_dir)\nheaders = {\'referer\': \'http://jandan.net/\',\n           \'user-agent\': \'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0\'}\n\nimage_cache = set()\n\nif os.path.exists(".cache"):\n    with open(\'.cache\', \'r\') as f:\n        image_cache = ast.literal_eval(f.read(-1))\n\n\n@atexit.register\ndef hook():\n    with open(\'.cache\', \'w+\') as f:\n        f.write(str(image_cache))\n\n\nindex = len(image_cache)\n\n\n# 保存图片\ndef save_jpg(res_url):\n    global index\n    html = BeautifulSoup(requests.get(res_url, headers=headers).text, features="html.parser")\n    for link in html.find_all(\'a\', {\'class\': \'view_img_link\'}):\n        if link.get(\'href\') not in image_cache:\n            with open(\n                    \'{}/{}.{}\'.format(_dir, index, link.get(\'href\')[len(link.get(\'href\')) - 3: len(link.get(\'href\'))]),\n                    \'wb\') as jpg:\n                jpg.write(requests.get("http:" + link.get(\'href\')).content)\n            image_cache.add(link.get(\'href\'))\n            print("正在抓取第%s条数据" % index)\n            index += 1\n\n\nif __name__ == \'__main__\':\n    url = \'http://jandan.net/ooxx\'\n    for i in range(0, page):\n        save_jpg(url)\n        ahref = BeautifulSoup(requests.get(url, headers=headers).text, features="html.parser").find(\'a\', {\'class\': \'previous-comment-page\'})\n        if ahref is None:\n            print(\'no more page\')\n            exit(0)\n        else:\n            url = "http:" + ahref.get(\'href\')\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": 'import os\nimport requests\nfrom bs4 import BeautifulSoup\nimport argparse\nimport ast\nimport atexit\nimport multiprocessing\n\nparser = argparse.ArgumentParser(description=\'Spider for jiandan.net\')\nparser.add_argument(\'--page\', dest=\'page\', action=\'store\', default=5, type=int, help=\'max page number\')\nparser.add_argument(\'--dir\', dest=\'dir\', action=\'store\', default=\'images\', help=\'the dir where the image save\')\nargs = parser.parse_args()\n\npage = args.page\n_dir = args.dir\nif not os.path.exists(_dir):\n    os.mkdir(_dir)\nheaders = {\'referer\': \'http://jandan.net/\',\n           \'user-agent\': \'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0\'}\n\nimage_cache = set()\n\nif os.path.exists(".cache"):\n    with open(\'.cache\', \'r\') as f:\n        image_cache = ast.literal_eval(f.read(-1))\n\n\n@atexit.register\ndef hook():\n    with open(\'.cache\', \'w+\') as f:\n        f.write(str(image_cache))\n\n\nindex = len(image_cache)\n\n\n# 保存图片\ndef save_jpg(res_url):\n    global index\n    html = BeautifulSoup(requests.get(res_url, headers=headers).text, features="html.parser")\n    for link in html.find_all(\'a\', {\'class\': \'view_img_link\'}):\n        if link.get(\'href\') not in image_cache:\n            with open(\n                    \'{}/{}.{}\'.format(_dir, index, link.get(\'href\')[len(link.get(\'href\')) - 3: len(link.get(\'href\'))]),\n                    \'wb\') as jpg:\n                jpg.write(requests.get("http:" + link.get(\'href\')).content)\n            image_cache.add(link.get(\'href\'))\n            print("正在抓取第%s条数据" % index)\n            index += 1\n\n\nif __name__ == \'__main__\':\n    url = \'http://jandan.net/ooxx\'\n    for i in range(0, page):\n        save_jpg(url)\n        ahref = BeautifulSoup(requests.get(url, headers=headers).text, features="html.parser").find(\'a\', {\'class\': \'previous-comment-page\'})\n        if ahref is None:\n            print(\'no more page\')\n            exit(0)\n        else:\n            url = "http:" + ahref.get(\'href\')\n',
        "original_format": 'requests',
        "source_url": 'https://github.com/kulovecc/jandan_spider',
        "author": "community",
        "tags": ['煎蛋妹纸图', 'requests', 'community', '社区'],
        "difficulty": "medium",
    },
    # ═══════════════════════════════════════
    # 社区: 漫画下载
    # ═══════════════════════════════════════
    {
        "name": '漫画下载',
        "description": '社区爬虫 - 漫画下载（来自 GitHub miaoerduo/cartoon-cat）',
        "category": 'life',
        "icon": '📖',
        "target_url": '',
        "mode": "code_generator",
        "code": '# Auto-adapted from requests/httpx script\nimport asyncio\n\n# --- Original Code ---\n#-*- coding: utf-8 -*-\n\nimport cartoon_cat as cc\n\n# __main__ removed\n\n    # 一拳超人\n    site = \'https://m.36mh.com/manhua/yiquanchaoren/#chapters\'\n\n    crawler = cc.CartoonCat(\n        site=site,                                  # 漫画首页\n        begin=0,                                    # 起始章节\n        end=-1,                                     # 结束章节\n        save_folder=\'./download\',                   # 保存路径，不存在会自动创建\n        browser=cc.BrowserType.CHROME,              # 浏览器类型：FIREFOX，CHROME，SAFARI，IE，PHANTOMJS\n        driver=\'./chromedriver.exe\'                 # 驱动程序路径，firefox不需要\n    )\n    crawler.start()\n\n\n# --- End Original ---\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    """Adapter: runs the original script and captures output."""\n    import io, sys, json\n\n    for func_name in [\'main\', \'run\', \'scrape\', \'fetch\', \'parse\', \'spider\', \'crawl_sync\', \'get_data\']:\n        if func_name in dir():\n            func = globals()[func_name]\n            try:\n                result = func(url) if url else func()\n                if isinstance(result, list):\n                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]\n                elif isinstance(result, dict):\n                    return [result]\n                else:\n                    return [{"data": str(result)}]\n            except Exception as e:\n                return [{"error": str(e)}]\n\n    old_stdout = sys.stdout\n    sys.stdout = buffer = io.StringIO()\n    try:\n        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))\n    except:\n        pass\n    finally:\n        sys.stdout = old_stdout\n\n    output = buffer.getvalue()\n    if output:\n        try:\n            return json.loads(output)\n        except:\n            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]\n\n    return [{"error": "No output captured"}]\n',
        "original_code": "#-*- coding: utf-8 -*-\n\nimport cartoon_cat as cc\n\nif __name__ == '__main__':\n\n    # 一拳超人\n    site = 'https://m.36mh.com/manhua/yiquanchaoren/#chapters'\n\n    crawler = cc.CartoonCat(\n        site=site,                                  # 漫画首页\n        begin=0,                                    # 起始章节\n        end=-1,                                     # 结束章节\n        save_folder='./download',                   # 保存路径，不存在会自动创建\n        browser=cc.BrowserType.CHROME,              # 浏览器类型：FIREFOX，CHROME，SAFARI，IE，PHANTOMJS\n        driver='./chromedriver.exe'                 # 驱动程序路径，firefox不需要\n    )\n    crawler.start()\n\n",
        "original_format": 'script',
        "source_url": 'https://github.com/miaoerduo/cartoon-cat',
        "author": "community",
        "tags": ['漫画下载', 'script', 'community', '社区'],
        "difficulty": "medium",
    },

    # ═══════════════════════════════════════════════════════════════
    #  量化金融专区
    # ═══════════════════════════════════════════════════════════════

    # ── 1. 东方财富A股实时行情 ──
    {
        "name": "东方财富A股实时行情",
        "description": "通过东方财富推送接口获取沪深A股实时行情数据，包括最新价、涨跌幅、成交量等",
        "category": "finance",
        "icon": "📈",
        "target_url": "http://push2.eastmoney.com/api/qt/clist/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """东方财富A股实时行情"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    # 分页参数
    page = config.get("page", 1)
    page_size = config.get("page_size", 20)
    params = {
        "pn": page,
        "pz": page_size,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",  # 按涨跌幅排序
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",  # 沪深A股
        "fields": "f2,f3,f4,f5,f6,f7,f12,f14",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(url or "http://push2.eastmoney.com/api/qt/clist/get", params=params)
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}) or {}).get("diff", []):
            results.append({
                "code": item.get("f12", ""),       # 股票代码
                "name": item.get("f14", ""),       # 股票名称
                "price": item.get("f2", 0),        # 最新价
                "change_pct": item.get("f3", 0),   # 涨跌幅%
                "change_amt": item.get("f4", 0),   # 涨跌额
                "volume": item.get("f5", 0),       # 成交量(手)
                "amount": item.get("f6", 0),       # 成交额
                "turnover": item.get("f7", 0),     # 换手率%
            })
    return results
''',
        "tags": ["A股", "行情", "东方财富", "实时", "沪深"],
        "difficulty": "easy",
    },

    # ── 2. 东方财富龙虎榜 ──
    {
        "name": "东方财富龙虎榜",
        "description": "获取东方财富龙虎榜数据，包含上榜原因、买卖金额等",
        "category": "finance",
        "icon": "🐉",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """东方财富龙虎榜数据"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "SECURITY_CODE",
        "sortTypes": "1",
        "pageNumber": config.get("page", 1),
        "pageSize": config.get("page_size", 50),
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "code": item.get("SECURITY_CODE", ""),
                "name": item.get("SECURITY_NAME_ABBR", ""),
                "close": item.get("CLOSE_PRICE", 0),
                "change_pct": item.get("CHANGE_RATE", 0),
                "net_buy": item.get("NET_BUY_AMT", 0),
                "reason": item.get("EXPLAIN", ""),
                "date": item.get("TRADE_DATE", ""),
            })
    return results
''',
        "tags": ["龙虎榜", "A股", "东方财富", "游资"],
        "difficulty": "easy",
    },

    # ── 3. 同花顺概念板块 ──
    {
        "name": "同花顺概念板块",
        "description": "获取同花顺概念板块列表及涨跌幅、领涨股等信息",
        "category": "finance",
        "icon": "🧩",
        "target_url": "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock/concept/list",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """同花顺概念板块行情（使用东财备用接口）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    # 使用东财概念板块接口作为稳定替代
    params = {
        "pn": config.get("page", 1),
        "pz": config.get("page_size", 50),
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:90+t:3+f:!50",  # 概念板块
        "fields": "f2,f3,f4,f8,f12,f14,f104,f105,f128,f140,f141",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            "http://push2.eastmoney.com/api/qt/clist/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}) or {}).get("diff", []):
            results.append({
                "name": item.get("f14", ""),        # 板块名称
                "code": item.get("f12", ""),        # 板块代码
                "change_pct": item.get("f3", 0),    # 涨跌幅%
                "turnover": item.get("f8", 0),      # 换手率%
                "leading_stock": item.get("f140", ""),  # 领涨股名称
            })
    return results
''',
        "tags": ["概念板块", "同花顺", "A股", "题材"],
        "difficulty": "easy",
    },

    # ── 4. 新浪财经A股行情 ──
    {
        "name": "新浪财经A股行情",
        "description": "通过新浪财经API获取沪深A股行情数据",
        "category": "finance",
        "icon": "📊",
        "target_url": "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """新浪财经A股行情"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "page": config.get("page", 1),
        "num": config.get("page_size", 40),
        "sort": "symbol",
        "asc": 1,
        "node": "hs_a",  # 沪深A股
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        api = url or "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
        resp = await client.get(api, params=params)
        resp.raise_for_status()
        data = resp.json()
        for item in data:
            results.append({
                "code": item.get("symbol", ""),
                "name": item.get("name", ""),
                "open": float(item.get("open", 0)),
                "close": float(item.get("trade", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "volume": float(item.get("volume", 0)),
                "amount": float(item.get("amount", 0)),
            })
    return results
''',
        "tags": ["A股", "行情", "新浪财经", "沪深"],
        "difficulty": "easy",
    },

    # ── 5. 雪球热股榜 ──
    {
        "name": "雪球热股榜",
        "description": "获取雪球热门股票排行，需要先访问雪球首页获取Cookie",
        "category": "finance",
        "icon": "🔥",
        "target_url": "https://stock.xueqiu.com/v5/stock/hot_stock/list.json",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """雪球热股榜（需先获取cookie）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://xueqiu.com",
        "Referer": "https://xueqiu.com/hq",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers, follow_redirects=True) as client:
        # 第一步：访问首页拿cookie
        await client.get("https://xueqiu.com/")
        # 第二步：请求热股接口
        params = {
            "size": config.get("page_size", 30),
            "_type": 10,
            "type": 10,
        }
        resp = await client.get(
            url or "https://stock.xueqiu.com/v5/stock/hot_stock/list.json",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}) or {}).get("items", []):
            results.append({
                "code": item.get("code", ""),
                "name": item.get("name", ""),
                "price": item.get("current", 0),
                "change_pct": item.get("percent", 0),
                "followers": item.get("follow_count", 0),
            })
    return results
''',
        "tags": ["雪球", "热股", "A股", "人气榜"],
        "difficulty": "medium",
    },

    # ── 6. 东财概念板块行情 ──
    {
        "name": "东财概念板块行情",
        "description": "通过东方财富数据中心API获取概念板块实时行情及领涨股",
        "category": "finance",
        "icon": "💡",
        "target_url": "http://push2.eastmoney.com/api/qt/clist/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """东财概念板块行情"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "pn": config.get("page", 1),
        "pz": config.get("page_size", 50),
        "po": 1, "np": 1, "fltt": 2, "invt": 2,
        "fid": "f3",
        "fs": "m:90+t:3+f:!50",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f12,f14,f104,f105,f128,f140,f141",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "http://push2.eastmoney.com/api/qt/clist/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}) or {}).get("diff", []):
            results.append({
                "name": item.get("f14", ""),
                "code": item.get("f12", ""),
                "change_pct": item.get("f3", 0),
                "volume": item.get("f5", 0),
                "leading_stock": item.get("f140", ""),
            })
    return results
''',
        "tags": ["概念板块", "东方财富", "题材", "A股"],
        "difficulty": "easy",
    },

    # ── 7. 富途牛牛港股行情 ──
    {
        "name": "富途牛牛港股行情",
        "description": "通过东方财富接口获取港股实时行情数据",
        "category": "finance",
        "icon": "🇭🇰",
        "target_url": "http://push2.eastmoney.com/api/qt/clist/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """港股实时行情（东财接口）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "pn": config.get("page", 1),
        "pz": config.get("page_size", 20),
        "po": 1, "np": 1, "fltt": 2, "invt": 2,
        "fid": "f3",
        "fs": "m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2",  # 港股
        "fields": "f2,f3,f4,f5,f6,f12,f14",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "http://push2.eastmoney.com/api/qt/clist/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}) or {}).get("diff", []):
            results.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),
                "volume": item.get("f5", 0),
            })
    return results
''',
        "tags": ["港股", "行情", "HK", "恒生"],
        "difficulty": "easy",
    },

    # ── 8. 东方财富资金流向 ──
    {
        "name": "东方财富资金流向",
        "description": "获取个股资金流向数据，包括主力、超大单、大单、中单、小单净流入",
        "category": "finance",
        "icon": "💰",
        "target_url": "http://push2.eastmoney.com/api/qt/clist/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """东方财富个股资金流向"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "pn": config.get("page", 1),
        "pz": config.get("page_size", 20),
        "po": 1, "np": 1, "fltt": 2, "invt": 2,
        "fid": "f62",  # 按主力净流入排序
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "http://push2.eastmoney.com/api/qt/clist/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}) or {}).get("diff", []):
            results.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),             # 涨跌幅
                "main_net_inflow": item.get("f62", 0),       # 主力净流入
                "main_pct": item.get("f184", 0),             # 主力净占比%
                "super_large_net": item.get("f66", 0),       # 超大单净流入
                "large_net": item.get("f72", 0),             # 大单净流入
                "medium_net": item.get("f78", 0),            # 中单净流入
                "small_net": item.get("f84", 0),             # 小单净流入
            })
    return results
''',
        "tags": ["资金流", "主力", "A股", "东方财富"],
        "difficulty": "easy",
    },

    # ── 9. 东方财富财务数据（利润表） ──
    {
        "name": "东方财富财务数据",
        "description": "获取上市公司财务利润表数据，包括营收、净利润、EPS、ROE等",
        "category": "finance",
        "icon": "📋",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """东方财富财务利润表数据"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    # 默认查600519（贵州茅台），可通过config传stock_code
    stock_code = config.get("stock_code", "600519")
    params = {
        "reportName": "RPT_LICO_FN_CPD",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(SECURITY_CODE="{stock_code}")',
        "pageNumber": 1,
        "pageSize": config.get("page_size", 10),
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "code": item.get("SECURITY_CODE", ""),
                "name": item.get("SECURITY_NAME_ABBR", ""),
                "revenue": item.get("TOTAL_OPERATE_INCOME", 0),
                "net_profit": item.get("NETPROFIT", 0),
                "eps": item.get("BASIC_EPS", 0),
                "roe": item.get("WEIGHTAVG_ROE", 0),
                "report_date": item.get("REPORT_DATE", ""),
            })
    return results
''',
        "tags": ["财务", "利润表", "A股", "基本面"],
        "difficulty": "easy",
    },

    # ── 10. 中国LPR利率 ──
    {
        "name": "中国LPR利率",
        "description": "获取中国贷款市场报价利率(LPR)历史数据",
        "category": "finance",
        "icon": "🏦",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """中国LPR利率数据（东财数据中心）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "reportName": "RPTA_WEB_RATE",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageNumber": 1,
        "pageSize": config.get("page_size", 20),
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "date": item.get("TRADE_DATE", ""),
                "lpr_1y": item.get("LPR1Y", 0),
                "lpr_5y": item.get("LPR5Y", 0),
            })
    return results
''',
        "tags": ["LPR", "利率", "央行", "宏观"],
        "difficulty": "easy",
    },

    # ── 11. 美股行情（Yahoo Finance） ──
    {
        "name": "美股行情Yahoo Finance",
        "description": "通过Yahoo Finance API获取美股行情数据，可能需要代理",
        "category": "finance",
        "icon": "🇺🇸",
        "target_url": "https://query1.finance.yahoo.com/v8/finance/chart/AAPL",
        "mode": "code_generator",
        "proxy_required": 1,
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """美股行情 - Yahoo Finance（可能需要代理）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    # 支持多个股票代码，逗号分隔
    symbols = config.get("symbols", "AAPL,MSFT,GOOGL,AMZN,TSLA").split(",")
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        for symbol in symbols:
            symbol = symbol.strip()
            try:
                resp = await client.get(
                    url or f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"range": "1d", "interval": "1d"},
                )
                resp.raise_for_status()
                data = resp.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                results.append({
                    "symbol": meta.get("symbol", symbol),
                    "price": meta.get("regularMarketPrice", 0),
                    "change": round(
                        meta.get("regularMarketPrice", 0) - meta.get("previousClose", 0), 2
                    ),
                    "change_pct": round(
                        (meta.get("regularMarketPrice", 0) - meta.get("previousClose", 0))
                        / meta.get("previousClose", 1) * 100, 2
                    ) if meta.get("previousClose") else 0,
                    "volume": meta.get("regularMarketVolume", 0),
                    "market_cap": meta.get("marketCap", 0),
                })
            except Exception:
                results.append({"symbol": symbol, "error": "请求失败，可能需要代理"})
    return results
''',
        "tags": ["美股", "Yahoo", "行情", "US"],
        "difficulty": "medium",
    },

    # ── 12. 加密货币行情（CoinGecko） ──
    {
        "name": "加密货币行情CoinGecko",
        "description": "通过CoinGecko免费API获取加密货币市值排行及行情，无需API Key",
        "category": "finance",
        "icon": "₿",
        "target_url": "https://api.coingecko.com/api/v3/coins/markets",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """加密货币行情 - CoinGecko（免费API，有频率限制）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "vs_currency": config.get("currency", "usd"),
        "order": "market_cap_desc",
        "per_page": config.get("page_size", 50),
        "page": config.get("page", 1),
        "sparkline": "false",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://api.coingecko.com/api/v3/coins/markets",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data:
            results.append({
                "name": item.get("name", ""),
                "symbol": item.get("symbol", "").upper(),
                "price": item.get("current_price", 0),
                "change_24h": item.get("price_change_percentage_24h", 0),
                "market_cap": item.get("market_cap", 0),
                "volume_24h": item.get("total_volume", 0),
            })
    return results
''',
        "tags": ["加密货币", "BTC", "ETH", "CoinGecko", "crypto"],
        "difficulty": "easy",
    },

    # ── 13. 期货行情（东方财富） ──
    {
        "name": "期货行情",
        "description": "通过东方财富获取国内期货主力合约实时行情",
        "category": "finance",
        "icon": "📦",
        "target_url": "http://push2.eastmoney.com/api/qt/clist/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """期货主力合约行情（东方财富）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "pn": config.get("page", 1),
        "pz": config.get("page_size", 20),
        "po": 1, "np": 1, "fltt": 2, "invt": 2,
        "fid": "f3",
        "fs": "m:113,m:114,m:115,m:8,m:142",  # 国内期货
        "fields": "f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18",
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "http://push2.eastmoney.com/api/qt/clist/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}) or {}).get("diff", []):
            results.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),
                "open_interest": item.get("f18", 0),  # 持仓量
                "volume": item.get("f5", 0),
            })
    return results
''',
        "tags": ["期货", "商品", "主力合约", "东方财富"],
        "difficulty": "easy",
    },

    # ── 14. 融资融券数据 ──
    {
        "name": "融资融券数据",
        "description": "获取沪深两市融资融券余额及交易数据",
        "category": "finance",
        "icon": "🔄",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """沪深融资融券数据（东财数据中心）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "reportName": "RPTA_WEB_RZRQ_SZSZ",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "DIM_DATE",
        "sortTypes": "-1",
        "pageNumber": 1,
        "pageSize": config.get("page_size", 30),
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "date": item.get("DIM_DATE", ""),
                "total_margin_buy": item.get("RZYE", 0),       # 融资余额
                "total_margin_sell": item.get("RQYE", 0),      # 融券余额
                "net_buy": item.get("RZMRE", 0),               # 融资买入额
                "balance": item.get("RZRQYE", 0),              # 融资融券余额合计
            })
    return results
''',
        "tags": ["融资融券", "两融", "杠杆", "A股"],
        "difficulty": "easy",
    },

    # ── 15. 北向资金/沪深港通 ──
    {
        "name": "北向资金沪深港通",
        "description": "获取沪深港通北向资金每日净买入数据",
        "category": "finance",
        "icon": "🧭",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """北向资金/沪深港通净买入（东财数据中心）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "reportName": "RPT_MUTUAL_DEAL_HISTORY",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageNumber": 1,
        "pageSize": config.get("page_size", 30),
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "date": item.get("TRADE_DATE", ""),
                "hk_to_sh": item.get("MUTUAL_A_DEALS_AMT", 0),   # 沪股通净买入
                "hk_to_sz": item.get("MUTUAL_B_DEALS_AMT", 0),   # 深股通净买入
                "total_net_buy": item.get("NET_DEAL_AMT", 0),     # 北向合计净买入
            })
    return results
''',
        "tags": ["北向资金", "沪深港通", "外资", "A股"],
        "difficulty": "easy",
    },

    # ── 16. 新股/IPO信息 ──
    {
        "name": "新股IPO信息",
        "description": "获取近期新股申购和上市信息",
        "category": "finance",
        "icon": "🆕",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """近期新股/IPO信息（东财数据中心）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    params = {
        "reportName": "RPTA_APP_IPOAPPLY",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "APPLY_DATE",
        "sortTypes": "-1",
        "pageNumber": 1,
        "pageSize": config.get("page_size", 30),
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "code": item.get("SECURITY_CODE", ""),
                "name": item.get("SECURITY_NAME", ""),
                "price": item.get("ISSUE_PRICE", 0),
                "date": item.get("APPLY_DATE", ""),
                "industry": item.get("INDUSTRY", ""),
                "pe_ratio": item.get("PE_RATIO", 0),
            })
    return results
''',
        "tags": ["新股", "IPO", "打新", "申购"],
        "difficulty": "easy",
    },

    # ── 17. 财经日历/经济数据 ──
    {
        "name": "财经日历",
        "description": "获取全球重要经济数据发布日历，包括GDP、CPI、PMI等",
        "category": "finance",
        "icon": "📅",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx
from datetime import datetime, timedelta

async def crawl(url: str, config: dict) -> list[dict]:
    """财经日历/经济数据（东财数据中心）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    # 默认查最近7天
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    params = {
        "reportName": "RPT_ECONOMICVALUE_HKCAL",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageNumber": 1,
        "pageSize": config.get("page_size", 50),
    }
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "time": item.get("TRADE_DATE", ""),
                "country": item.get("COUNTRY", ""),
                "event": item.get("INDICATOR_NAME", ""),
                "importance": item.get("IMPORTANCE", ""),
                "actual": item.get("ACTUAL_VALUE", ""),
                "forecast": item.get("FORECAST_VALUE", ""),
                "previous": item.get("PRE_VALUE", ""),
            })
    return results
''',
        "tags": ["财经日历", "经济数据", "宏观", "GDP", "CPI"],
        "difficulty": "easy",
    },

    # ── 18. 股票公告/研报 ──
    {
        "name": "股票公告研报",
        "description": "获取上市公司最新公告和研究报告",
        "category": "finance",
        "icon": "📄",
        "target_url": "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "mode": "code_generator",
        "code": '''import httpx

async def crawl(url: str, config: dict) -> list[dict]:
    """上市公司公告/研报（东财数据中心）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    }
    proxy = config.get("proxy")
    proxies = {"http://": proxy, "https://": proxy} if proxy else None
    # 可通过config传stock_code筛选特定股票
    stock_code = config.get("stock_code", "")
    params = {
        "reportName": "RPT_REPORT_LIST",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "NOTICE_DATE",
        "sortTypes": "-1",
        "pageNumber": config.get("page", 1),
        "pageSize": config.get("page_size", 30),
    }
    if stock_code:
        params["filter"] = f'(SECURITY_CODE="{stock_code}")'
    results = []
    async with httpx.AsyncClient(proxies=proxies, timeout=30, headers=headers) as client:
        resp = await client.get(
            url or "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("result", {}) or {}).get("data", []):
            results.append({
                "code": item.get("SECURITY_CODE", ""),
                "name": item.get("SECURITY_NAME_ABBR", ""),
                "title": item.get("TITLE", ""),
                "date": item.get("NOTICE_DATE", ""),
                "type": item.get("NOTICE_TYPE", ""),
                "url": item.get("INFO_CODE", ""),
            })
    return results
''',
        "tags": ["公告", "研报", "A股", "信息披露"],
        "difficulty": "easy",
    },

    # ═══════════════════════════════════════
    # Community Seeds (auto-fetched from GitHub)
    # ═══════════════════════════════════════
    {
        "name": "小红书笔记爬虫",
        "description": "社区爬虫 - 来自 NanmiCoder/MediaCrawler (GitHub高星项目)",
        "category": "social",
        "icon": "📕",
        "target_url": "https://www.xiaohongshu.com",
        "mode": "code_generator",
        "code": '''# Auto-adapted from Playwright script
# === media_platform/xhs/core.py ===
# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/xhs/core.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import os
import random
from asyncio import Task
from typing import Dict, List, Optional

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)
from tenacity import RetryError

import config
from base.base_crawler import AbstractCrawler
from model.m_xiaohongshu import NoteUrlInfo, CreatorUrlInfo
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import xhs as xhs_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import XiaoHongShuClient
from .exception import DataFetchError, NoteNotFoundError
from .field import SearchSortType
from .help import parse_note_info_from_note_url, parse_creator_info_from_url, get_search_id
from .login import XiaoHongShuLogin


class XiaoHongShuCrawler(AbstractCrawler):
    context_page: Page
    xhs_client: XiaoHongShuClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self) -> None:
        self.index_url = "https://www.xiaohongshu.com"
        # self.user_agent = utils.get_user_agent()
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.cdp_manager = None
        self.ip_proxy_pool = None  # Proxy IP pool for automatic proxy refresh

    async def start(self) -> None:
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            # Choose launch mode based on configuration
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[XiaoHongShuCrawler] Launching browser using CDP mode")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[XiaoHongShuCrawler] Launching browser using standard mode")
                # Launch a browser context.
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.HEADLESS,
                )
                # stealth.min.js is a js script to prevent the website from detecting the crawler.
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)

            # Create a client to interact with the Xiaohongshu website.
            self.xhs_client = await self.create_xhs_client(httpx_proxy_format)
            if not await self.xhs_client.pong():
                login_obj = XiaoHongShuLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone="",  # input your phone number
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.xhs_client.update_cookies(browser_context=self.browser_context)

            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                # Search for notes and retrieve their comment information.
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                # Get the information and comments of the specified post
                await self.get_specified_notes()
            elif config.CRAWLER_TYPE == "creator":
                # Get creator's information and their notes and comments
                await self.get_creators_and_notes()
            else:
                pass

            utils.logger.info("[XiaoHongShuCrawler.start] Xhs Crawler finished ...")

    async def search(self) -> None:
        """Search for notes and retrieve their comment information."""
        utils.logger.info("[XiaoHongShuCrawler.search] Begin search Xiaohongshu keywords")
        xhs_limit_count = 20  # Xiaohongshu limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < xhs_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = xhs_limit_count
        start_page = config.START_PAGE
        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(f"[XiaoHongShuCrawler.search] Current search keyword: {keyword}")
            page = 1
            search_id = get_search_id()
            while (page - start_page + 1) * xhs_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    utils.logger.info(f"[XiaoHongShuCrawler.search] Skip page {page}")
                    page += 1
                    continue

                try:
                    utils.logger.info(f"[XiaoHongShuCrawler.search] search Xiaohongshu keyword: {keyword}, page: {page}")
                    note_ids: List[str] = []
                    xsec_tokens: List[str] = []
                    notes_res = await self.xhs_client.get_note_by_keyword(
                        keyword=keyword,
                        search_id=search_id,
                        page=page,
                        sort=(SearchSortType(config.SORT_TYPE) if config.SORT_TYPE != "" else SearchSortType.GENERAL),
                    )
                    utils.logger.info(f"[XiaoHongShuCrawler.search] Search notes response: {notes_res}")
                    if not notes_res or not notes_res.get("has_more", False):
                        utils.logger.info("[XiaoHongShuCrawler.search] No more content!")
                        break
                    semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
                    task_list = [
                        self.get_note_detail_async_task(
                            note_id=post_item.get("id"),
                            xsec_source=post_item.get("xsec_source"),
                            xsec_token=post_item.get("xsec_token"),
                            semaphore=semaphore,
                        ) for post_item in notes_res.get("items", {}) if post_item.get("model_type") not in ("rec_query", "hot_query")
                    ]
                    note_details = await asyncio.gather(*task_list)
                    for note_detail in note_details:
                        if note_detail:
                            await xhs_store.update_xhs_note(note_detail)
                            await self.get_notice_media(note_detail)
                            note_ids.append(note_detail.get("note_id"))
                            xsec_tokens.append(note_detail.get("xsec_token"))
                    page += 1
                    utils.logger.info(f"[XiaoHongShuCrawler.search] Note detai
# ... (truncated)

if 'crawl' not in dir():
    async def crawl(url: str, config: dict) -> list[dict]:
        for func_name in ['main', 'run', 'scrape']:
            if func_name in dir():
                func = globals()[func_name]
                import asyncio
                result = await func(url) if asyncio.iscoroutinefunction(func) else func(url)
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
        return [{"error": "No entry function found"}]
''',
        "tags": ['小红书', '社交', '笔记', '中文'],
        "difficulty": "hard",
        "author": "community",
        "source_url": "https://github.com/NanmiCoder/MediaCrawler",
        "use_browser": 1,
    },
    {
        "name": "抖音视频爬虫",
        "description": "社区爬虫 - 来自 NanmiCoder/MediaCrawler (GitHub高星项目)",
        "category": "social",
        "icon": "🎵",
        "target_url": "https://www.douyin.com",
        "mode": "code_generator",
        "code": '''# Auto-adapted from Playwright script
# === media_platform/douyin/core.py ===
# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/douyin/core.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import os
import random
from asyncio import Task
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import douyin as douyin_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import DouYinClient
from .exception import DataFetchError
from .field import PublishTimeType
from .help import parse_video_info_from_url, parse_creator_info_from_url
from .login import DouYinLogin


class DouYinCrawler(AbstractCrawler):
    context_page: Page
    dy_client: DouYinClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self) -> None:
        self.index_url = "https://www.douyin.com"
        self.cdp_manager = None
        self.ip_proxy_pool = None  # Proxy IP pool for automatic proxy refresh

    async def start(self) -> None:
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            # Select startup mode based on configuration
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[DouYinCrawler] 使用CDP模式启动浏览器")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    None,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[DouYinCrawler] 使用标准模式启动浏览器")
                # Launch a browser context.
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    user_agent=None,
                    headless=config.HEADLESS,
                )
                # stealth.min.js is a js script to prevent the website from detecting the crawler.
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)

            self.dy_client = await self.create_douyin_client(httpx_proxy_format)
            if not await self.dy_client.pong(browser_context=self.browser_context):
                login_obj = DouYinLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone="",  # you phone number
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.dy_client.update_cookies(browser_context=self.browser_context)
            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                # Search for notes and retrieve their comment information.
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                # Get the information and comments of the specified post
                await self.get_specified_awemes()
            elif config.CRAWLER_TYPE == "creator":
                # Get the information and comments of the specified creator
                await self.get_creators_and_videos()

            utils.logger.info("[DouYinCrawler.start] Douyin Crawler finished ...")

    async def search(self) -> None:
        utils.logger.info("[DouYinCrawler.search] Begin search douyin keywords")
        dy_limit_count = 10  # douyin limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < dy_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = dy_limit_count
        start_page = config.START_PAGE  # start page number
        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(f"[DouYinCrawler.search] Current keyword: {keyword}")
            aweme_list: List[str] = []
            page = 0
            dy_search_id = ""
            while (page - start_page + 1) * dy_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    utils.logger.info(f"[DouYinCrawler.search] Skip {page}")
                    page += 1
                    continue
                try:
                    utils.logger.info(f"[DouYinCrawler.search] search douyin keyword: {keyword}, page: {page}")
                    posts_res = await self.dy_client.search_info_by_keyword(
                        keyword=keyword,
                        offset=page * dy_limit_count - dy_limit_count,
                        publish_time=PublishTimeType(config.PUBLISH_TIME_TYPE),
                        search_id=dy_search_id,
                    )
                    if posts_res.get("data") is None or posts_res.get("data") == []:
                        utils.logger.info(f"[DouYinCrawler.search] search douyin keyword: {keyword}, page: {page} is empty,{posts_res.get('data')}`")
                        break
                except DataFetchError:
                    utils.logger.error(f"[DouYinCrawler.search] search douyin keyword: {keyword} failed")
                    break

                page += 1
                if "data" not in posts_res:
                    utils.logger.error(f"[DouYinCrawler.search] search douyin keyword: {keyword} failed，账号也许被风控了。")
                    break
                dy_search_id = posts_res.get("extra", {}).get("logid", "")
                page_aweme_list = []
                for post_item in posts_res.get("data"):
                    try:
                        aweme_info: Dict = (post_item.get("aweme_info") or post_item.get("aweme_mix_info", {}).get("mix_items")[0])
                    except TypeError:
                        continue
                    aweme_list.append(aweme_info.get("aweme_id", ""))
                    page_aweme_list.append(aweme_info.get("aweme_id", ""))
                    await douyin_store.update_douyin_aweme(aweme_item=aweme_info)
                    await self.get_aweme_media(aweme_item=aweme_info)
                
                # Batch get note comments for the current page
                await self.batch_get_note_comments(page_aweme_list)

                # Sleep after each page navigation
                await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                utils.logger.info(f"[DouYinCrawler.search] Sleeping for {config.CRAWLER_MAX_SLEEP_SEC} seconds after page {page-1}")
            utils.logger.info(f"[DouYinCrawler.search] keyword:{keyword}, aweme_list:{aweme_list}")

    async def get_specified_awemes(self):
        """Get the information and comments of the specified post from URLs or IDs"""
        utils.logger.info("[DouYinCrawler.get_specified_awemes] Parsing video URLs...")
        aweme_id_li
# ... (truncated)

if 'crawl' not in dir():
    async def crawl(url: str, config: dict) -> list[dict]:
        for func_name in ['main', 'run', 'scrape']:
            if func_name in dir():
                func = globals()[func_name]
                import asyncio
                result = await func(url) if asyncio.iscoroutinefunction(func) else func(url)
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
        return [{"error": "No entry function found"}]
''',
        "tags": ['抖音', '短视频', '中文'],
        "difficulty": "hard",
        "author": "community",
        "source_url": "https://github.com/NanmiCoder/MediaCrawler",
        "use_browser": 1,
    },
    {
        "name": "快手视频爬虫",
        "description": "社区爬虫 - 来自 NanmiCoder/MediaCrawler (GitHub高星项目)",
        "category": "social",
        "icon": "🎬",
        "target_url": "https://www.kuaishou.com",
        "mode": "code_generator",
        "code": '''# Auto-adapted from Playwright script
# === media_platform/kuaishou/core.py ===
# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/kuaishou/core.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


import asyncio
import os
# import random  # Removed as we now use fixed config.CRAWLER_MAX_SLEEP_SEC intervals
import time
from asyncio import Task
from typing import Dict, List, Optional, Tuple

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from model.m_kuaishou import VideoUrlInfo, CreatorUrlInfo
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import kuaishou as kuaishou_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import comment_tasks_var, crawler_type_var, source_keyword_var

from .client import KuaiShouClient
from .exception import DataFetchError
from .help import parse_video_info_from_url, parse_creator_info_from_url
from .login import KuaishouLogin


class KuaishouCrawler(AbstractCrawler):
    context_page: Page
    ks_client: KuaiShouClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self):
        self.index_url = "https://www.kuaishou.com"
        self.user_agent = utils.get_user_agent()
        self.cdp_manager = None
        self.ip_proxy_pool = None  # Proxy IP pool, used for automatic proxy refresh

    async def start(self):
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(
                config.IP_PROXY_POOL_COUNT, enable_validate_ip=True
            )
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(
                ip_proxy_info
            )

        async with async_playwright() as playwright:
            # Select startup mode based on configuration
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[KuaishouCrawler] Launching browser using CDP mode")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[KuaishouCrawler] Launching browser using standard mode")
                # Launch a browser context.
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium, None, self.user_agent, headless=config.HEADLESS
                )
                # stealth.min.js is a js script to prevent the website from detecting the crawler.
                await self.browser_context.add_init_script(path="libs/stealth.min.js")


            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(f"{self.index_url}?isHome=1")

            # Create a client to interact with the kuaishou website.
            self.ks_client = await self.create_ks_client(httpx_proxy_format)
            if not await self.ks_client.pong():
                login_obj = KuaishouLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone=httpx_proxy_format,
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.ks_client.update_cookies(
                    browser_context=self.browser_context
                )

            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                # Search for videos and retrieve their comment information.
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                # Get the information and comments of the specified post
                await self.get_specified_videos()
            elif config.CRAWLER_TYPE == "creator":
                # Get creator's information and their videos and comments
                await self.get_creators_and_videos()
            else:
                pass

            utils.logger.info("[KuaishouCrawler.start] Kuaishou Crawler finished ...")

    async def search(self):
        utils.logger.info("[KuaishouCrawler.search] Begin search kuaishou keywords")
        ks_limit_count = 20  # kuaishou limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < ks_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = ks_limit_count
        start_page = config.START_PAGE
        for keyword in config.KEYWORDS.split(","):
            search_session_id = ""
            source_keyword_var.set(keyword)
            utils.logger.info(
                f"[KuaishouCrawler.search] Current search keyword: {keyword}"
            )
            page = 1
            while (
                page - start_page + 1
            ) * ks_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    utils.logger.info(f"[KuaishouCrawler.search] Skip page: {page}")
                    page += 1
                    continue
                utils.logger.info(
                    f"[KuaishouCrawler.search] search kuaishou keyword: {keyword}, page: {page}"
                )
                video_id_list: List[str] = []
                videos_res = await self.ks_client.search_info_by_keyword(
                    keyword=keyword,
                    pcursor=str(page),
                    search_session_id=search_session_id,
                )
                if not videos_res:
                    utils.logger.error(
                        f"[KuaishouCrawler.search] search info by keyword:{keyword} not found data"
                    )
                    continue

                vision_search_photo: Dict = videos_res.get("visionSearchPhoto")
                if vision_search_photo.get("result") != 1:
                    utils.logger.error(
                        f"[KuaishouCrawler.search] search info by keyword:{keyword} not found data "
                    )
                    continue
                search_session_id = vision_search_photo.get("searchSessionId", "")
                for video_detail in vision_search_photo.get("feeds"):
                    video_id_list.append(video_detail.get("photo", {}).get("id"))
                    await kuaishou_store.update_kuaishou_video(video_item=video_detail)

                # batch fetch video comments
                page += 1

                # Sleep after page navigation
                await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                utils.logger.info(f"[KuaishouCrawler.search] Sleeping for {config.CRAWLER_MAX_SLEEP_SEC} seconds after page {page-1}")

                await self.batch_get_video_comments(video_id_list)

    async def get_specified_videos(self):
        """Get the information and comments of the specified post"""
        utils.logger.info("[KuaishouCrawler.get_specified_videos] Parsing video URLs...")
        video_ids = []
        for video_url in config.KS_SPECIFIED_ID_LIST:
            try:
                video_info = parse_video_info_from_url(video_url)
                video_ids.append(video_info.video_id)
                utils.logger.info(f"Parsed video ID: {video_info.video_id} from 
# ... (truncated)

if 'crawl' not in dir():
    async def crawl(url: str, config: dict) -> list[dict]:
        for func_name in ['main', 'run', 'scrape']:
            if func_name in dir():
                func = globals()[func_name]
                import asyncio
                result = await func(url) if asyncio.iscoroutinefunction(func) else func(url)
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
        return [{"error": "No entry function found"}]
''',
        "tags": ['快手', '短视频', '中文'],
        "difficulty": "hard",
        "author": "community",
        "source_url": "https://github.com/NanmiCoder/MediaCrawler",
        "use_browser": 1,
    },
    {
        "name": "百度贴吧爬虫",
        "description": "社区爬虫 - 来自 NanmiCoder/MediaCrawler (GitHub高星项目)",
        "category": "social",
        "icon": "💬",
        "target_url": "https://tieba.baidu.com",
        "mode": "code_generator",
        "code": '''# Auto-adapted from Playwright script
# === media_platform/tieba/core.py ===
# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/tieba/core.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


import asyncio
import os
from asyncio import Task
from typing import Dict, List, Optional, Tuple

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from model.m_baidu_tieba import TiebaCreator, TiebaNote
from proxy.proxy_ip_pool import IpInfoModel, ProxyIpPool, create_ip_pool
from store import tieba as tieba_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import BaiduTieBaClient
from .field import SearchNoteType, SearchSortType
from .help import TieBaExtractor
from .login import BaiduTieBaLogin


class TieBaCrawler(AbstractCrawler):
    context_page: Page
    tieba_client: BaiduTieBaClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self) -> None:
        self.index_url = "https://tieba.baidu.com"
        self.user_agent = utils.get_user_agent()
        self._page_extractor = TieBaExtractor()
        self.cdp_manager = None

    async def start(self) -> None:
        """
        Start the crawler
        Returns:

        """
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            utils.logger.info(
                "[BaiduTieBaCrawler.start] Begin create ip proxy pool ..."
            )
            ip_proxy_pool = await create_ip_pool(
                config.IP_PROXY_POOL_COUNT, enable_validate_ip=True
            )
            ip_proxy_info: IpInfoModel = await ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)
            utils.logger.info(
                f"[BaiduTieBaCrawler.start] Init default ip proxy, value: {httpx_proxy_format}"
            )

        async with async_playwright() as playwright:
            # Choose startup mode based on configuration
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[BaiduTieBaCrawler] Launching browser in CDP mode")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[BaiduTieBaCrawler] Launching browser in standard mode")
                # Launch a browser context.
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.HEADLESS,
                )

            # Inject anti-detection scripts - for Baidu's special detection
            await self._inject_anti_detection_scripts()

            self.context_page = await self.browser_context.new_page()

            # First visit Baidu homepage, then click Tieba link to avoid triggering security verification
            await self._navigate_to_tieba_via_baidu()

            # Create a client to interact with the baidutieba website.
            self.tieba_client = await self.create_tieba_client(
                httpx_proxy_format,
                ip_proxy_pool if config.ENABLE_IP_PROXY else None
            )

            # Check login status and perform login if necessary
            if not await self.tieba_client.pong(browser_context=self.browser_context):
                login_obj = BaiduTieBaLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone="",  # your phone number
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.tieba_client.update_cookies(browser_context=self.browser_context)

            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                # Search for notes and retrieve their comment information.
                await self.search()
                await self.get_specified_tieba_notes()
            elif config.CRAWLER_TYPE == "detail":
                # Get the information and comments of the specified post
                await self.get_specified_notes()
            elif config.CRAWLER_TYPE == "creator":
                # Get creator's information and their notes and comments
                await self.get_creators_and_notes()
            else:
                pass

            utils.logger.info("[BaiduTieBaCrawler.start] Tieba Crawler finished ...")

    async def search(self) -> None:
        """
        Search for notes and retrieve their comment information.
        Returns:

        """
        utils.logger.info(
            "[BaiduTieBaCrawler.search] Begin search baidu tieba keywords"
        )
        tieba_limit_count = 10  # tieba limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < tieba_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = tieba_limit_count
        start_page = config.START_PAGE
        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(
                f"[BaiduTieBaCrawler.search] Current search keyword: {keyword}"
            )
            page = 1
            while (
                page - start_page + 1
            ) * tieba_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    utils.logger.info(f"[BaiduTieBaCrawler.search] Skip page {page}")
                    page += 1
                    continue
                try:
                    utils.logger.info(
                        f"[BaiduTieBaCrawler.search] search tieba keyword: {keyword}, page: {page}"
                    )
                    notes_list: List[TiebaNote] = (
                        await self.tieba_client.get_notes_by_keyword(
                            keyword=keyword,
                            page=page,
                            page_size=tieba_limit_count,
                            sort=SearchSortType.TIME_DESC,
                            note_type=SearchNoteType.FIXED_THREAD,
                        )
                    )
                    if not notes_list:
                        utils.logger.info(
                            f"[BaiduTieBaCrawler.search] Search note list is empty"
                        )
                        break
                    utils.logger.info(
                        f"[BaiduTieBaCrawler.search] Note list len: {len(notes_list)}"
                    )
                    await self.get_specified_notes(
                        note_id_list=[note_detail.note_id for note_detail in notes_list]
                    )

                    # Sleep after page navigation
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                    utils.logger.info(f"[TieBaCrawler.search] Sleeping for {config.CRAWLER_MAX_SLEEP_SEC} seconds after page {page}")

                    page += 1
                except Exception as ex:
                    utils.logger.error(
                        f"[BaiduTieBaCrawler.search] Search keywords error, c
# ... (truncated)

if 'crawl' not in dir():
    async def crawl(url: str, config: dict) -> list[dict]:
        for func_name in ['main', 'run', 'scrape']:
            if func_name in dir():
                func = globals()[func_name]
                import asyncio
                result = await func(url) if asyncio.iscoroutinefunction(func) else func(url)
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
        return [{"error": "No entry function found"}]
''',
        "tags": ['贴吧', '社区', '中文'],
        "difficulty": "medium",
        "author": "community",
        "source_url": "https://github.com/NanmiCoder/MediaCrawler",
        "use_browser": 1,
    },
    {
        "name": "抖音视频下载",
        "description": "社区爬虫 - 来自 Jack-Cherish/python-spider (GitHub高星项目)",
        "category": "social",
        "icon": "📱",
        "target_url": "https://www.douyin.com",
        "mode": "code_generator",
        "code": '''# Auto-adapted from requests/httpx script
import asyncio

# --- Original Code ---
# === douyin/douyin.py ===
# -*- coding:utf-8 -*-
from contextlib import closing
import requests, json, re, os, sys
import urllib

class DouYin(object):
	def __init__(self, width = 500, height = 300):
		"""
		抖音App视频下载
		"""
		self.headers = {
			'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36',
			'sec-fetch-mode': 'cors',
			'sec-fetch-site': 'same-origin',
			'accept': 'application/json',
			'accept-encoding': 'gzip, deflate, br',
			'accept-language': 'zh-CN,zh;q=0.9',
		}
		self.headers1 = {
			'User-Agent': 'Mozilla/5.0 (Linux; U; Android 5.1.1; zh-cn; MI 4S Build/LMY47V) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53.0.2785.146 Mobile Safari/537.36 XiaoMi/MiuiBrowser/9.1.3',
		}

	def get_video_urls(self, user_id, type_flag='f'):
		"""
		获得视频播放地址
		Parameters:
			user_id：查询的用户UID
		Returns:
			video_names: 视频名字列表
			video_urls: 视频链接列表
			nickname: 用户昵称
		"""
		video_names = []
		video_urls = []
		share_urls = []
		max_cursor = 0
		has_more = 1
		sign_api = 'http://49.233.200.77:5001'
		share_user_url = 'https://www.iesdouyin.com/share/user/%s' % user_id
		share_user = requests.get(share_user_url, headers=self.headers)
		while share_user.status_code != 200:
			share_user = requests.get(share_user_url, headers=self.headers)
		_tac_re = re.compile(r"tac='([\\s\\S]*?)'</script>")
		tac = _tac_re.search(share_user.text).group(1)
		_dytk_re = re.compile(r"dytk\\s*:\\s*'(.+)'")
		dytk = _dytk_re.search(share_user.text).group(1)
		_nickname_re = re.compile(r'<p class="nickname">(.+?)<\\/p>')
		nickname = _nickname_re.search(share_user.text).group(1)
		data = {
			'tac': tac.split('|')[0],
			'user_id': user_id,
		}
		req = requests.post(sign_api, data=data)
		while req.status_code != 200:
			req = requests.post(sign_api, data=data)
		sign = req.json().get('signature')
		user_url_prefix = 'https://www.iesdouyin.com/web/api/v2/aweme/like' if type_flag == 'f' else 'https://www.iesdouyin.com/web/api/v2/aweme/post'
		print('解析视频链接中')
		while has_more != 0:
			user_url = user_url_prefix + '/?user_id=%s&sec_uid=&count=21&max_cursor=%s&aid=1128&_signature=%s&dytk=%s' % (user_id, max_cursor, sign, dytk)
			req = requests.get(user_url, headers=self.headers)
			while req.status_code != 200:
				req = requests.get(user_url, headers=self.headers)
			html = json.loads(req.text)
			for each in html['aweme_list']:
				try:
					url = 'https://aweme.snssdk.com/aweme/v1/play/?video_id=%s&line=0&ratio=720p&media_type=4&vr_type=0&improve_bitrate=0&is_play_url=1&is_support_h265=0&source=PackSourceEnum_PUBLISH'
					vid = each['video']['vid']
					video_url = url % vid
				except:
					continue
				share_desc = each['desc']
				if os.name == 'nt':
					for c in r'\\/:*?"<>|':
						nickname = nickname.replace(c, '').strip().strip('\\.')
						share_desc = share_desc.replace(c, '').strip()
				share_id = each['aweme_id']
				if share_desc in ['抖音-原创音乐短视频社区', 'TikTok', '']:
					video_names.append(share_id + '.mp4')
				else:
					video_names.append(share_id + '-' + share_desc + '.mp4')
				share_url = 'https://www.iesdouyin.com/share/video/%s' % share_id
				share_urls.append(share_url)
				video_urls.append(video_url)
			max_cursor = html['max_cursor']
			has_more = html['has_more']

		return video_names, video_urls, share_urls, nickname

	def get_download_url(self, video_url, watermark_flag):
		"""
		获得带水印的视频播放地址
		Parameters:
			video_url：带水印的视频播放地址
		Returns:
			download_url: 带水印的视频下载地址
		"""
		# 带水印视频
		if watermark_flag == True:
			download_url = video_url.replace('/play/', '/playwm/')
		# 无水印视频
		else:
			download_url = video_url.replace('/playwm/', '/play/')

		return download_url

	def video_downloader(self, video_url, video_name, watermark_flag=False):
		"""
		视频下载
		Parameters:
			video_url: 带水印的视频地址
			video_name: 视频名
			watermark_flag: 是否下载带水印的视频
		Returns:
			无
		"""
		size = 0
		video_url = self.get_download_url(video_url, watermark_flag=watermark_flag)
		with closing(requests.get(video_url, headers=self.headers1, stream=True)) as response:
			chunk_size = 1024
			content_size = int(response.headers['content-length'])
			if response.status_code == 200:
				sys.stdout.write('  [文件大小]:%0.2f MB\\n' % (content_size / chunk_size / 1024))

				with open(video_name, 'wb') as file:
					for data in response.iter_content(chunk_size = chunk_size):
						file.write(data)
						size += len(data)
						file.flush()

						sys.stdout.write('  [下载进度]:%.2f%%' % float(size / content_size * 100) + '\\r')
						sys.stdout.flush()

	def run(self):
		"""
		运行函数
		Parameters:
			None
		Returns:
			None
		"""
		self.hello()
		print('UID取得方式：\\n分享用户页面，用浏览器打开短链接，原始链接中/share/user/后的数字即是UID')
		user_id = input('请输入UID (例如60388937600):')
		user_id = user_id if user_id else '60388937600'
		watermark_flag = input('是否下载带水印的视频 (0-否(默认), 1-是):')
		watermark_flag = watermark_flag if watermark_flag!='' else '0'
		watermark_flag = bool(int(watermark_flag))
		type_flag = input('f-收藏的(默认), p-上传的:')
		type_flag = type_flag if type_flag!='' else 'f'
		save_dir = input('保存路径 (例如"E:/Download/", 默认"./Download/"):')
		save_dir = save_dir if save_dir else "./Download/"
		video_names, video_urls, share_urls, nickname = self.get_video_urls(user_id, type_flag)
		nickname_dir = os.path.join(save_dir, nickname)
		if not os.path.exists(save_dir):
			os.makedirs(save_dir)
		if nickname not in os.listdir(save_dir):
			os.mkdir(nickname_dir)
		if type_flag == 'f':
			if 'favorite' not in os.listdir(nickname_dir):
				os.mkdir(os.path.join(nickname_dir, 'favorite'))
		print('视频下载中:共有%d个作品!\\n' % len(video_urls))
		for num in range(len(video_urls)):
			print('  解析第%d个视频链接 [%s] 中，请稍后!\\n' % (num + 1, share_urls[num]))
			if '\\\\' in video_names[num]:
				video_name = video_names[num].replace('\\\\', '')
			elif '/' in video_names[num]:
				video_name = video_names[num].replace('/', '')
			else:
				video_name = video_names[num]
			video_path = os.path.join(nickname_dir, video_name) if type_flag!='f' else os.path.join(nickname_dir, 'favorite', video_name)
			if os.path.isfile(video_path):
				print('视频已存在')
			else:
				self.video_downloader(video_urls[num], video_path, watermark_flag)
			print('\\n')
		print('下载完成!')

	def hello(self):
		"""
		打印欢迎界面
		Parameters:
			None
		Returns:
			None
		"""
		print('*' * 100)
		print('\\t\\t\\t\\t抖音App视频下载小助手')
		print('\\t\\t作者:Jack Cui、steven7851')
		print('*' * 100)


if __name__ == '__main__':
	douyin = DouYin()
	douyin.run()

# --- End Original ---

async def crawl(url: str, config: dict) -> list[dict]:
    """Adapter: runs the original script and captures output."""
    import io, sys, json

    for func_name in ['main', 'run', 'scrape', 'fetch', 'parse', 'spider', 'crawl_sync', 'get_data']:
        if func_name in dir():
            func = globals()[func_name]
            try:
                result = func(url) if url else func()
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
                else:
                    return [{"data": str(result)}]
            except Exception as e:
                return [{"error": str(e)}]

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))
    except:
        pass
    finally:
        sys.stdout = old_stdout

    output = buffer.getvalue()
    if output:
        try:
            return json.loads(output)
        except:
            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]

    return [{"error": "No output captured"}]
''',
        "tags": ['抖音', '下载', '视频'],
        "difficulty": "hard",
        "author": "community",
        "source_url": "https://github.com/Jack-Cherish/python-spider",
        "use_browser": 1,
    },
    {
        "name": "小红书数据采集",
        "description": "社区爬虫 - 来自 cv-cat/Spider_XHS (GitHub高星项目)",
        "category": "social",
        "icon": "📕",
        "target_url": "https://www.xiaohongshu.com",
        "mode": "code_generator",
        "code": '''# Auto-adapted from requests/httpx script
import asyncio

# --- Original Code ---
# === main.py ===
import json
import os
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, download_note, save_to_xlsx


class Data_Spider():
    def __init__(self):
        self.xhs_apis = XHS_Apis()

    def spider_note(self, note_url: str, cookies_str: str, proxies=None):
        """
        爬取一个笔记的信息
        :param note_url:
        :param cookies_str:
        :return:
        """
        note_info = None
        try:
            success, msg, note_info = self.xhs_apis.get_note_info(note_url, cookies_str, proxies)
            if success:
                note_info = note_info['data']['items'][0]
                note_info['url'] = note_url
                note_info = handle_note_info(note_info)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'爬取笔记信息 {note_url}: {success}, msg: {msg}')
        return success, msg, note_info

    def spider_some_note(self, notes: list, cookies_str: str, base_path: dict, save_choice: str, excel_name: str = '', proxies=None):
        """
        爬取一些笔记的信息
        :param notes:
        :param cookies_str:
        :param base_path:
        :return:
        """
        if (save_choice == 'all' or save_choice == 'excel') and excel_name == '':
            raise ValueError('excel_name 不能为空')
        note_list = []
        for note_url in notes:
            success, msg, note_info = self.spider_note(note_url, cookies_str, proxies)
            if note_info is not None and success:
                note_list.append(note_info)
        for note_info in note_list:
            if save_choice == 'all' or 'media' in save_choice:
                download_note(note_info, base_path['media'], save_choice)
        if save_choice == 'all' or save_choice == 'excel':
            file_path = os.path.abspath(os.path.join(base_path['excel'], f'{excel_name}.xlsx'))
            save_to_xlsx(note_list, file_path)


    def spider_user_all_note(self, user_url: str, cookies_str: str, base_path: dict, save_choice: str, excel_name: str = '', proxies=None):
        """
        爬取一个用户的所有笔记
        :param user_url:
        :param cookies_str:
        :param base_path:
        :return:
        """
        note_list = []
        try:
            success, msg, all_note_info = self.xhs_apis.get_user_all_notes(user_url, cookies_str, proxies)
            if success:
                logger.info(f'用户 {user_url} 作品数量: {len(all_note_info)}')
                for simple_note_info in all_note_info:
                    note_url = f"https://www.xiaohongshu.com/explore/{simple_note_info['note_id']}?xsec_token={simple_note_info['xsec_token']}"
                    note_list.append(note_url)
            if save_choice == 'all' or save_choice == 'excel':
                excel_name = user_url.split('/')[-1].split('?')[0]
            self.spider_some_note(note_list, cookies_str, base_path, save_choice, excel_name, proxies)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'爬取用户所有视频 {user_url}: {success}, msg: {msg}')
        return note_list, success, msg

    def spider_some_search_note(self, query: str, require_num: int, cookies_str: str, base_path: dict, save_choice: str, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo: dict = None,  excel_name: str = '', proxies=None):
        """
            指定数量搜索笔记，设置排序方式和笔记类型和笔记数量
            :param query 搜索的关键词
            :param require_num 搜索的数量
            :param cookies_str 你的cookies
            :param base_path 保存路径
            :param sort_type_choice 排序方式 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
            :param note_type 笔记类型 0 不限, 1 视频笔记, 2 普通笔记
            :param note_time 笔记时间 0 不限, 1 一天内, 2 一周内天, 3 半年内
            :param note_range 笔记范围 0 不限, 1 已看过, 2 未看过, 3 已关注
            :param pos_distance 位置距离 0 不限, 1 同城, 2 附近 指定这个必须要指定 geo
            返回搜索的结果
        """
        note_list = []
        try:
            success, msg, notes = self.xhs_apis.search_some_note(query, require_num, cookies_str, sort_type_choice, note_type, note_time, note_range, pos_distance, geo, proxies)
            if success:
                notes = list(filter(lambda x: x['model_type'] == "note", notes))
                logger.info(f'搜索关键词 {query} 笔记数量: {len(notes)}')
                for note in notes:
                    note_url = f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"
                    note_list.append(note_url)
            if save_choice == 'all' or save_choice == 'excel':
                excel_name = query
            self.spider_some_note(note_list, cookies_str, base_path, save_choice, excel_name, proxies)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'搜索关键词 {query} 笔记: {success}, msg: {msg}')
        return note_list, success, msg

# __main__ removed
    """
        此文件为爬虫的入口文件，可以直接运行
        apis/xhs_pc_apis.py 为爬虫的api文件，包含小红书的全部数据接口，可以继续封装
        apis/xhs_creator_apis.py 为小红书创作者中心的api文件
        感谢star和follow
    """

    cookies_str, base_path = init()
    data_spider = Data_Spider()
    """
        save_choice: all: 保存所有的信息, media: 保存视频和图片（media-video只下载视频, media-image只下载图片，media都下载）, excel: 保存到excel
        save_choice 为 excel 或者 all 时，excel_name 不能为空
    """


    # 1 爬取列表的所有笔记信息 笔记链接 如下所示 注意此url会过期！
    notes = [
        r'https://www.xiaohongshu.com/explore/683fe17f0000000023017c6a?xsec_token=ABBr_cMzallQeLyKSRdPk9fwzA0torkbT_ubuQP1ayvKA=&xsec_source=pc_user',
    ]
    data_spider.spider_some_note(notes, cookies_str, base_path, 'all', 'test')

    # 2 爬取用户的所有笔记信息 用户链接 如下所示 注意此url会过期！
    user_url = 'https://www.xiaohongshu.com/user/profile/64c3f392000000002b009e45?xsec_token=AB-GhAToFu07JwNk_AMICHnp7bSTjVz2beVIDBwSyPwvM=&xsec_source=pc_feed'
    data_spider.spider_user_all_note(user_url, cookies_str, base_path, 'all')

    # 3 搜索指定关键词的笔记
    query = "榴莲"
    query_num = 10
    sort_type_choice = 0  # 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
    note_type = 0 # 0 不限, 1 视频笔记, 2 普通笔记
    note_time = 0  # 0 不限, 1 一天内, 2 一周内天, 3 半年内
    note_range = 0  # 0 不限, 1 已看过, 2 未看过, 3 已关注
    pos_distance = 0  # 0 不限, 1 同城, 2 附近 指定这个1或2必须要指定 geo
    # geo = {
    #     # 经纬度
    #     "latitude": 39.9725,
    #     "longitude": 116.4207
    # }
    data_spider.spider_some_search_note(query, query_num, cookies_str, base_path, 'all', sort_type_choice, note_type, note_time, note_range, pos_distance, geo=None)

# --- End Original ---

async def crawl(url: str, config: dict) -> list[dict]:
    """Adapter: runs the original script and captures output."""
    import io, sys, json

    for func_name in ['main', 'run', 'scrape', 'fetch', 'parse', 'spider', 'crawl_sync', 'get_data']:
        if func_name in dir():
            func = globals()[func_name]
            try:
                result = func(url) if url else func()
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
                else:
                    return [{"data": str(result)}]
            except Exception as e:
                return [{"error": str(e)}]

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))
    except:
        pass
    finally:
        sys.stdout = old_stdout

    output = buffer.getvalue()
    if output:
        try:
            return json.loads(output)
        except:
            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]

    return [{"error": "No output captured"}]
''',
        "tags": ['小红书', '采集', '运营'],
        "difficulty": "hard",
        "author": "community",
        "source_url": "https://github.com/cv-cat/Spider_XHS",
        "use_browser": 1,
    },
    {
        "name": "微博用户爬虫",
        "description": "社区爬虫 - 来自 dataabc/weiboSpider (GitHub高星项目)",
        "category": "social",
        "icon": "📱",
        "target_url": "https://weibo.com",
        "mode": "code_generator",
        "code": '''# Auto-adapted from requests/httpx script
import asyncio

# --- Original Code ---
# === weibo_spider/spider.py ===
#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import json
import logging
import logging.config
import os
import random
import shutil
import sys
import asyncio
import aiohttp
from datetime import date, datetime, timedelta
from time import sleep

from absl import app, flags
from tqdm import tqdm

from . import config_util, datetime_util
from .downloader import AvatarPictureDownloader
from .parser import AlbumParser, IndexParser, PageParser, PhotoParser
from .parser.util import handle_html_async
from .user import User

FLAGS = flags.FLAGS

flags.DEFINE_string('config_path', None, 'The path to config.json.')
flags.DEFINE_string('u', None, 'The user_id we want to input.')
flags.DEFINE_string('user_id_list', None, 'The path to user_id_list.txt.')
flags.DEFINE_string('output_dir', None, 'The dir path to store results.')

logging_path = os.path.split(
    os.path.realpath(__file__))[0] + os.sep + 'logging.conf'
logging.config.fileConfig(logging_path)
logger = logging.getLogger('spider')


class Spider:
    def __init__(self, config):
        """Weibo类初始化"""
        self.filter = config[
            'filter']  # 取值范围为0、1,程序默认值为0,代表要爬取用户的全部微博,1代表只爬取用户的原创微博
        since_date = config['since_date']
        if isinstance(since_date, int):
            since_date = date.today() - timedelta(since_date)
        self.since_date = str(
            since_date)  # 起始时间，即爬取发布日期从该值到结束时间的微博，形式为yyyy-mm-dd
        self.end_date = config[
            'end_date']  # 结束时间，即爬取发布日期从起始时间到该值的微博，形式为yyyy-mm-dd，特殊值"now"代表现在
        random_wait_pages = config['random_wait_pages']
        self.random_wait_pages = [
            min(random_wait_pages),
            max(random_wait_pages)
        ]  # 随机等待频率，即每爬多少页暂停一次
        random_wait_seconds = config['random_wait_seconds']
        self.random_wait_seconds = [
            min(random_wait_seconds),
            max(random_wait_seconds)
        ]  # 随机等待时间，即每次暂停要sleep多少秒
        self.global_wait = config['global_wait']  # 配置全局等待时间，如每爬1000页等待3600秒等
        self.page_count = 0  # 统计每次全局等待后，爬取了多少页，若页数满足全局等待要求就进入下一次全局等待
        self.write_mode = config[
            'write_mode']  # 结果信息保存类型，为list形式，可包含txt、csv、json、mongo和mysql五种类型
        self.pic_download = config[
            'pic_download']  # 取值范围为0、1,程序默认值为0,代表不下载微博原始图片,1代表下载
        self.video_download = config[
            'video_download']  # 取值范围为0、1,程序默认为0,代表不下载微博视频,1代表下载
        self.file_download_timeout = config.get(
            'file_download_timeout',
            [5, 5, 10
             ])  # 控制文件下载“超时”时的操作，值是list形式，包含三个数字，依次分别是最大超时重试次数、最大连接时间和最大读取时间
        self.result_dir_name = config.get(
            'result_dir_name', 0)  # 结果目录名，取值为0或1，决定结果文件存储在用户昵称文件夹里还是用户id文件夹里
        self.cookie = config['cookie']
        self.mysql_config = config.get('mysql_config')  # MySQL数据库连接配置，可以不填

        self.sqlite_config = config.get('sqlite_config')
        self.kafka_config = config.get('kafka_config')
        self.mongo_config = config.get('mongo_config')
        self.post_config = config.get('post_config')
        self.user_config_file_path = ''
        user_id_list = config['user_id_list']
        if FLAGS.user_id_list:
            user_id_list = FLAGS.user_id_list
        if not isinstance(user_id_list, list):
            if not os.path.isabs(user_id_list):
                user_id_list = os.getcwd() + os.sep + user_id_list
            if not os.path.isfile(user_id_list):
                logger.warning('不存在%s文件', user_id_list)
                sys.exit()
            self.user_config_file_path = user_id_list
        if FLAGS.u:
            user_id_list = FLAGS.u.split(',')
        if isinstance(user_id_list, list):
            # 第一部分是处理dict类型的
            # 第二部分是其他类型,其他类型提供去重功能
            user_config_list = list(
                map(
                    lambda x: {
                        'user_uri': x['id'],
                        'since_date': x.get('since_date', self.since_date),
                        'end_date': x.get('end_date', self.end_date),
                    }, [user_id for user_id in user_id_list
                        if isinstance(user_id, dict)])) + list(
                    map(
                        lambda x: {
                            'user_uri': x,
                            'since_date': self.since_date,
                            'end_date': self.end_date
                        },
                        set([
                            user_id for user_id in user_id_list
                            if not isinstance(user_id, dict)
                        ])))
            if FLAGS.u:
                config_util.add_user_uri_list(self.user_config_file_path,
                                              user_id_list)
        else:
            user_config_list = config_util.get_user_config_list(
                user_id_list, self.since_date)
            for user_config in user_config_list:
                user_config['end_date'] = self.end_date
        self.user_config_list = user_config_list  # 要爬取的微博用户的user_config列表
        self.user_config = {}  # 用户配置,包含用户id和since_date
        self.new_since_date = ''  # 完成某用户爬取后，自动生成对应用户新的since_date
        self.user = User()  # 存储爬取到的用户信息
        self.got_num = 0  # 存储爬取到的微博数
        self.weibo_id_list = []  # 存储爬取到的所有微博id
        self.session = None # aiohttp session

    async def write_weibo(self, weibos):
        """将爬取到的信息写入文件或数据库"""
        for downloader in self.downloaders:
            await downloader.download_files(weibos, self.session)
        for writer in self.writers:
            writer.write_weibo(weibos)

    def write_user(self, user):
        """将用户信息写入数据库"""
        for writer in self.writers:
            writer.write_user(user)

    async def get_user_info(self, user_uri):
        """获取用户信息"""
        url = 'https://weibo.cn/%s/profile' % (user_uri)
        selector = await handle_html_async(self.cookie, url, self.session)
        self.user = await IndexParser(self.cookie, user_uri, selector=selector).get_user_async(self.session)
        self.page_count += 1

    async def download_user_avatar(self, user_uri):
        """下载用户头像"""
        # Note: This remains synchronous for now as it's a minor part of the flow
        avatar_album_url = PhotoParser(self.cookie,
                                       user_uri).extract_avatar_album_url()
        pic_urls = AlbumParser(self.cookie,
                               avatar_album_url).extract_pic_urls()
        await AvatarPictureDownloader(
            self._get_filepath('img'),
            self.file_download_timeout).handle_download(pic_urls, self.session)

    async def get_weibo_info(self):
        """获取微博信息"""
        try:
            since_date = datetime_util.str_to_time(
                self.user_config['since_date'])
            now = datetime.now()
            if since_date <= now:
                # Async fetch page num
                user_uri = self.user_config['user_uri']
                url = 'https://weibo.cn/%s/profile' % (user_uri)
                selector = await handle_html_async(self.cookie, url, self.session)
                page_num = IndexParser(self.cookie, user_uri, selector=selector).get_page_num()
                
                self.page_count += 1
                if self.page_count > 2 and (self.page_count +
                                            page_num) > self.global_wait[0][0]:
                    wait_seconds = int(
                        self.global_wait[0][1] *
                        min(1, self.page_count / self.global_wait[0][0]))
                    logger.info(u'即将进入全局等待时间，%d秒后程序继续执行' % wait_seconds)
                    for i in tqdm(range(wait_seconds)):
                        await asyncio.sleep(1)
                    self.page_count = 0
                    self.global_wait.append(self.global_wait.pop(0))
                page1 = 0
                random_pages = random.randint(*self.random_wait_pages)
                for page in tqdm(range(1, page_num + 1), desc='Progress
# ... (truncated)
# --- End Original ---

async def crawl(url: str, config: dict) -> list[dict]:
    """Adapter: runs the original script and captures output."""
    import io, sys, json

    for func_name in ['main', 'run', 'scrape', 'fetch', 'parse', 'spider', 'crawl_sync', 'get_data']:
        if func_name in dir():
            func = globals()[func_name]
            try:
                result = func(url) if url else func()
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
                else:
                    return [{"data": str(result)}]
            except Exception as e:
                return [{"error": str(e)}]

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))
    except:
        pass
    finally:
        sys.stdout = old_stdout

    output = buffer.getvalue()
    if output:
        try:
            return json.loads(output)
        except:
            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]

    return [{"error": "No output captured"}]
''',
        "tags": ['微博', '用户', '社交'],
        "difficulty": "medium",
        "author": "community",
        "source_url": "https://github.com/dataabc/weiboSpider",
    },
    {
        "name": "TuShare金融数据",
        "description": "社区爬虫 - 来自 waditu/tushare (GitHub高星项目)",
        "category": "finance",
        "icon": "📊",
        "target_url": "",
        "mode": "code_generator",
        "code": '''# Auto-adapted from requests/httpx script
import asyncio

# --- Original Code ---
# === tushare/stock/trading.py ===
# -*- coding:utf-8 -*- 
"""
交易数据接口 
Created on 2014/07/31
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""
from __future__ import division

import time
import json
import lxml.html
from lxml import etree
import pandas as pd
import numpy as np
import datetime
from tushare.stock import cons as ct
import re
from pandas.compat import StringIO
from tushare.util import dateu as du
from tushare.util.formula import MA
import os
from tushare.util.conns import get_apis, close_apis
from tushare.stock.fundamental import get_stock_basics
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request


def get_hist_data(code=None, start=None, end=None,
                  ktype='D', retry_count=3,
                  pause=0.001):
    """
        获取个股历史交易记录
    Parameters
    ------
      code:string
                  股票代码 e.g. 600848
      start:string
                  开始日期 format：YYYY-MM-DD 为空时取到API所提供的最早日期数据
      end:string
                  结束日期 format：YYYY-MM-DD 为空时取到最近一个交易日数据
      ktype：string
                  数据类型，D=日k线 W=周 M=月 5=5分钟 15=15分钟 30=30分钟 60=60分钟，默认为D
      retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
      pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    return
    -------
      DataFrame
          属性:日期 ，开盘价， 最高价， 收盘价， 最低价， 成交量， 价格变动 ，涨跌幅，5日均价，10日均价，20日均价，5日均量，10日均量，20日均量，换手率
    """
    symbol = ct._code_to_symbol(code)
    url = ''
    if ktype.upper() in ct.K_LABELS:
        url = ct.DAY_PRICE_URL%(ct.P_TYPE['http'], ct.DOMAINS['ifeng'],
                                ct.K_TYPE[ktype.upper()], symbol)
    elif ktype in ct.K_MIN_LABELS:
        url = ct.DAY_PRICE_MIN_URL%(ct.P_TYPE['http'], ct.DOMAINS['ifeng'],
                                    symbol, ktype)
    else:
        raise TypeError('ktype input error.')
    
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(url)
            lines = urlopen(request, timeout = 10).read()
            if len(lines) < 15: #no data
                return None
        except Exception as e:
            print(e)
        else:
            js = json.loads(lines.decode('utf-8') if ct.PY3 else lines)
            cols = []
            if (code in ct.INDEX_LABELS) & (ktype.upper() in ct.K_LABELS):
                cols = ct.INX_DAY_PRICE_COLUMNS
            else:
                cols = ct.DAY_PRICE_COLUMNS
            if len(js['record'][0]) == 14:
                cols = ct.INX_DAY_PRICE_COLUMNS
            df = pd.DataFrame(js['record'], columns=cols)
            if ktype.upper() in ['D', 'W', 'M']:
                df = df.applymap(lambda x: x.replace(u',', u''))
                df[df==''] = 0
            for col in cols[1:]:
                df[col] = df[col].astype(float)
            if start is not None:
                df = df[df.date >= start]
            if end is not None:
                df = df[df.date <= end]
            if (code in ct.INDEX_LABELS) & (ktype in ct.K_MIN_LABELS):
                df = df.drop('turnover', axis=1)
            df = df.set_index('date')
            df = df.sort_index(ascending = False)
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def _parsing_dayprice_json(types=None, page=1):
    """
           处理当日行情分页数据，格式为json
     Parameters
     ------
        pageNum:页码
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
    """
    ct._write_console()
    request = Request(ct.SINA_DAY_PRICE_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                 ct.PAGES['jv'], types, page))
    text = urlopen(request, timeout=10).read()
    if text == 'null':
        return None
    reg = re.compile(r'\\,(.*?)\\:') 
    text = reg.sub(r',"\\1":', text.decode('gbk') if ct.PY3 else text) 
    text = text.replace('"{symbol', '{"symbol')
    text = text.replace('{symbol', '{"symbol"')
    if ct.PY3:
        jstr = json.dumps(text)
    else:
        jstr = json.dumps(text, encoding='GBK')
    js = json.loads(jstr)
    df = pd.DataFrame(pd.read_json(js, dtype={'code':object}),
                      columns=ct.DAY_TRADING_COLUMNS)
    df = df.drop('symbol', axis=1)
#     df = df.ix[df.volume > 0]
    return df


def get_tick_data(code=None, date=None, retry_count=3, pause=0.001,
                  src='sn'):
    """
        获取分笔数据
    Parameters
    ------
        code:string
                  股票代码 e.g. 600848
        date:string
                  日期 format: YYYY-MM-DD
        retry_count : int, 默认 3
                  如遇网络等问题重复执行的次数
        pause : int, 默认 0
                 重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
        src : 数据源选择，可输入sn(新浪)、tt(腾讯)、nt(网易)，默认sn
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
              属性:成交时间、成交价格、价格变动，成交手、成交金额(元)，买卖类型
    """
    if (src.strip() not in ct.TICK_SRCS):
        print(ct.TICK_SRC_ERROR)
        return None
    symbol = ct._code_to_symbol(code)
    symbol_dgt = ct._code_to_symbol_dgt(code)
    datestr = date.replace('-', '')
    url = {
            ct.TICK_SRCS[0] : ct.TICK_PRICE_URL % (ct.P_TYPE['http'], ct.DOMAINS['sf'], ct.PAGES['dl'],
                                date, symbol),
            ct.TICK_SRCS[1] : ct.TICK_PRICE_URL_TT % (ct.P_TYPE['http'], ct.DOMAINS['tt'], ct.PAGES['idx'],
                                           symbol, datestr),
            ct.TICK_SRCS[2] : ct.TICK_PRICE_URL_NT % (ct.P_TYPE['http'], ct.DOMAINS['163'], date[0:4], 
                                         datestr, symbol_dgt)
             }
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            if src == ct.TICK_SRCS[2]:
                df = pd.read_excel(url[src])
                df.columns = ct.TICK_COLUMNS
            else:
                re = Request(url[src])
                lines = urlopen(re, timeout=10).read()
                lines = lines.decode('GBK') 
                if len(lines) < 20:
                    return None
                df = pd.read_table(StringIO(lines), names=ct.TICK_COLUMNS,
                                   skiprows=[0])      
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_sina_dd(code=None, date=None, vol=400, retry_count=3, pause=0.001):
    """
        获取sina大单数据
    Parameters
    ------
        code:string
                  股票代码 e.g. 600848
        date:string
                  日期 format：YYYY-MM-DD
        retry_count : int, 默认 3
                  如遇网络等问题重复执行的次数
        pause : int, 默认 0
                 重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
              属性:股票代码    股票名称    交易时间    价格    成交量    前一笔价格    类型（买、卖、中性盘）
    """
    if code is None or len(code)!=6 or date is None:
        return None
    symbol = ct._code_to_symbol(code)
    vol = vol*100
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            re = Request(ct.SINA_DD % (ct.P_TYPE['http'], ct.DOMAINS['vsf'], ct.PAGES['sinadd'],
                                symbol, vol, date))
            lines = urlopen(re, timeout=10).read()
            lines = lines.decode('GBK') 
            if len(lines) < 100:
                return None
            df = pd.read_csv(StringIO(lines), names=ct.SINA_DD_COLS,
                               skiprows=[0])    
            if df is not None:
                df['code'] = df['code'].map(lambda x: x[2:])
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_today_ticks(code=None, retry_count=3, pause=0.001):
    """
        获取当日分笔明细数据
    Parameters
    ------
        code
# ... (truncated)
# --- End Original ---

async def crawl(url: str, config: dict) -> list[dict]:
    """Adapter: runs the original script and captures output."""
    import io, sys, json

    for func_name in ['main', 'run', 'scrape', 'fetch', 'parse', 'spider', 'crawl_sync', 'get_data']:
        if func_name in dir():
            func = globals()[func_name]
            try:
                result = func(url) if url else func()
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {"data": str(r)} for r in result]
                elif isinstance(result, dict):
                    return [result]
                else:
                    return [{"data": str(result)}]
            except Exception as e:
                return [{"error": str(e)}]

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        exec(compile(open(__file__).read() if hasattr(__file__, "read") else "", "<adapted>", "exec"))
    except:
        pass
    finally:
        sys.stdout = old_stdout

    output = buffer.getvalue()
    if output:
        try:
            return json.loads(output)
        except:
            return [{"output": line} for line in output.strip().split("\\n") if line.strip()]

    return [{"error": "No output captured"}]
''',
        "tags": ['金融', '股票', '数据', 'A股'],
        "difficulty": "easy",
        "author": "community",
        "source_url": "https://github.com/waditu/tushare",
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
