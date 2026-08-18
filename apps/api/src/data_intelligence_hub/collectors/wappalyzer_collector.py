"""Tech-stack detection collector.

Uses a built-in fingerprint ruleset (no external Wappalyzer package required)
to detect frameworks, CMS, CDN, analytics, and other technologies from a
page's HTML, HTTP headers, and script URLs.

Environment variables:
    HTTP_PROXY   Forwarded to httpx (optional)
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
    require_text,
)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# Lightweight fingerprint ruleset
# Each rule: (tech_name, category, match_type, pattern)
#   match_type: "html" | "script" | "header:<name>" | "meta:<name>" | "cookie:<name>"
# ---------------------------------------------------------------------------
_RULES: list[tuple[str, str, str, str]] = [
    # JavaScript frameworks
    ("React", "JavaScript Framework", "html", r'react(?:\.min)?\.js|__reactFiber|__reactProps'),
    ("Vue.js", "JavaScript Framework", "html", r'vue(?:\.min)?\.js|__vue__|Vue\.version'),
    ("Angular", "JavaScript Framework", "html", r'ng-version=|angular(?:\.min)?\.js'),
    ("Next.js", "JavaScript Framework", "html", r'__NEXT_DATA__|/_next/static/'),
    ("Nuxt.js", "JavaScript Framework", "html", r'__nuxt__|/_nuxt/'),
    ("Svelte", "JavaScript Framework", "html", r'__svelte__|svelte-'),
    ("Ember.js", "JavaScript Framework", "html", r'ember(?:\.min)?\.js|Ember\.VERSION'),
    ("Backbone.js", "JavaScript Framework", "html", r'backbone(?:\.min)?\.js'),
    ("jQuery", "JavaScript Library", "html", r'jquery(?:\.min)?\.js|jQuery\.fn\.jquery'),
    ("Alpine.js", "JavaScript Framework", "html", r'x-data=|alpinejs'),
    # CSS frameworks
    ("Bootstrap", "UI Framework", "html",
     r'bootstrap(?:\.min)?\.css|class="[^"]*(?:btn-|col-|navbar)'),
    ("Tailwind CSS", "UI Framework", "html",
     r'tailwind(?:\.min)?\.css|class="[^"]*(?:flex |grid |text-[a-z])'),
    ("Bulma", "UI Framework", "html", r'bulma(?:\.min)?\.css'),
    ("Foundation", "UI Framework", "html", r'foundation(?:\.min)?\.css'),
    # CMS
    ("WordPress", "CMS", "html", r'/wp-content/|/wp-includes/|wp-json'),
    ("Drupal", "CMS", "html", r'Drupal\.settings|drupal\.js|/sites/default/files/'),
    ("Joomla", "CMS", "html", r'/components/com_|Joomla!'),
    ("Ghost", "CMS", "html", r'content="Ghost '),
    ("Shopify", "E-commerce", "html", r'cdn\.shopify\.com|Shopify\.theme'),
    ("WooCommerce", "E-commerce", "html", r'woocommerce|wc-'),
    ("Magento", "E-commerce", "html", r'Mage\.Cookies|skin/frontend/'),
    ("PrestaShop", "E-commerce", "html", r'prestashop|presta-'),
    # Analytics
    ("Google Analytics", "Analytics", "html", r'google-analytics\.com/analytics|gtag\(|_gaq\.push'),
    ("Google Tag Manager", "Tag Manager", "html", r'googletagmanager\.com/gtm\.js'),
    ("Hotjar", "Analytics", "html", r'hotjar\.com/c/hotjar-'),
    ("Mixpanel", "Analytics", "html", r'mixpanel\.com/site_media|mixpanel\.track'),
    ("Segment", "Analytics", "html", r'cdn\.segment\.com|analytics\.load\('),
    ("Plausible", "Analytics", "html", r'plausible\.io/js/'),
    ("Fathom", "Analytics", "html", r'usefathom\.com/script'),
    # CDN / Hosting
    ("Cloudflare", "CDN", "header:server", r'cloudflare'),
    ("Cloudflare", "CDN", "header:cf-ray", r'.+'),
    ("Fastly", "CDN", "header:x-served-by", r'cache-'),
    ("AWS CloudFront", "CDN", "header:x-amz-cf-id", r'.+'),
    ("Vercel", "Hosting", "header:x-vercel-id", r'.+'),
    ("Netlify", "Hosting", "header:x-nf-request-id", r'.+'),
    ("GitHub Pages", "Hosting", "header:server", r'GitHub\.com'),
    # Web servers
    ("Nginx", "Web Server", "header:server", r'nginx'),
    ("Apache", "Web Server", "header:server", r'apache'),
    ("Caddy", "Web Server", "header:server", r'caddy'),
    ("LiteSpeed", "Web Server", "header:server", r'litespeed'),
    # Backend frameworks
    ("Laravel", "Web Framework", "html", r'laravel_session|/vendor/laravel'),
    ("Django", "Web Framework", "html", r'csrfmiddlewaretoken|django'),
    ("Ruby on Rails", "Web Framework", "html", r'csrf-token.*rails|action_dispatch'),
    ("ASP.NET", "Web Framework", "header:x-aspnet-version", r'.+'),
    ("ASP.NET", "Web Framework", "html", r'__VIEWSTATE|aspnetForm'),
    ("Express", "Web Framework", "header:x-powered-by", r'express'),
    ("Spring", "Web Framework", "header:x-application-context", r'.+'),
    # Font / icons
    ("Font Awesome", "Font", "html", r'font-awesome|fontawesome'),
    ("Google Fonts", "Font", "html", r'fonts\.googleapis\.com'),
    # Misc
    ("Intercom", "Customer Support", "html", r'intercom-frame|intercom\.io/frame'),
    ("Zendesk", "Customer Support", "html", r'zopim\.com|zendesk\.com/embeddable'),
    ("HubSpot", "CRM", "html", r'hubspot\.com/|hs-scripts\.com'),
    ("Stripe", "Payment", "html", r'js\.stripe\.com'),
    ("PayPal", "Payment", "html", r'paypal\.com/sdk|paypalobjects\.com'),
    ("reCAPTCHA", "Security", "html", r'google\.com/recaptcha|recaptcha/api\.js'),
    ("Cloudflare Turnstile", "Security", "html", r'challenges\.cloudflare\.com/turnstile'),
]


def _get_proxy() -> str | None:
    import os
    return os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_TIMEOUT,
        proxy=_get_proxy(),
        headers={"User-Agent": _UA},
        follow_redirects=True,
    )


def _detect(html: str, headers: dict[str, str]) -> list[dict[str, str]]:
    html_lower = html.lower()
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}
    detected: dict[str, dict[str, str]] = {}

    for tech, category, match_type, pattern in _RULES:
        if tech in detected:
            continue
        matched = False
        if match_type in ("html", "script"):
            matched = bool(re.search(pattern, html_lower, re.I))
        elif match_type.startswith("header:"):
            header_name = match_type[7:]
            value = headers_lower.get(header_name, "")
            matched = bool(re.search(pattern, value, re.I))
        elif match_type.startswith("meta:"):
            matched = bool(re.search(
                rf'<meta[^>]+name=["\']?{re.escape(match_type[5:])}["\']?[^>]+'
                rf'content=["\']?[^"\']*{pattern}',
                html_lower, re.I,
            ))
        elif match_type.startswith("cookie:"):
            cookie_val = headers_lower.get("set-cookie", "")
            matched = bool(re.search(
                rf'{re.escape(match_type[7:])}=[^;]*{pattern}',
                cookie_val, re.I,
            ))
        if matched:
            detected[tech] = {"name": tech, "category": category}

    return sorted(detected.values(), key=lambda x: x["category"])


class TechStackDetectCollector(BaseCollector):
    """Detect the technology stack of a given URL using HTML/header fingerprinting."""

    collector_type = "tech_stack_detect"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            from data_intelligence_hub.collectors.base import CollectorError
            raise CollectorError("url must start with http:// or https://")
        return {"url": url}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok", message="TechStackDetect collector ready (httpx + built-in rules)",
            logs=[collector_log("tech_stack_test_ok", "ready")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)
        url = config["url"]

        try:
            async with _client() as c:
                r = await c.get(url)
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("tech_stack_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        technologies = _detect(r.text, dict(r.headers))
        categories: dict[str, list[str]] = {}
        for t in technologies:
            categories.setdefault(t["category"], []).append(t["name"])

        record = CollectorRawRecord(
            record_type="web_page",
            source_url=url,
            content={
                "url": url,
                "final_url": str(r.url),
                "status_code": r.status_code,
                "technologies": technologies,
                "categories": categories,
                "tech_count": len(technologies),
                "server": r.headers.get("server", ""),
                "x_powered_by": r.headers.get("x-powered-by", ""),
            },
            collected_at=collected_at,
        )
        logs.append(
            collector_log(
                "tech_stack_detected",
                f"url={url!r} technologies={len(technologies)}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
