from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from data_intelligence_hub.collectors import generic_web as generic_web_module
from data_intelligence_hub.collectors.base import HTTP_HEADERS, HTTP_TIMEOUT_SECONDS, CollectorError
from data_intelligence_hub.schemas.toolkit import (
    ToolkitPreflightAuthorizationGateResponse,
    ToolkitPreflightDomResponse,
    ToolkitPreflightHttpResourceResponse,
    ToolkitPreflightNetworkResponse,
    ToolkitPreflightRedirectResponse,
    ToolkitPreflightReportResponse,
    ToolkitPreflightRequest,
)

MAX_REDIRECTS = 3
MAX_HTML_BYTES = 300_000
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
HEADER_ALLOWLIST = {
    "cache-control",
    "content-security-policy",
    "content-type",
    "etag",
    "last-modified",
    "permissions-policy",
    "referrer-policy",
    "server",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "x-robots-tag",
}


async def run_toolkit_preflight(
    payload: ToolkitPreflightRequest,
    http_client: httpx.AsyncClient | None = None,
) -> ToolkitPreflightReportResponse:
    requested_url = payload.url.strip()
    if not payload.authorized:
        raise CollectorError("preflight_authorization_required")
    if len(requested_url) > 2_048:
        raise CollectorError("url_too_long")
    await generic_web_module._assert_public_http_url(requested_url)

    if http_client is not None:
        return await _run_preflight_with_client(payload, requested_url, http_client)

    async with httpx.AsyncClient() as client:
        return await _run_preflight_with_client(payload, requested_url, client)


async def _run_preflight_with_client(
    payload: ToolkitPreflightRequest,
    requested_url: str,
    client: httpx.AsyncClient,
) -> ToolkitPreflightReportResponse:
    document = await _fetch_with_redirects(client, requested_url)
    origin = _origin(document.final_url)
    robots = await _fetch_resource(client, urljoin(origin, "/robots.txt"), "robots.txt")
    sitemap = await _fetch_resource(client, urljoin(origin, "/sitemap.xml"), "sitemap.xml")
    security_txt = await _fetch_resource(
        client,
        urljoin(origin, "/.well-known/security.txt"),
        "security.txt",
    )
    dom = _inspect_dom(_decode_preview(document.response), document.final_url)
    network = _build_network(document=document, dom=dom)
    gate, recommendations = _assess_preflight(
        document=document,
        dom=dom,
        robots=robots,
        sitemap=sitemap,
        security_txt=security_txt,
    )
    return ToolkitPreflightReportResponse(
        requested_url=payload.url.strip(),
        final_url=document.final_url,
        checked_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        headers=_select_headers(document.response.headers),
        redirects=document.redirects,
        robots=robots,
        sitemap=sitemap,
        security_txt=security_txt,
        dom=dom.to_response(),
        network=network,
        authorization_gate=gate,
        recommendations=recommendations,
    )


@dataclass(frozen=True)
class _DocumentFetch:
    final_url: str
    response: httpx.Response
    redirects: list[ToolkitPreflightRedirectResponse]


