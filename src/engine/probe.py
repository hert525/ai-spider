"""
站点探测模块 — 探测目标网站技术栈和反爬机制。

用法::

    from src.engine.probe import probe_site
    result = await probe_site("https://example.com")
"""
from __future__ import annotations

import ssl
import time
import asyncio
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger


async def probe_site(url: str) -> dict:
    """
    探测目标网站，返回探测报告。

    检测项目:
    - robots.txt 是否存在及内容摘要
    - sitemap.xml 是否存在
    - 反爬机制检测（Cloudflare/WAF等）
    - 响应时间
    - TLS版本
    - 基本HTTP头信息
    """
    report: dict = {
        "url": url,
        "status": "ok",
        "response_time_ms": None,
        "http_status": None,
        "tls_version": None,
        "server": None,
        "robots_txt": {"exists": False, "content_preview": None},
        "sitemap_xml": {"exists": False, "url": None},
        "anti_crawler": {
            "cloudflare": False,
            "waf_detected": False,
            "captcha_detected": False,
            "details": [],
        },
        "headers": {},
        "errors": [],
    }

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # 通用请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            verify=True,
            headers=headers,
        ) as client:
            # 1. 主页请求 + 响应时间
            t0 = time.monotonic()
            resp = await client.get(url)
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            report["response_time_ms"] = elapsed_ms
            report["http_status"] = resp.status_code

            # HTTP头
            report["server"] = resp.headers.get("server")
            report["headers"] = {
                k: v for k, v in resp.headers.items()
                if k.lower() in (
                    "server", "x-powered-by", "content-type",
                    "x-frame-options", "strict-transport-security",
                    "content-security-policy", "x-content-type-options",
                )
            }

            # TLS版本检测
            report["tls_version"] = await _detect_tls(parsed.hostname, parsed.port or 443)

            # 反爬检测
            _detect_anti_crawler(resp, report)

            # 2. robots.txt
            try:
                robots_resp = await client.get(urljoin(base_url, "/robots.txt"))
                if robots_resp.status_code == 200 and "user-agent" in robots_resp.text.lower():
                    report["robots_txt"]["exists"] = True
                    # 截取前500字符作为预览
                    report["robots_txt"]["content_preview"] = robots_resp.text[:500]
            except Exception as e:
                report["errors"].append(f"robots.txt检测失败: {str(e)[:80]}")

            # 3. sitemap.xml
            try:
                sitemap_resp = await client.get(urljoin(base_url, "/sitemap.xml"))
                if sitemap_resp.status_code == 200 and "<?xml" in sitemap_resp.text[:200]:
                    report["sitemap_xml"]["exists"] = True
                    report["sitemap_xml"]["url"] = urljoin(base_url, "/sitemap.xml")
            except Exception as e:
                report["errors"].append(f"sitemap.xml检测失败: {str(e)[:80]}")

    except httpx.ConnectError as e:
        report["status"] = "error"
        report["errors"].append(f"连接失败: {str(e)[:120]}")
    except httpx.TimeoutException:
        report["status"] = "error"
        report["errors"].append("请求超时(15s)")
    except Exception as e:
        report["status"] = "error"
        report["errors"].append(f"探测异常: {str(e)[:120]}")

    return report


async def _detect_tls(hostname: str | None, port: int) -> str | None:
    """检测TLS版本"""
    if not hostname:
        return None
    try:
        ctx = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, port, ssl=ctx),
            timeout=5.0,
        )
        ssl_obj = writer.get_extra_info("ssl_object")
        version = ssl_obj.version() if ssl_obj else None
        writer.close()
        await writer.wait_closed()
        return version
    except Exception:
        return None


def _detect_anti_crawler(resp: httpx.Response, report: dict) -> None:
    """通过响应头和内容检测反爬机制"""
    anti = report["anti_crawler"]
    headers_lower = {k.lower(): v for k, v in resp.headers.items()}
    body_lower = resp.text[:5000].lower() if resp.text else ""

    # Cloudflare 检测
    cf_indicators = ["cf-ray", "cf-cache-status", "cf-request-id"]
    if any(h in headers_lower for h in cf_indicators):
        anti["cloudflare"] = True
        anti["details"].append("检测到Cloudflare CDN/WAF")

    if "server" in headers_lower and "cloudflare" in headers_lower["server"].lower():
        anti["cloudflare"] = True

    # WAF 检测
    waf_headers = ["x-sucuri-id", "x-sucuri-cache", "x-akamai-transformed", "x-cdn"]
    for h in waf_headers:
        if h in headers_lower:
            anti["waf_detected"] = True
            anti["details"].append(f"检测到WAF/CDN头: {h}")

    # 验证码检测
    captcha_keywords = ["captcha", "recaptcha", "hcaptcha", "challenge-platform"]
    if any(kw in body_lower for kw in captcha_keywords):
        anti["captcha_detected"] = True
        anti["details"].append("页面包含验证码")

    # JS挑战检测
    if resp.status_code == 403 and ("just a moment" in body_lower or "checking your browser" in body_lower):
        anti["waf_detected"] = True
        anti["details"].append("检测到浏览器JS挑战（可能需要浏览器模式）")
