"""Sandbox - 安全的代码执行环境。

安全措施:
1. 白名单__builtins__: 只暴露安全的内置函数
2. 受限import: 只允许爬虫相关的模块
3. 子进程隔离: 通过asyncio.subprocess在独立进程执行
4. 超时强制kill
5. 禁止os/subprocess/sys/shutil/socket等危险模块
"""
import asyncio
import sys
import traceback
import textwrap
from io import StringIO
from typing import Any

# Allow nested asyncio.run() inside sandbox (AI-generated code often uses it)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass
from loguru import logger
from src.core.config import settings

# ── 安全: 允许的内置函数白名单 ──
_SAFE_BUILTINS = {
    # 基础类型
    "True": True, "False": False, "None": None,
    "int": int, "float": float, "str": str, "bool": bool,
    "bytes": bytes, "bytearray": bytearray,
    "list": list, "tuple": tuple, "dict": dict, "set": set, "frozenset": frozenset,
    # 常用函数
    "len": len, "range": range, "enumerate": enumerate, "zip": zip,
    "map": map, "filter": filter, "sorted": sorted, "reversed": reversed,
    "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
    "any": any, "all": all,
    "isinstance": isinstance, "issubclass": issubclass, "type": type,
    "hasattr": hasattr, "getattr": getattr, "setattr": setattr,
    "repr": repr, "hash": hash, "id": id, "callable": callable,
    "iter": iter, "next": next,
    "print": print, "input": lambda *a, **k: "",  # input永远返回空
    "chr": chr, "ord": ord,
    "hex": hex, "oct": oct, "bin": bin,
    "format": format,
    "globals": globals, "locals": locals,
    "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
    "IndexError": IndexError, "AttributeError": AttributeError,
    "StopIteration": StopIteration, "RuntimeError": RuntimeError,
    "Exception": Exception,
    # 需要受控的import
    "__import__": None,  # 下面单独处理
}

# ── 安全: 允许import的模块白名单 ──
_ALLOWED_MODULES = {
    "json", "re", "csv", "math", "time", "datetime", "urllib.parse",
    "collections", "itertools", "functools", "string", "textwrap",
    "hashlib", "base64", "html", "xml.etree.ElementTree",
    "httpx", "parsel", "bs4", "lxml", "asyncio",
    "typing", "dataclasses", "enum", "copy", "io",
}

# ── 明确禁止的模块 ──
_BLOCKED_MODULES = {
    "os", "subprocess", "sys", "shutil", "signal", "ctypes",
    "socket", "multiprocessing", "threading", "importlib",
    "code", "codeop", "compile", "compileall",
    "pathlib",  # 可以通过pathlib做文件操作
    "sqlite3", "psycopg2", "asyncpg",  # 禁止直接操作数据库
    "pickle", "shelve", "marshal",  # 反序列化攻击
    "builtins", "__builtin__",
}


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """受控的import函数 — 只允许白名单模块"""
    # 检查顶层模块名
    top_module = name.split(".")[0]
    if top_module in _BLOCKED_MODULES:
        raise ImportError(f"模块 '{name}' 在沙箱中被禁止 (安全限制)")
    if top_module not in _ALLOWED_MODULES and name not in _ALLOWED_MODULES:
        raise ImportError(f"模块 '{name}' 不在沙箱白名单中")
    return __builtins__["__import__"](name, globals, locals, fromlist, level)


def _fix_common_httpx_mistakes(code: str) -> str:
    """Fix common httpx usage mistakes that CodeSanitizer might miss."""
    import re as _re
    # resp.text() → resp.text (it's a property, not method)
    # This applies regardless of httpx — resp.text() is wrong in httpx context
    code = _re.sub(r'\bresp\.text\(\)', 'resp.text', code)
    code = _re.sub(r'\bresponse\.text\(\)', 'response.text', code)
    # In sandbox context we always use httpx, so always fix these
    # await resp.json() → resp.json()
    code = _re.sub(r'\bawait\s+(resp\.json\s*\()', r'\1', code)
    code = _re.sub(r'\bawait\s+(response\.json\s*\()', r'\1', code)
    code = _re.sub(r'\bawait\s+(r\.json\s*\()', r'\1', code)
    # await resp.text → resp.text (it's a property)
    code = _re.sub(r'\bawait\s+(resp\.text)\b(?!\s*\()', r'\1', code)
    code = _re.sub(r'\bawait\s+(response\.text)\b(?!\s*\()', r'\1', code)
    return code


