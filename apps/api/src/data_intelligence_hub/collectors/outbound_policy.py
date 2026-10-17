"""Server-owned execution policy; request parameters never grant network access."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.core.config import get_settings

POLICY_VERSION = "outbound.v1"
ExecutionKind = Literal["offline", "guarded_http", "provider_api", "unsupported"]

OFFLINE_COLLECTORS = frozenset({"manual_json"})
GUARDED_HTTP_COLLECTORS = frozenset(
    {
        "generic_web",
        "public_feed",
        "ecommerce_product_page",
        "ecommerce_product_discovery",
    }
)
PROVIDER_API_COLLECTORS = frozenset(
    {
        "github_repo",
        "github_topic",
        "apify_actor",
        "tikhub_social",
        "anysearch",
        "exa_search",
        "exa_find_similar",
        "exa_contents",
        "exa_answer",
        "hackernews_front_page",
        "hackernews_search",
        "hackernews_user",
        "npm_package",
        "npm_search",
        "pypi_package",
        "pypi_search",
        "crates_package",
        "crates_search",
        "rubygems_package",
        "rubygems_search",
        "go_package",
        "go_search",
        "packagist_package",
        "packagist_search",
        "nuget_package",
        "nuget_search",
        "pubdev_package",
        "pubdev_search",
    }
)
# These implementations delegate networking to an uncontrolled process, sidecar,
# browser, proxy, or configurable upstream. No request flag unlocks them.
UNSUPPORTED_COLLECTORS = frozenset(
    {
        "sherlock",
        "maigret",
        "playwright_browser",
        "browser_use_task",
        "aliens_eye_basic",
        "aliens_eye_advanced",
        "aliens_eye_correlate",
        "aliens_eye_recurse",
        "aliens_eye_domain",
        "aliens_eye_batch",
        "aliens_eye_selfcheck",
        "blackbird_email_osint",
        "blackbird_username_osint",
        "spiderfoot_domain_osint",
        "spiderfoot_ip_osint",
        "spiderfoot_email_osint",
        "spiderfoot_subdomain_enum",
        "spiderfoot_threat_intel",
        "spiderfoot_breach_check",
        "spiderfoot_cert_transparency",
        "spiderfoot_dark_web",
        "spiderfoot_attack_surface",
        "robin_darkweb_search",
        "robin_darkweb_username",
        "robin_darkweb_email",
        "autoscraper_enhanced_web",
        "tech_stack_detect",
        "anydoc_file_to_markdown",
        "twscrape_search",
        "twscrape_user_tweets",
        "twscrape_trends",
        "firecrawl_crawl",
        "firecrawl_extract",
        "firecrawl_batch_scrape",
        "jina_reader",
        "bestblogs_articles",
        "devto_articles",
        "juejin_articles",
        "substack_posts",
        "baidu_search",
        "bing_search",
        "duckduckgo_search",
        "bilibili_video_search",
        "bilibili_user_videos",
        "bilibili_video_comments",
        "weibo_keyword_search",
        "weibo_user_posts",
        "weibo_trending_topics",
        "zhihu_question_answers",
        "zhihu_keyword_search",
        "zhihu_hot_list",
        "kuaishou_video_search",
        "kuaishou_user_videos",
    }
)


class CollectionPolicyDenied(CollectorError):
    def __init__(self, reason: str, *, code: str = "collection_policy_denied") -> None:
        self.code = code
        self.reason = reason
        super().__init__(f"{code}: {reason}")


@dataclass(frozen=True)
class HttpGrant:
    collector_type: str
    hosts: frozenset[str]
    expires_at: datetime
    max_requests: int
    max_domains: int
    timeout_seconds: float


def execution_kind(collector_type: str) -> ExecutionKind:
    if collector_type in OFFLINE_COLLECTORS:
        return "offline"
    if collector_type in GUARDED_HTTP_COLLECTORS:
        return "guarded_http"
    if collector_type in PROVIDER_API_COLLECTORS:
        return "provider_api"
    return "unsupported"


def canonical_host(value: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("invalid host")
    try:
        host = httpx.URL(scheme="https", host=value.rstrip(".").lower()).raw_host.decode("ascii")
    except (httpx.InvalidURL, UnicodeError) as exc:
        raise ValueError("invalid host") from exc
    if len(host) > 253 or "." not in host:
        raise ValueError("host must be an exact public hostname")
    if any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in host.split(".")
    ):
        raise ValueError("invalid host label")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses cannot be approved as hostnames")
    if host.endswith((".localhost", ".local", ".onion")):
        raise ValueError("host is not an approved public hostname")
    return host


def http_grant(collector_type: str) -> HttpGrant:
    grants = get_settings().collection_http_grants
    matches = [g for g in grants if g.get("collector_type") == collector_type]
    if len(matches) != 1:
        raise CollectionPolicyDenied("缺少唯一的服务端域名批准配置")
    raw = matches[0]
    try:
        hosts_value = raw["hosts"]
        if not isinstance(hosts_value, list) or not 1 <= len(hosts_value) <= 5:
            raise ValueError
        hosts = frozenset(canonical_host(h) for h in hosts_value)
        expires_at = datetime.fromisoformat(raw["expires_at"].replace("Z", "+00:00"))
        requests = raw.get("max_requests", 50)
        domains = raw.get("max_domains", 5)
        timeout = raw.get("timeout_seconds", 60)
        if type(requests) is not int or not 1 <= requests <= 50:
            raise ValueError
        if type(domains) is not int or not 1 <= domains <= 5 or len(hosts) > domains:
            raise ValueError
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            raise ValueError
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            raise ValueError
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise CollectionPolicyDenied("服务端域名批准无效或已过期") from exc
    return HttpGrant(collector_type, hosts, expires_at, requests, domains, float(timeout))


def assert_collector_allowed(collector_type: str) -> None:
    kind = execution_kind(collector_type)
    if kind == "offline":
        return
    if kind == "unsupported":
        raise CollectionPolicyDenied(f"{collector_type} 未具备受控出口，禁止执行")
    if get_settings().effective_collection_network_mode == "offline":
        raise CollectionPolicyDenied("当前执行环境为离线模式")
    if kind == "guarded_http":
        http_grant(collector_type)


def policy_block_reason(collector_type: str) -> str | None:
    try:
        assert_collector_allowed(collector_type)
    except CollectionPolicyDenied as exc:
        return str(exc)
    return None


def host_block_reason(collector_type: str, url: str | None) -> str | None:
    """判断一个固定目标 URL 是否在批准范围内。

    类型级检查只回答「这个 collector 有没有有效批准」。
    受控 HTTP 采集器还要逐主机匹配；不匹配时请求会在发出前被拒，
    错误码是 ``outbound_domain_denied``。

    目录投影若只用类型级结论，会把未批准的主机显示成可用，
    用户点采集才失败。本函数让目录给出与执行一致的结论。

    ``url`` 为空表示目标由调用方传入，无法预先判定，按类型级结论处理。
    """
    reason = policy_block_reason(collector_type)
    if reason is not None:
        return reason

    if url is None or execution_kind(collector_type) != "guarded_http":
        return None

    try:
        host = canonical_host(httpx.URL(url).host or "")
    except (ValueError, UnicodeError, httpx.InvalidURL):
        return "outbound_domain_denied: 目标地址不符合批准范围"

    try:
        grant = http_grant(collector_type)
    except CollectionPolicyDenied as exc:
        return str(exc)

    if host not in grant.hosts:
        return f"outbound_domain_denied: 目标主机未获批准：{host}"
    return None


def is_policy_failure(message: str | None) -> bool:
    return bool(
        message
        and message.startswith(
            (
                "collection_policy_denied:",
                "outbound_domain_denied:",
                "outbound_budget_exceeded:",
            )
        )
    )
