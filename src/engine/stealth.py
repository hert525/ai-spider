"""Anti-detection stealth measures for Playwright browser."""
from __future__ import annotations

import random
from loguru import logger

# User-Agent池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
]

# 屏幕分辨率池
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 2560, "height": 1440},
    {"width": 1280, "height": 720},
]

# 语言池
LOCALES = ["zh-CN", "en-US", "zh-TW", "ja-JP"]

# 时区池
TIMEZONES = ["Asia/Shanghai", "America/New_York", "Europe/London", "Asia/Tokyo"]


async def apply_stealth(context_or_page, level: str = "medium"):
    """Apply anti-detection stealth to a Playwright context or page.

    Levels:
    - basic: 只注入基本的navigator覆盖
    - medium: basic + WebGL/Canvas指纹随机化
    - full: medium + WebRTC禁用 + 更多
    """
    page = context_or_page

    # 基础stealth脚本 — 覆盖常见检测点
    stealth_js = """
    () => {
        // 1. 覆盖webdriver标志
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // 2. 覆盖chrome对象
        window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };

        // 3. 覆盖permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );

        // 4. 覆盖plugins（模拟真实浏览器）
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' },
            ],
        });

        // 5. 覆盖languages
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

        // 6. 覆盖platform
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

        // 7. 隐藏自动化相关属性
        delete navigator.__proto__.webdriver;
    }
    """

    await page.add_init_script(stealth_js)

    if level in ("medium", "full"):
        # Canvas指纹随机化
        canvas_js = """
        () => {
            const toBlob = HTMLCanvasElement.prototype.toBlob;
            const toDataURL = HTMLCanvasElement.prototype.toDataURL;
            const getImageData = CanvasRenderingContext2D.prototype.getImageData;

            // 给canvas添加微小噪声
            const noisify = function(canvas, context) {
                const shift = { r: Math.floor(Math.random() * 10) - 5,
                               g: Math.floor(Math.random() * 10) - 5,
                               b: Math.floor(Math.random() * 10) - 5 };
                const width = canvas.width, height = canvas.height;
                if (width === 0 || height === 0) return;
                const imageData = getImageData.apply(context, [0, 0, width, height]);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += shift.r;
                    imageData.data[i+1] += shift.g;
                    imageData.data[i+2] += shift.b;
                }
                context.putImageData(imageData, 0, 0);
            };

            HTMLCanvasElement.prototype.toDataURL = function() {
                const context = this.getContext('2d');
                if (context) noisify(this, context);
                return toDataURL.apply(this, arguments);
            };

            HTMLCanvasElement.prototype.toBlob = function() {
                const context = this.getContext('2d');
                if (context) noisify(this, context);
                return toBlob.apply(this, arguments);
            };
        }
        """
        await page.add_init_script(canvas_js)

    if level == "full":
        # 禁用WebRTC（防止IP泄露）
        webrtc_js = """
        () => {
            // 禁用WebRTC
            if (typeof RTCPeerConnection !== 'undefined') {
                RTCPeerConnection = undefined;
            }
            if (typeof webkitRTCPeerConnection !== 'undefined') {
                webkitRTCPeerConnection = undefined;
            }
        }
        """
        await page.add_init_script(webrtc_js)

    logger.debug(f"Stealth applied (level={level})")


def get_stealth_context_options(level: str = "medium") -> dict:
    """Get randomized browser context options for stealth."""
    ua = random.choice(USER_AGENTS)
    viewport = random.choice(VIEWPORTS)
    locale = random.choice(LOCALES[:2])  # 主要用中英文
    timezone = random.choice(TIMEZONES[:2])  # 主要用中美时区

    opts = {
        "user_agent": ua,
        "viewport": viewport,
        "locale": locale,
        "timezone_id": timezone,
        "color_scheme": random.choice(["light", "dark"]),
        "java_script_enabled": True,
        "ignore_https_errors": True,
    }

    if level == "full":
        opts["permissions"] = []  # 不授予任何权限

    return opts