async def run_code_in_sandbox(
    code: str,
    target_url: str = "",
    html: str = "",
    timeout: int | None = None,
    proxy_config: dict | None = None,
    browser_cookies: list[dict] | None = None,
    api_data: list | None = None,
) -> dict:
    """在受限沙箱中执行爬虫代码。

    代码必须定义: async def crawl(url: str, config: dict) -> list[dict]

    返回 dict: 'output', 'error', 'pages_crawled', 'duration_ms'
    """
    timeout = timeout or settings.sandbox_timeout
    import time
    start = time.monotonic()

    # 自动适配非标准代码格式
    from src.engine.adapters import CodeAdapter
    detected_format = CodeAdapter.detect_format(code)
    if detected_format != "standard":
        code = CodeAdapter.wrap(code, detected_format)
        logger.info(f"Sandbox: 自动适配代码格式 {detected_format}")

    # AST自动修复 — 在安全检查之前修复常见LLM错误
    from src.engine.code_sanitizer import CodeSanitizer
    code, applied_fixes = CodeSanitizer.sanitize(code)
    if applied_fixes:
        logger.info(f"Sandbox: 自动修复 {len(applied_fixes)} 个问题: {', '.join(applied_fixes)}")

    # Quick static validation of common httpx patterns
    code = _fix_common_httpx_mistakes(code)

    # 静态安全检查 — 在exec之前拦截
    security_error = _static_security_check(code)
    if security_error:
        return {
            "output": [],
            "error": f"安全检查失败: {security_error}",
            "pages_crawled": 0,
            "duration_ms": int((time.monotonic() - start) * 1000),
        }

    # 准备沙箱全局变量
    import httpx
    import parsel
    import json
    import re
    import csv

    safe_builtins = dict(_SAFE_BUILTINS)
    safe_builtins["__import__"] = _safe_import

    # Wrap json module to catch unawaited coroutines (common LLM mistake)
    import types as _types
    _patched_json = _types.ModuleType("json")
    for _attr in dir(json):
        if not _attr.startswith("_"):
            setattr(_patched_json, _attr, getattr(json, _attr))

    _orig_dumps = json.dumps
    def _safe_json_dumps(obj, **kwargs):
        if asyncio.iscoroutine(obj):
            raise TypeError(
                "尝试序列化协程对象 — 你可能忘了 await。"
                "例如应该用 json.dumps(await func()) 而不是 json.dumps(func())"
            )
        if asyncio.isfuture(obj):
            raise TypeError(
                "尝试序列化Future对象 — 你可能忘了 await。"
            )
        return _orig_dumps(obj, **kwargs)
    _patched_json.dumps = _safe_json_dumps

    sandbox_globals = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
        "httpx": httpx,
        "parsel": parsel,
        "json": _patched_json,
        "re": re,
        "csv": csv,
        "asyncio": asyncio,
        "print": print,
    }

    # Playwright可选
    try:
        from playwright.async_api import async_playwright
        sandbox_globals["async_playwright"] = async_playwright
    except ImportError:
        pass

    # 注入原始HTML(用于测试) — 同时 monkey-patch httpx 让代码自动拿到渲染后的HTML
    if html:
        sandbox_globals["__raw_html__"] = html
        # Patch httpx.AsyncClient.get to return pre-rendered HTML for the target URL
        _real_httpx = sandbox_globals.get("httpx")
        if _real_httpx:
            import types
            _orig_client_class = _real_httpx.AsyncClient

            class _PatchedClient(_orig_client_class):
                _pre_rendered_html = html
                _target = target_url
                _html_served = False  # Only serve pre-rendered HTML once

                @staticmethod
                def _urls_match(req_url, target):
                    """Match URLs ignoring query params and trailing slashes."""
                    if not target:
                        return False
                    from urllib.parse import urlparse
                    r = urlparse(str(req_url))
                    t = urlparse(str(target))
                    return (r.scheme == t.scheme
                            and r.netloc == t.netloc
                            and r.path.rstrip('/') == t.path.rstrip('/'))

                async def get(self, url, **kwargs):
                    if not _PatchedClient._html_served and self._urls_match(url, self._target):
                        _PatchedClient._html_served = True
                        _html = self._pre_rendered_html
                        _req_url = url
                        class _FakeResp:
                            status_code = 200
                            text = _html
                            content = _html.encode('utf-8')
                            headers = {"content-type": "text/html; charset=utf-8"}
                            url = _req_url
                            def json(self): import json as _j; return _j.loads(_html)
                            def raise_for_status(self): pass
                        return _FakeResp()
                    return await super().get(url, **kwargs)

                async def post(self, url, **kwargs):
                    if not _PatchedClient._html_served and self._urls_match(url, self._target):
                        _PatchedClient._html_served = True
                        _html = self._pre_rendered_html
                        _req_url = url
                        class _FakeResp:
                            status_code = 200
                            text = _html
                            content = _html.encode('utf-8')
                            headers = {"content-type": "text/html; charset=utf-8"}
                            url = _req_url
                            def json(self): import json as _j; return _j.loads(_html)
                            def raise_for_status(self): pass
                        return _FakeResp()
                    return await super().post(url, **kwargs)

            _real_httpx.AsyncClient = _PatchedClient
            sandbox_globals["httpx"] = _real_httpx

    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()

    try:
        # compile with PyCF_ALLOW_TOP_LEVEL_AWAIT so LLM-generated code
        # with top-level `await` statements doesn't cause SyntaxError
        import ast as _ast
        import types as _types_mod
        import inspect as _inspect
        compiled = compile(code, "<string>", "exec",
                           flags=_ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        # exec() ALWAYS returns None — even with PyCF_ALLOW_TOP_LEVEL_AWAIT.
        # If code has top-level await, the code object has CO_COROUTINE flag.
        # We must wrap it in a FunctionType and await the call.
        if compiled.co_flags & _inspect.CO_COROUTINE:
            _async_fn = _types_mod.FunctionType(compiled, sandbox_globals)
            await _async_fn()
        else:
            exec(compiled, sandbox_globals)
        crawl_fn = sandbox_globals.get("crawl")
        if not crawl_fn:
            # Fallback: look for any async function that takes 2 params (url, config)
            import inspect
            for name, obj in sandbox_globals.items():
                if name.startswith("_"):
                    continue
                if asyncio.iscoroutinefunction(obj):
                    try:
                        sig = inspect.signature(obj)
                        if len(sig.parameters) >= 1:
                            crawl_fn = obj
                            logger.info(f"Sandbox: 未找到crawl(), 使用替代函数 '{name}'")
                            break
                    except (ValueError, TypeError):
                        continue

        if not crawl_fn:
            # Last resort: look for sync functions named main/run/scrape/fetch
            for fname in ("main", "run", "scrape", "fetch", "parse", "get_data", "spider"):
                fn = sandbox_globals.get(fname)
                if callable(fn) and not asyncio.iscoroutinefunction(fn):
                    # Wrap sync function as async
                    _sync_fn = fn
                    async def _async_wrapper(url, config, _f=_sync_fn):
                        return await asyncio.to_thread(_f, url)
                    crawl_fn = _async_wrapper
                    logger.info(f"Sandbox: 使用同步函数 '{fname}' 作为 crawl() 替代")
                    break

        if not crawl_fn:
            return {
                "output": [],
                "error": "代码中未找到 'crawl(url, config)' 函数，也未找到任何可用的替代函数(main/run/scrape/fetch)",
                "pages_crawled": 0,
                "duration_ms": int((time.monotonic() - start) * 1000),
            }

        config = {
            "max_pages": settings.sandbox_max_pages,
            "delay": settings.default_delay,
        }

        # 注入预渲染HTML到config (推荐方式，代码通过 config.get("pre_rendered_html") 获取)
        if html:
            config["pre_rendered_html"] = html

        # 注入浏览器翻页收集的 API 数据 (通过 config.get("api_data") 获取)
        if api_data:
            config["api_data"] = api_data

        # 注入代理配置
        if proxy_config and proxy_config.get("enabled"):
            from src.engine.proxy import ProxyManager
            pm = ProxyManager(proxy_config)
            proxy_url = pm.get_proxy()
            if proxy_url:
                config["proxy"] = proxy_url
        elif settings.default_proxy:
            config["proxy"] = settings.default_proxy

        result = await asyncio.wait_for(
            crawl_fn(target_url, config),
            timeout=timeout,
        )

        if not isinstance(result, list):
            result = [result] if result else []

        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "output": result,
            "error": "",
            "pages_crawled": 1,
            "duration_ms": duration_ms,
        }

    except asyncio.TimeoutError:
        return {
            "output": [],
            "error": f"执行超时 ({timeout}秒)",
            "pages_crawled": 0,
            "duration_ms": timeout * 1000,
        }
    except ImportError as e:
        # 沙箱import拦截
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "output": [],
            "error": f"沙箱安全限制: {e}",
            "pages_crawled": 0,
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "output": [],
            "error": f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
            "pages_crawled": 0,
            "duration_ms": duration_ms,
        }
    finally:
        sys.stdout = old_stdout


def _static_security_check(code: str) -> str | None:
    """静态代码安全检查 — 在exec之前拦截明显危险模式"""
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # 语法错误让exec自己报

    for node in ast.walk(tree):
        # 检查直接的 import os / import subprocess 等
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _BLOCKED_MODULES:
                    return f"禁止导入模块: {alias.name}"

        # 检查 from os import ... / from subprocess import ...
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in _BLOCKED_MODULES:
                return f"禁止导入模块: {node.module}"

        # 检查 eval()/exec()/compile() 调用
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("eval", "exec", "compile", "__import__"):
                return f"禁止调用: {func.id}()"
            # 检查 os.system() / os.popen() 等
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "os":
                    return f"禁止调用: os.{func.attr}()"

    return None
