from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = "browser_structure_diagnostic.v1"
MAX_SAMPLES = 12


def build_browser_structure_diagnostic(
    raw_snapshot: Mapping[str, Any],
    *,
    requested_url: str,
    authorized: bool,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    page = _as_mapping(raw_snapshot.get("page"))
    dom = _as_mapping(raw_snapshot.get("dom"))
    accessibility = _as_mapping(raw_snapshot.get("accessibility"))
    evidence = _as_mapping(raw_snapshot.get("evidence"))
    errors = _as_text_list(raw_snapshot.get("errors"))

    final_url = _text(page.get("url")) or _text(dom.get("final_url")) or requested_url
    counters = _build_dom_counters(dom)
    network_summary = _build_network_summary(
        _as_mapping_list(dom.get("resources")),
        final_url=final_url,
    )
    visible_text = _build_visible_text_summary(dom)
    interaction_summary = _build_interaction_summary(dom)
    accessibility_summary = _build_accessibility_summary(accessibility)
    risk_flags = _build_risk_flags(
        final_url=final_url,
        visible_text_sample=visible_text["sample"],
        counters=counters,
        network_summary=network_summary,
        errors=errors,
    )
    extraction_strategy = recommend_browser_extraction_strategy(
        counters=counters,
        visible_text_length=_as_int(visible_text["length"]),
        network_summary=network_summary,
        risk_flags=risk_flags,
        authorized=authorized,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "requested_url": requested_url,
        "final_url": final_url,
        "run_policy": {
            "authorization_confirmed": authorized,
            "execution_mode": "browser_harness_real_chrome_read_only",
            "production_write": False,
            "login_or_private_page_allowed": False,
            "cookies_exported": False,
            "note": (
                "脚本不读取或输出 cookie；真实 Chrome 访问公开 URL 时"
                "可能存在浏览器环境自带状态。"
            ),
        },
        "page": {
            "title": _text(page.get("title")) or _text(dom.get("title")),
            "viewport": {
                "width": _as_int(page.get("w")),
                "height": _as_int(page.get("h")),
                "page_width": _as_int(page.get("pw")),
                "page_height": _as_int(page.get("ph")),
            },
        },
        "visible_text": visible_text,
        "dom_counters": counters,
        "headings": _as_text_list(dom.get("headings"))[:MAX_SAMPLES],
        "metadata": {
            "description": _text(_as_mapping(dom.get("meta")).get("description")),
            "robots": _text(_as_mapping(dom.get("meta")).get("robots")),
            "canonical_url": _text(_as_mapping(dom.get("meta")).get("canonical_url")),
            "json_ld_types": _as_text_list(dom.get("json_ld_types"))[:MAX_SAMPLES],
        },
        "interaction_summary": interaction_summary,
        "network_summary": network_summary,
        "accessibility_summary": accessibility_summary,
        "risk_flags": risk_flags,
        "extraction_strategy": extraction_strategy,
        "evidence": {
            "screenshot_path": _text(evidence.get("screenshot_path")),
            "source": "browser-harness",
            "errors": errors,
        },
    }


def recommend_browser_extraction_strategy(
    *,
    counters: Mapping[str, int],
    visible_text_length: int,
    network_summary: Mapping[str, Any],
    risk_flags: list[str],
    authorized: bool,
) -> dict[str, Any]:
    if not authorized:
        return {
            "recommended_path": "blocked_review",
            "fit": "blocked",
            "confidence": 10,
            "field_stability": "low",
            "reasons": ["未确认授权，不执行真实浏览器结构诊断。"],
            "next_steps": ["取得明确授权后重新运行诊断。"],
            "cleaning_notes": ["不生成字段抽取或清洗脚本。"],
        }

    if "auth_wall_or_login_signal" in risk_flags:
        return {
            "recommended_path": "manual_review",
            "fit": "low",
            "confidence": 35,
            "field_stability": "low",
            "reasons": ["页面存在登录、验证码或账号态信号。"],
            "next_steps": ["人工确认公开边界；不要把登录态页面纳入自动采集。"],
            "cleaning_notes": ["只保留公开页面字段，不处理账号态或个人信息字段。"],
        }

    if counters.get("forms", 0) > 0:
        return {
            "recommended_path": "manual_review",
            "fit": "low",
            "confidence": 45,
            "field_stability": "low",
            "reasons": ["页面包含表单，可能涉及查询条件、登录态或个人信息。"],
            "next_steps": ["先确认表单用途；公开搜索表单可转为参数化采集计划。"],
            "cleaning_notes": ["将输入参数、结果列表和详情字段分开建模。"],
        }

    if _as_int(network_summary.get("api_candidate_count")) > 0:
        return {
            "recommended_path": "official_api_or_file",
            "fit": "medium",
            "confidence": 74,
            "field_stability": "medium",
            "reasons": ["浏览器运行时发现 XHR/fetch 或 JSON/API 候选请求。"],
            "next_steps": [
                "优先核验候选接口是否公开、稳定且允许使用。",
                "若接口字段稳定，将其转为结构化采集源；否则回退浏览器自动化。",
            ],
            "cleaning_notes": [
                "保留接口路径、字段名、分页参数和响应样本，先做类型推断再清洗。"
            ],
        }

    if "dynamic_rendering_signal" in risk_flags:
        return {
            "recommended_path": "browser_automation",
            "fit": "medium",
            "confidence": 68,
            "field_stability": "low",
            "reasons": ["脚本和资源信号较重，静态 HTML 可能只是页面骨架。"],
            "next_steps": [
                "用真实浏览器记录可见文本、截图和选择器样本。",
                "对比静态 preflight 与浏览器结果，定位运行时才出现的字段。",
            ],
            "cleaning_notes": ["为运行时字段记录选择器、缺失率和截图证据。"],
        }

    if (
        visible_text_length >= 120
        and counters.get("links", 0) > 0
        and counters.get("scripts", 0) <= 10
    ):
        return {
            "recommended_path": "generic_web",
            "fit": "high",
            "confidence": 84,
            "field_stability": "high",
            "reasons": ["浏览器渲染后正文、链接和标题可直接读取，动态依赖较低。"],
            "next_steps": ["建立 DOM 字段契约，先低频采集公开页面样本。"],
            "cleaning_notes": ["清洗标题、正文、链接和 canonical URL，保留 requested/final URL。"],
        }

    return {
        "recommended_path": "manual_review",
        "fit": "low",
        "confidence": 50,
        "field_stability": "low",
        "reasons": ["页面结构信号不足，无法稳定判断采集方式。"],
        "next_steps": ["补充人工页面审阅，或提供平台类型后再生成专项采集方案。"],
        "cleaning_notes": ["暂不生成自动清洗规则，先确认字段来源。"],
    }


def _build_dom_counters(dom: Mapping[str, Any]) -> dict[str, int]:
    counters = _as_mapping(dom.get("counters"))
    return {
        "links": _as_int(counters.get("links")),
        "same_origin_links": _as_int(counters.get("same_origin_links")),
        "external_links": _as_int(counters.get("external_links")),
        "forms": _as_int(counters.get("forms")),
        "inputs": _as_int(counters.get("inputs")),
        "buttons": _as_int(counters.get("buttons")),
        "tables": _as_int(counters.get("tables")),
        "lists": _as_int(counters.get("lists")),
        "articles": _as_int(counters.get("articles")),
        "cards": _as_int(counters.get("cards")),
        "images": _as_int(counters.get("images")),
        "scripts": _as_int(counters.get("scripts")),
        "stylesheets": _as_int(counters.get("stylesheets")),
        "json_ld_blocks": _as_int(counters.get("json_ld_blocks")),
    }


def _build_visible_text_summary(dom: Mapping[str, Any]) -> dict[str, Any]:
    sample = _text(dom.get("visible_text_sample"))
    length = _as_int(dom.get("visible_text_length"))
    line_count = _as_int(dom.get("visible_line_count"))
    return {
        "length": length,
        "line_count": line_count,
        "sample": sample[:1_200],
    }


def _build_interaction_summary(dom: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "links": _as_mapping_list(dom.get("links"))[:MAX_SAMPLES],
        "forms": _as_mapping_list(dom.get("forms"))[:MAX_SAMPLES],
    }


def _build_network_summary(
    resources: list[Mapping[str, Any]],
    *,
    final_url: str,
) -> dict[str, Any]:
    counts = Counter(
        _text(resource.get("initiator_type")) or _text(resource.get("initiatorType")) or "other"
        for resource in resources
    )
    origin = _origin(final_url)
    same_origin = 0
    cross_origin = 0
    api_candidates: list[dict[str, Any]] = []
    for resource in resources:
        resource_url = _text(resource.get("url"))
        if resource_url == "":
            continue
        if _origin(resource_url) == origin:
            same_origin += 1
        else:
            cross_origin += 1
        initiator = _text(resource.get("initiator_type")) or _text(resource.get("initiatorType"))
        if _is_api_candidate(resource_url, initiator):
            api_candidates.append(
                {
                    "url": _redact_url(resource_url),
                    "initiator_type": initiator or "other",
                    "same_origin": _origin(resource_url) == origin,
                    "duration_ms": _as_int(resource.get("duration_ms")),
                    "transfer_size": _as_int(resource.get("transfer_size")),
                }
            )
    return {
        "resource_count": len(resources),
        "same_origin_resources": same_origin,
        "cross_origin_resources": cross_origin,
        "initiator_type_counts": dict(sorted(counts.items())),
        "xhr_fetch_count": counts.get("fetch", 0) + counts.get("xmlhttprequest", 0),
        "script_count": counts.get("script", 0),
        "image_count": counts.get("img", 0) + counts.get("image", 0),
        "api_candidate_count": len(api_candidates),
        "api_candidates": api_candidates[:MAX_SAMPLES],
    }


def _build_accessibility_summary(accessibility: Mapping[str, Any]) -> dict[str, Any]:
    role_counts = _as_mapping(accessibility.get("role_counts"))
    normalized_counts = {str(key): _as_int(value) for key, value in role_counts.items()}
    return {
        "total_nodes": _as_int(accessibility.get("total_nodes")),
        "role_counts": dict(sorted(normalized_counts.items())),
        "named_nodes": _as_mapping_list(accessibility.get("named_nodes"))[:MAX_SAMPLES],
    }


def _build_risk_flags(
    *,
    final_url: str,
    visible_text_sample: str,
    counters: Mapping[str, int],
    network_summary: Mapping[str, Any],
    errors: list[str],
) -> list[str]:
    flags: list[str] = []
    combined_text = f"{final_url} {visible_text_sample}".lower()
    auth_markers = [
        "login",
        "log in",
        "sign in",
        "signin",
        "account",
        "captcha",
        "验证码",
        "登录",
        "注册",
    ]
    if any(marker in combined_text for marker in auth_markers):
        flags.append("auth_wall_or_login_signal")
    if counters.get("forms", 0) > 0:
        flags.append("form_present")
    if counters.get("scripts", 0) > 10 or _as_int(network_summary.get("xhr_fetch_count")) > 0:
        flags.append("dynamic_rendering_signal")
    if (
        _as_int(network_summary.get("cross_origin_resources")) > 20
        and _as_int(network_summary.get("resource_count")) > 30
    ):
        flags.append("heavy_third_party_surface")
    if errors:
        flags.append("diagnostic_error_present")
    return sorted(set(flags))


def _is_api_candidate(url: str, initiator_type: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if initiator_type in {"fetch", "xmlhttprequest"}:
        return True
    markers = ["/api/", "/graphql", ".json", "/search", "/query", "/ajax"]
    return any(marker in path for marker in markers)


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc == "":
        return url[:500]
    query = "?..." if parsed.query else ""
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}{query}"[:500]


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_mapping_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _as_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item) != ""]


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0
