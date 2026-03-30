"""Auto-detect pagination patterns from browser-rendered pages.

Runs inside Playwright after page load. Detects:
1. JS pagination functions (gotoPage, changePage, loadPage, etc.)
2. Paginated API endpoints (intercepted XHR/fetch with pageIndex, page, offset, etc.)
3. Pagination UI elements (next/prev buttons, page numbers)

Returns a pagination config dict compatible with _pre_render's pagination parameter.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class PaginationResult:
    """Detected pagination configuration."""
    detected: bool = False
    api_pattern: str = ""
    page_fn: str = ""
    page_size: int = 10
    total_key: str = ""
    data_key: str = ""
    confidence: float = 0.0
    method: str = ""  # "js_function", "api_intercept", "url_pattern"
    details: str = ""

    def to_config(self) -> dict | None:
        if not self.detected:
            return None
        cfg: dict = {}
        if self.api_pattern:
            cfg["api_pattern"] = self.api_pattern
        if self.page_fn:
            cfg["page_fn"] = self.page_fn
        if self.page_size:
            cfg["page_size"] = self.page_size
        if self.total_key:
            cfg["total_key"] = self.total_key
        if self.data_key:
            cfg["data_key"] = self.data_key
        return cfg


# JS code to detect pagination patterns in the browser
_DETECT_JS = """
() => {
    const result = {
        functions: [],
        paginationElements: [],
        apiHints: [],
    };
    
    // 1. Detect pagination-related global functions
    const pageFnPatterns = [
        'gotoPage', 'goToPage', 'changePage', 'loadPage', 'turnPage',
        'nextPage', 'prevPage', 'getPage', 'fetchPage', 'queryPage',
        'pageChange', 'onPageChange', 'handlePageChange',
        'loadMore', 'loadData', 'getData', 'fetchData', 'queryData',
    ];
    for (const name of pageFnPatterns) {
        if (typeof window[name] === 'function') {
            result.functions.push({
                name: name,
                source: window[name].toString().substring(0, 1000),
            });
        }
    }
    
    // 2. Detect pagination UI elements
    const selectors = [
        // Common pagination containers
        '.pagination', '.pager', '.page-nav', '.page-list',
        '[class*=pagination]', '[class*=pager]', '[class*=page-nav]',
        '.ant-pagination', '.el-pagination', '.layui-laypage',
        // Next/prev buttons
        'a[onclick*=page]', 'a[onclick*=Page]', 'button[onclick*=page]',
        'a:has-text("下一页")', 'a:has-text(">")', 'a:has-text("Next")',
    ];
    for (const sel of selectors) {
        try {
            const els = document.querySelectorAll(sel);
            if (els.length > 0) {
                const items = [];
                els.forEach(el => {
                    items.push({
                        tag: el.tagName,
                        text: el.textContent.trim().substring(0, 100),
                        onclick: el.getAttribute('onclick') || '',
                        href: el.getAttribute('href') || '',
                        className: el.className.substring(0, 100),
                    });
                });
                result.paginationElements.push({selector: sel, count: els.length, items: items.slice(0, 5)});
            }
        } catch(e) {}
    }
    
    // 3. Look for inline scripts with API URL patterns
    const scripts = document.querySelectorAll('script:not([src])');
    const apiPatterns = [
        /\\.ajax\\s*\\(\\s*\\{[^}]*url\\s*[:=]\\s*['"](.*?)['"]/g,
        /fetch\\s*\\(\\s*['"](.*?)['"]/g,
        /\\.get\\s*\\(\\s*['"](.*?)['"]/g,
        /\\.post\\s*\\(\\s*['"](.*?)['"]/g,
        /XMLHttpRequest.*\\.open\\s*\\(\\s*['"][A-Z]+['"]\\s*,\\s*['"](.*?)['"]/g,
    ];
    scripts.forEach(script => {
        const text = script.textContent;
        if (text.includes('page') || text.includes('Page') || text.includes('PAGE')) {
            for (const pattern of apiPatterns) {
                pattern.lastIndex = 0;
                let match;
                while ((match = pattern.exec(text)) !== null) {
                    if (match[1] && (match[1].includes('page') || match[1].includes('Page') || 
                        match[1].includes('data') || match[1].includes('report') ||
                        match[1].includes('list') || match[1].includes('query'))) {
                        result.apiHints.push(match[1]);
                    }
                }
            }
        }
    });
    
    // 4. Check for total count text
    const bodyText = document.body.innerText;
    const totalMatch = bodyText.match(/共\\s*(\\d+)\\s*[条项笔个件]/);
    if (totalMatch) {
        result.totalText = totalMatch[0];
        result.totalCount = parseInt(totalMatch[1]);
    }
    
    return result;
}
"""

# JS code to analyze a detected pagination function's source
_ANALYZE_FN_JS = """
(fnName) => {
    const fn = window[fnName];
    if (!fn) return null;
    
    const src = fn.toString();
    const result = {
        name: fnName,
        params: [],
        apiUrl: null,
        idParam: null,
    };
    
    // Extract parameter names
    const paramMatch = src.match(/function\\s*\\w*\\s*\\(([^)]*)\\)/);
    if (paramMatch) {
        result.params = paramMatch[1].split(',').map(p => p.trim()).filter(Boolean);
    }
    
    // Look for AJAX/fetch URL in function body
    const urlMatch = src.match(/url\\s*[:=]\\s*['"](.*?)['"]/) ||
                     src.match(/fetch\\s*\\(\\s*['"](.*?)['"]/) ||
                     src.match(/\\.get\\s*\\(\\s*['"](.*?)['"]/);
    if (urlMatch) {
        result.apiUrl = urlMatch[1];
    }
    
    // Look for the first string parameter (usually an ID like 'bdzq')
    const callMatch = src.match(/['"]([a-zA-Z_][a-zA-Z0-9_]*)['"]\\s*[,)]/);
    if (callMatch) {
        result.idParam = callMatch[1];
    }
    
    return result;
}
"""


async def detect_pagination(page) -> PaginationResult:
    """Detect pagination patterns on a Playwright page.
    
    Should be called after page has fully loaded (JS challenge passed, 
    initial data rendered).
    
    Args:
        page: Playwright Page object
        
    Returns:
        PaginationResult with detected config
    """
    result = PaginationResult()
    
    try:
        detection = await page.evaluate(_DETECT_JS)
    except Exception as e:
        logger.warning(f"Pagination detection JS failed: {e}")
        return result
    
    if not detection:
        return result
    
    functions = detection.get("functions", [])
    pagination_els = detection.get("paginationElements", [])
    api_hints = detection.get("apiHints", [])
    total_count = detection.get("totalCount")
    
    # Strategy 1: onclick attributes on pagination elements (most reliable — has actual call args)
    if pagination_els:
        for pg in pagination_els:
            for item in pg.get("items", []):
                onclick = item.get("onclick", "")
                if onclick:
                    match = re.match(r"(\w+)\s*\(\s*(.+)\s*\)", onclick)
                    if match:
                        fn_name = match.group(1)
                        args_str = match.group(2)
                        args = [a.strip().strip("'\"") for a in args_str.split(",")]
                        
                        if len(args) >= 3:
                            result.page_fn = f"{fn_name}('{args[0]}', {{page}}, {{size}})"
                        elif len(args) == 2:
                            try:
                                int(args[1])
                                result.page_fn = f"{fn_name}('{args[0]}', {{page}}, {{size}})"
                            except ValueError:
                                result.page_fn = f"{fn_name}({{page}}, {{size}})"
                        else:
                            result.page_fn = f"{fn_name}({{page}})"
                        
                        result.method = "onclick_pattern"
                        result.confidence = 0.9
                        result.details = f"onclick: {onclick}"
                        break
            if result.page_fn:
                break

    # Strategy 2: Detected a JS pagination function (fallback — params may be unreliable)
    if not result.page_fn and functions:
        fn = functions[0]  # Take the first match
        fn_name = fn["name"]
        fn_source = fn["source"]
        
        logger.info(f"Pagination: detected JS function '{fn_name}'")
        
        # Analyze the function to extract call pattern
        try:
            analysis = await page.evaluate(_ANALYZE_FN_JS, fn_name)
        except Exception:
            analysis = None
        
        if analysis:
            params = analysis.get("params", [])
            api_url = analysis.get("apiUrl", "")
            id_param = analysis.get("idParam", "")
            
            # Build the page_fn call template
            # Common patterns:
            # gotoPage(id, pageIndex, pageSize) → gotoPage('bdzq', {page}, {size})
            # changePage(pageIndex) → changePage({page})
            # loadPage(page, size) → loadPage({page}, {size})
            
            if len(params) >= 3:
                # 3+ params: likely (id, page, size)
                first_arg = f"'{id_param}'" if id_param else f"'{params[0]}'"
                page_fn = f"{fn_name}({first_arg}, {{page}}, {{size}})"
            elif len(params) == 2:
                # 2 params: likely (page, size)
                page_fn = f"{fn_name}({{page}}, {{size}})"
            elif len(params) == 1:
                # 1 param: just page number
                page_fn = f"{fn_name}({{page}})"
            else:
                page_fn = f"{fn_name}({{page}})"
            
            result.page_fn = page_fn
            result.method = "js_function"
            result.confidence = 0.8
            result.details = f"Function: {fn_name}({', '.join(params)})"
            
            # Extract API pattern from function source or api_url
            if api_url:
                # Get the distinctive part of the API URL
                parts = api_url.strip("/").split("/")
                result.api_pattern = parts[-1] if parts else api_url
        else:
            # Fallback: just use function name with basic params
            result.page_fn = f"{fn_name}({{page}}, {{size}})"
            result.method = "js_function"
            result.confidence = 0.5
    
    # (Strategy 2 was onclick — now promoted to Strategy 1 above)
    
    # If we have a page_fn but no api_pattern, try to detect from intercepted responses
    # (This will be done separately when we have response interception)
    
    if result.page_fn:
        result.detected = True
        # Default page_size based on what we can see
        result.page_size = 500  # Use large pages for efficiency
        logger.info(
            f"Pagination detected ({result.method}, confidence={result.confidence:.1f}): "
            f"page_fn={result.page_fn}"
        )
    else:
        logger.info("No pagination pattern detected")
    
    return result


async def detect_api_structure(api_response_text: str) -> tuple[str, str, int]:
    """Analyze a JSON API response to find data array and total count keys.
    
    Returns (data_key, total_key, page_size) detected from the response structure.
    """
    try:
        data = json.loads(api_response_text)
    except (json.JSONDecodeError, TypeError):
        return "data", "totalCount", 10
    
    if not isinstance(data, dict):
        return "data", "totalCount", 10
    
    # Find the data array key
    data_key = "data"
    max_len = 0
    for key, value in data.items():
        if isinstance(value, list) and len(value) > max_len:
            data_key = key
            max_len = len(value)
    
    # Find the total count key
    total_key = ""
    total_patterns = ["totalCount", "total_count", "total", "count", "totalNum",
                      "total_num", "recordCount", "record_count", "totalRecords",
                      "totalElements", "totalItems"]
    for pattern in total_patterns:
        if pattern in data:
            val = data[pattern]
            if isinstance(val, (int, float)) and val > 0:
                total_key = pattern
                break
        # Case-insensitive fallback
        for key in data:
            if key.lower() == pattern.lower():
                val = data[key]
                if isinstance(val, (int, float)) and val > 0:
                    total_key = key
                    break
        if total_key:
            break
    
    # Detect page size from the data array length or explicit field
    page_size = max_len if max_len > 0 else 10
    for key in ("pageSize", "page_size", "size", "limit", "per_page", "perPage"):
        if key in data and isinstance(data[key], int):
            page_size = data[key]
            break
    
    return data_key, total_key, page_size
