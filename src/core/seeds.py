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
