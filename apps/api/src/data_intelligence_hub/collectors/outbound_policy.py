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


GRANT_HOSTS_MIN = 1
GRANT_HOSTS_MAX = 5
GRANT_MAX_REQUESTS = 50
GRANT_MAX_DOMAINS = 5
GRANT_MAX_TIMEOUT_SECONDS = 60

_GUARDED_HTTP_NAMES = "、".join(sorted(GUARDED_HTTP_COLLECTORS))


def _grant_host_issue(item_index: int, host_index: int, value: object) -> str | None:
    """返回一个主机名的问题说明。主机名可用时返回 None。"""
    field = f"collection_http_grants[{item_index}].hosts[{host_index}]"
    if not isinstance(value, str):
        return f"{field}：必须是字符串形式的域名"
    candidate = value.strip().rstrip(".")
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        pass
    else:
        return f"{field}：不得是 IP 地址，必须填写公网域名"
    if candidate.lower().endswith((".localhost", ".local", ".onion")):
        return f"{field}：不得以 .localhost / .local / .onion 结尾"
    try:
        canonical_host(value)
    except ValueError:
        return f"{field}：必须是精确的公开主机名，不得含协议、路径、端口或通配符"
    return None


def _grant_expires_issue(item_index: int, value: object) -> str | None:
    """返回 expires_at 的问题说明。时间可用时返回 None。"""
    field = f"collection_http_grants[{item_index}].expires_at"
    if not isinstance(value, str):
        return f"{field}：必须是 ISO-8601 时间字符串，例如 2027-01-01T00:00:00Z"
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"{field}：必须是可解析的 ISO-8601 时间字符串，例如 2027-01-01T00:00:00Z"
    if expires_at.tzinfo is None:
        return f"{field}：必须带时区，例如以 Z 结尾"
    if expires_at <= datetime.now(UTC):
        return f"{field}：已经过期，必须填写未来时间"
    return None


def _grant_budget_issues(
    item_index: int,
    raw: dict[str, object],
    host_count: int | None,
) -> list[str]:
    """校验可选的预算字段。缺省值由 http_grant 提供。"""
    prefix = f"collection_http_grants[{item_index}]"
    issues: list[str] = []
    if "max_requests" in raw:
        value = raw["max_requests"]
        if type(value) is not int or not 1 <= value <= GRANT_MAX_REQUESTS:
            issues.append(f"{prefix}.max_requests：必须是 1 到 50 的整数")
    if "max_domains" in raw:
        value = raw["max_domains"]
        if type(value) is not int or not 1 <= value <= GRANT_MAX_DOMAINS:
            issues.append(f"{prefix}.max_domains：必须是 1 到 5 的整数")
        elif host_count is not None and host_count > value:
            issues.append(
                f"{prefix}.max_domains：必须不小于 hosts 的数量（当前 {host_count}）"
            )
    if "timeout_seconds" in raw:
        value = raw["timeout_seconds"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < value <= GRANT_MAX_TIMEOUT_SECONDS
        ):
            issues.append(
                f"{prefix}.timeout_seconds：必须是 0 到 60 之间的数字（不含 0）"
            )
    return issues


def validate_collection_http_grants(grants: object) -> list[str]:
    """校验完整的 collection_http_grants 数组。

    返回中文问题列表。空列表表示全部通过。
    本函数不抛异常，也不读取全局设置。启动时调用它，只记录日志。
    这里比较宽松：运行时仍由 http_grant 复核并拒绝无效配置。
    """
    if not isinstance(grants, list):
        return ["collection_http_grants：必须是 JSON 数组"]

    issues: list[str] = []
    seen: dict[str, int] = {}
    for item_index, raw in enumerate(grants):
        prefix = f"collection_http_grants[{item_index}]"
        if not isinstance(raw, dict):
            issues.append(f"{prefix}：必须是 JSON 对象")
            continue

        if "collector_type" not in raw:
            issues.append(f"{prefix}.collector_type：缺少必填字段")
        else:
            collector_type = raw["collector_type"]
            if (
                not isinstance(collector_type, str)
                or collector_type not in GUARDED_HTTP_COLLECTORS
            ):
                issues.append(
                    f"{prefix}.collector_type：必须是受控 HTTP 采集器之一："
                    f"{_GUARDED_HTTP_NAMES}"
                )
            elif collector_type in seen:
                issues.append(
                    f"{prefix}.collector_type：{collector_type} 与第 "
                    f"{seen[collector_type]} 项重复；同一 collector_type 只能出现一次，"
                    "否则运行时拒绝并报「缺少唯一的服务端域名批准配置」"
                )
            else:
                seen[collector_type] = item_index

        host_count: int | None = None
        if "hosts" not in raw:
            issues.append(f"{prefix}.hosts：缺少必填字段")
        else:
            hosts_value = raw["hosts"]
            if not isinstance(hosts_value, list):
                issues.append(f"{prefix}.hosts：必须是数组")
            elif not GRANT_HOSTS_MIN <= len(hosts_value) <= GRANT_HOSTS_MAX:
                issues.append(
                    f"{prefix}.hosts：必须包含 1 到 5 个主机名，"
                    f"当前 {len(hosts_value)} 个"
                )
            else:
                canonical_hosts: set[str] = set()
                hosts_valid = True
                for host_index, value in enumerate(hosts_value):
                    host_issue = _grant_host_issue(item_index, host_index, value)
                    if host_issue is not None:
                        issues.append(host_issue)
                        hosts_valid = False
                        continue
                    assert isinstance(value, str)
                    canonical_hosts.add(canonical_host(value))
                if hosts_valid:
                    host_count = len(canonical_hosts)

        if "expires_at" not in raw:
            issues.append(f"{prefix}.expires_at：缺少必填字段")
        else:
            expires_issue = _grant_expires_issue(item_index, raw["expires_at"])
            if expires_issue is not None:
                issues.append(expires_issue)

        issues.extend(_grant_budget_issues(item_index, raw, host_count))
    return issues


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