async def _fetch_with_redirects(client: httpx.AsyncClient, url: str) -> _DocumentFetch:
    current_url = url
    redirects: list[ToolkitPreflightRedirectResponse] = []
    for _ in range(MAX_REDIRECTS + 1):
        await generic_web_module._assert_public_http_url(current_url)
        try:
            response = await client.get(
                current_url,
                headers=HTTP_HEADERS,
                follow_redirects=False,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise CollectorError("http_timeout: upstream did not respond") from exc
        except httpx.HTTPError as exc:
            raise CollectorError(f"http_request_failed: {exc.__class__.__name__}") from exc

        location = response.headers.get("location")
        if response.status_code not in REDIRECT_STATUS_CODES:
            return _DocumentFetch(
                final_url=str(response.url),
                response=response,
                redirects=redirects,
            )
        if len(redirects) >= MAX_REDIRECTS:
            raise CollectorError("http_redirect_limit_exceeded")
        next_url = urljoin(str(response.url), location or "")
        redirects.append(
            ToolkitPreflightRedirectResponse(
                url=str(response.url),
                status_code=response.status_code,
                location=next_url if location else None,
            )
        )
        current_url = next_url
    raise CollectorError("http_redirect_limit_exceeded")


async def _fetch_resource(
    client: httpx.AsyncClient,
    url: str,
    label: str,
) -> ToolkitPreflightHttpResourceResponse:
    try:
        result = await _fetch_with_redirects(client, url)
    except CollectorError as exc:
        return ToolkitPreflightHttpResourceResponse(
            url=url,
            status_code=None,
            content_type=None,
            content_length=None,
            available=False,
            summary=f"{label} 不可读取：{exc}",
        )
    response = result.response
    text = _decode_preview(response)
    return ToolkitPreflightHttpResourceResponse(
        url=result.final_url,
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        content_length=_content_length(response),
        available=200 <= response.status_code < 300,
        summary=_resource_summary(label, response.status_code, text),
    )


def _decode_preview(response: httpx.Response) -> str:
    encoding = response.encoding or "utf-8"
    return response.content[:MAX_HTML_BYTES].decode(encoding, errors="replace")


def _resource_summary(label: str, status_code: int, text: str) -> str:
    if not (200 <= status_code < 300):
        return f"{label} 返回 {status_code}，需要人工复核是否存在公开声明。"
    if label == "robots.txt":
        if _robots_global_disallow(text):
            return "robots.txt 对 User-agent: * 声明 Disallow: /，不应进入自动采集。"
        if "sitemap:" in text.lower():
            return "robots.txt 可读取，并提供 sitemap 线索。"
        return "robots.txt 可读取，未发现全站禁止规则。"
    if label == "sitemap.xml":
        return "sitemap.xml 可读取，可作为公开 URL 发现入口。"
    return "security.txt 可读取，可作为安全联系与授权边界线索。"


@dataclass(frozen=True)
class _DomInspection:
    title: str | None
    description: str | None
    canonical_url: str | None
    meta_robots: str | None
    headings: list[str]
    link_urls: list[str]
    script_count: int
    stylesheet_count: int
    image_count: int
    form_count: int
    text_sample: str
    same_origin_links: int
    external_links: int

    def to_response(self) -> ToolkitPreflightDomResponse:
        return ToolkitPreflightDomResponse(
            title=self.title,
            description=self.description,
            canonical_url=self.canonical_url,
            meta_robots=self.meta_robots,
            headings=self.headings,
            link_count=len(self.link_urls),
            script_count=self.script_count,
            stylesheet_count=self.stylesheet_count,
            image_count=self.image_count,
            form_count=self.form_count,
            text_sample=self.text_sample,
        )


class _DomInspector(HTMLParser):
    def __init__(self, final_url: str) -> None:
        super().__init__()
        self.final_url = final_url
        self.title_parts: list[str] = []
        self.description: str | None = None
        self.canonical_url: str | None = None
        self.meta_robots: str | None = None
        self.heading_parts: list[str] = []
        self.headings: list[str] = []
        self.link_urls: list[str] = []
        self.script_count = 0
        self.stylesheet_count = 0
        self.image_count = 0
        self.form_count = 0
        self.text_parts: list[str] = []
        self._in_title = False
        self._heading_tag: str | None = None
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attrs_by_name = {name.lower(): value or "" for name, value in attrs}
        if tag_name in {"script", "style", "noscript"}:
            self._ignore_depth += 1
        if tag_name == "title":
            self._in_title = True
        if tag_name in {"h1", "h2", "h3"}:
            self._heading_tag = tag_name
            self.heading_parts = []
        if tag_name == "meta":
            name = attrs_by_name.get("name", "").lower()
            content = attrs_by_name.get("content", "").strip()
            if name == "description" and content:
                self.description = content[:240]
            if name == "robots" and content:
                self.meta_robots = content[:240]
        if tag_name == "a":
            href = attrs_by_name.get("href", "").strip()
            if href:
                self.link_urls.append(urljoin(self.final_url, href))
        if tag_name == "link":
            rel = attrs_by_name.get("rel", "").lower()
            href = attrs_by_name.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonical_url = urljoin(self.final_url, href)
            if "stylesheet" in rel:
                self.stylesheet_count += 1
        if tag_name == "script":
            self.script_count += 1
        if tag_name == "img":
            self.image_count += 1
        if tag_name == "form":
            self.form_count += 1

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript"} and self._ignore_depth > 0:
            self._ignore_depth -= 1
        if tag_name == "title":
            self._in_title = False
        if self._heading_tag == tag_name:
            heading = " ".join(self.heading_parts).strip()
            if heading:
                self.headings.append(heading[:140])
            self._heading_tag = None
            self.heading_parts = []

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if normalized == "":
            return
        if self._in_title:
            self.title_parts.append(normalized)
        if self._heading_tag is not None:
            self.heading_parts.append(normalized)
        if self._ignore_depth == 0:
            self.text_parts.append(normalized)


def _inspect_dom(html: str, final_url: str) -> _DomInspection:
    inspector = _DomInspector(final_url)
    inspector.feed(html)
    final_origin = _origin(final_url)
    same_origin = 0
    external = 0
    for link_url in inspector.link_urls:
        if _origin(link_url) == final_origin:
            same_origin += 1
        else:
            external += 1
    return _DomInspection(
        title=" ".join(inspector.title_parts).strip()[:180] or None,
        description=inspector.description,
        canonical_url=inspector.canonical_url,
        meta_robots=inspector.meta_robots,
        headings=inspector.headings[:8],
        link_urls=inspector.link_urls,
        script_count=inspector.script_count,
        stylesheet_count=inspector.stylesheet_count,
        image_count=inspector.image_count,
        form_count=inspector.form_count,
        text_sample=" ".join(inspector.text_parts).strip()[:360],
        same_origin_links=same_origin,
        external_links=external,
    )


def _build_network(
    *,
    document: _DocumentFetch,
    dom: _DomInspection,
) -> ToolkitPreflightNetworkResponse:
    return ToolkitPreflightNetworkResponse(
        request_method="GET",
        final_status_code=document.response.status_code,
        final_content_type=document.response.headers.get("content-type"),
        redirect_count=len(document.redirects),
        same_origin_links=dom.same_origin_links,
        external_links=dom.external_links,
        script_count=dom.script_count,
        stylesheet_count=dom.stylesheet_count,
        image_count=dom.image_count,
        form_count=dom.form_count,
    )


def _assess_preflight(
    *,
    document: _DocumentFetch,
    dom: _DomInspection,
    robots: ToolkitPreflightHttpResourceResponse,
    sitemap: ToolkitPreflightHttpResourceResponse,
    security_txt: ToolkitPreflightHttpResourceResponse,
) -> tuple[ToolkitPreflightAuthorizationGateResponse, list[str]]:
    blocked: list[str] = []
    actions: list[str] = []
    recommendations: list[str] = []
    status_code = document.response.status_code
    content_type = (document.response.headers.get("content-type") or "").lower()

    if status_code in {401, 403}:
        blocked.append("主文档返回鉴权或禁止状态，不进入自动采集。")
    if robots.available and "Disallow: /" in robots.summary:
        blocked.append("robots.txt 对全站采集给出禁止信号。")
    if "html" not in content_type:
        actions.append("目标主响应不是 HTML；优先判断是否存在官方 API 或文件下载权限。")
    if dom.form_count > 0:
        actions.append("页面包含表单；确认是否涉及登录、账号态或个人信息。")
    if not robots.available:
        actions.append("robots.txt 不可读取；进入人工政策复核。")
    if not sitemap.available:
        actions.append("sitemap.xml 不可读取；不要假设存在完整公开 URL 清单。")
    if not security_txt.available:
        actions.append("security.txt 不可读取；授权联系路径需要人工确认。")
    if "content-security-policy" not in _select_headers(document.response.headers):
        recommendations.append("未发现 CSP 响应头，截图和脚本资源分析需要保留风险备注。")
    if document.redirects:
        recommendations.append("存在重定向链，采集记录必须保留 requested_url 与 final_url。")
    if dom.same_origin_links > 0:
        recommendations.append("可从同域链接中抽样建立 DOM 字段契约。")
    if dom.script_count > 10:
        recommendations.append("脚本资源较多，动态内容优先使用浏览器采集或官方 API 复核。")
    if robots.available:
        recommendations.append(robots.summary)
    if sitemap.available:
        recommendations.append(sitemap.summary)
    if security_txt.available:
        recommendations.append(security_txt.summary)

    risk_level = "high" if blocked else "medium" if actions else "low"
    if not actions and not blocked:
        actions.append("可进入低风险公开页面采集实验，但仍需限频、缓存和证据留存。")
    return (
        ToolkitPreflightAuthorizationGateResponse(
            allowed_to_continue=len(blocked) == 0,
            risk_level=risk_level,
            blocked_reasons=blocked,
            required_next_actions=actions,
        ),
        recommendations,
    )


def _select_headers(headers: httpx.Headers) -> dict[str, str]:
    selected: dict[str, str] = {}
    for key, value in headers.items():
        normalized = key.lower()
        if normalized in HEADER_ALLOWLIST:
            selected[normalized] = value[:500]
    return selected


def _content_length(response: httpx.Response) -> int | None:
    value = response.headers.get("content-length")
    if value is None:
        return len(response.content)
    try:
        return int(value)
    except ValueError:
        return len(response.content)


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _robots_global_disallow(text: str) -> bool:
    current_user_agent_all = False
    for raw_line in text.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if line == "":
            current_user_agent_all = False
            continue
        key, _, value = line.partition(":")
        normalized_key = key.strip().lower()
        normalized_value = value.strip().lower()
        if normalized_key == "user-agent":
            current_user_agent_all = normalized_value == "*"
        if current_user_agent_all and normalized_key == "disallow" and normalized_value == "/":
            return True
    return False
