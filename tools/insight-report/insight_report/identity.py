"""Product identity freeze.

Implements SOP skill ``voc-product-identity`` (G1): parse the Amazon PDP,
separate parent and child ASINs, enumerate the variant matrix, and attach an
explicit confidence to every mapping.  It never merges TikTok SKUs with
Amazon ASINs because no verified crosswalk exists.

Not implemented here: the human adjudication step for fuzzy matches.  Those
cases are returned as ``review_queue`` entries with a null confidence rather
than being guessed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from . import contract
from .ingest import IngestResult, RawResponse

ASIN_RE = re.compile(r"\b([A-Z0-9]{10})\b")
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


@dataclass
class PdpParse:
    request_asin: str
    title: str
    brand: str
    variants: dict[str, list[str]]
    variant_count_claim: int | None
    rating_value: float | None
    rating_count: int | None
    parent_asin: str | None
    child_asin: str | None
    target_color: str | None
    target_size: str | None
    parsed_at: str
    gaps: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)


def _strip_tags(value: str) -> str:
    return WS_RE.sub(" ", TAG_RE.sub(" ", value)).strip()


def _json_object_after(text: str, marker: str) -> dict[str, Any] | None:
    pos = text.find(marker)
    if pos < 0:
        return None
    start = text.find("{", pos)
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _find_title(html_text: str) -> str:
    m = re.search(r'id="productTitle"[^>]*>(.*?)</span>', html_text, re.S | re.I)
    if m:
        value = _strip_tags(m.group(1))
        if value:
            return value
    m = re.search(r"<title>(.*?)</title>", html_text, re.S | re.I)
    if m:
        value = _strip_tags(m.group(1))
        value = re.split(r"\s+[|]\s+|\s+at Amazon", value)[0].strip()
        return value
    return ""


def _find_brand(html_text: str) -> str:
    m = re.search(r'id="bylineInfo"[^>]*>(.*?)</a>', html_text, re.S | re.I)
    if m:
        value = _strip_tags(m.group(1))
        value = re.sub(r"^Visit the\s+", "", value, flags=re.I)
        value = re.sub(r"\s+Store$", "", value, flags=re.I)
        if value:
            return value
    m = re.search(r'"brand"\s*:\s*"([^"]+)"', html_text)
    return m.group(1).strip() if m else ""


def _find_rating(html_text: str) -> tuple[float | None, int | None]:
    rating = None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s+out of 5 stars", html_text)
    if m:
        try:
            rating = float(m.group(1))
        except ValueError:
            rating = None
    count = None
    # Prefer the product-level customer review block.  A bare "N ratings"
    # search can match a sponsored product elsewhere on the page.
    patterns = (
        r'acrCustomerReviewText"[^>]*aria-label="([0-9][0-9,]*)\s+Reviews?"',
        r'data-hook="total-review-count"[^>]*>([0-9][0-9,]*)\s+(?:global\s+)?ratings?',
        r"([0-9][0-9,]*)\s+global ratings",
        r'id="pqv-ratings"[^>]*>\s*[0-9.]+\s+out of 5 stars,\s*([0-9][0-9,]*)\s+ratings?',
    )
    for pattern in patterns:
        m = re.search(pattern, html_text, re.I)
        if m:
            count = int(m.group(1).replace(",", ""))
            break
    return rating, count


def _find_variant_count(html_text: str) -> int | None:
    m = re.search(r'"totalVariationCount"\s*:\s*"?([0-9]+)', html_text)
    if m:
        return int(m.group(1))
    m = re.search(r"([0-9]+)\s+variations?", html_text, re.I)
    return int(m.group(1)) if m else None


def parse_pdp(response: RawResponse) -> PdpParse:
    html_text = response.payload_text or ""
    request_asin = str((response.records[0] or {}).get("asin") if response.records else "") or ""
    gaps: list[str] = []
    evidence: dict[str, str] = {}

    title = _find_title(html_text)
    brand = _find_brand(html_text)
    variants_raw = _json_object_after(html_text, "dimensionValuesDisplayData")
    variants: dict[str, list[str]] = {}
    if variants_raw:
        for asin, values in variants_raw.items():
            if isinstance(values, list):
                variants[str(asin)] = [str(v) for v in values]
        evidence["variants"] = "dimensionValuesDisplayData"
    else:
        gaps.append("[Evidence gap] dimensionValuesDisplayData 未解析到")
    rating, rating_count = _find_rating(html_text)
    variant_count_claim = _find_variant_count(html_text)

    if title:
        evidence["title"] = "productTitle/title"
    else:
        gaps.append("[Evidence gap] product title 未解析到")
    if brand:
        evidence["brand"] = "bylineInfo"
    else:
        gaps.append("[Evidence gap] bylineInfo 未解析到")

    parent: str | None = None
    child: str | None = None
    target_color = None
    target_size = None
    if request_asin in variants:
        child = request_asin
        target_color, target_size = (variants[request_asin] + [None, None])[:2]
    elif request_asin:
        parent = request_asin
    else:
        gaps.append("[Evidence gap] request ASIN 缺失")

    return PdpParse(
        request_asin=request_asin,
        title=title,
        brand=brand,
        variants=variants,
        variant_count_claim=variant_count_claim,
        rating_value=rating,
        rating_count=rating_count,
        parent_asin=parent,
        child_asin=child,
        target_color=target_color,
        target_size=target_size,
        parsed_at=contract.now_iso(),
        gaps=gaps,
        evidence=evidence,
    )


def _window_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def freeze_identity(
    run: IngestResult,
    artifacts: dict[str, Any],
    *,
    market: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    charter = artifacts.get("voc-research-charter.json") or {}
    product_cfg = charter.get("product") or {}
    window_cfg = charter.get("window") or {}
    start = str(window_cfg.get("start") or "2024-01-01")
    end = str(window_cfg.get("end") or contract.today_iso())

    amazon = [r for r in run.responses if r.provider == "amazon"]
    if not amazon:
        raise contract.DataGap("variant", "no Amazon PDP raw response in this run")
    parses = [parse_pdp(r) for r in amazon]

    variants: dict[str, list[str]] = {}
    for p in parses:
        for asin, values in p.variants.items():
            variants.setdefault(asin, values)

    requested = {p.request_asin for p in parses if p.request_asin}
    requested_children = sorted(requested & set(variants))
    requested_parents = sorted(requested - set(variants))
    target_asin = product_cfg.get("target_child_asin")
    if target_asin not in variants:
        target_asin = requested_children[0] if requested_children else None
    parent_asin = product_cfg.get("parent_asin")
    if parent_asin not in requested_parents:
        parent_asin = requested_parents[0] if requested_parents else None
    child_asin = target_asin if target_asin in variants else (requested_children[0] if requested_children else None)
    target_color, target_size = (variants.get(child_asin, []) + [None, None])[:2] if child_asin else (None, None)

    title = next((p.title for p in parses if p.title), "") or str(product_cfg.get("name") or "")
    brand = next((p.brand for p in parses if p.brand), "") or str(product_cfg.get("brand") or "")
    ratings = [p.rating_value for p in parses if p.rating_value is not None]
    counts = [p.rating_count for p in parses if p.rating_count is not None]
    gaps: list[str] = []
    for p in parses:
        gaps.extend(p.gaps)
    if len(variants) == 0:
        gaps.append("[Evidence gap] no variant matrix parsed")
    if not child_asin:
        gaps.append("[Evidence gap] no target child ASIN could be identified")
    if not parent_asin:
        gaps.append("[Evidence gap] no parent ASIN could be identified")

    exact = bool(parent_asin and child_asin and variants and title and brand)
    identity_quality = "exact" if exact else ("probable" if variants and title else "unknown")
    confidence = 1.0 if exact else (0.9 if identity_quality == "probable" else None)

    # The variant claim count is a cross-check, never a substitute for the
    # parsed matrix.  A mismatch is recorded, not silently repaired.
    for p in parses:
        if p.variant_count_claim is not None and p.variant_count_claim != len(variants):
            gaps.append(
                f"[Evidence gap] PDP variant count claim {p.variant_count_claim} != parsed matrix {len(variants)}"
            )

    items = []
    for asin in sorted(variants):
        color, size = (variants[asin] + [None, None])[:2]
        items.append(
            {
                "variant_key": asin,
                "sku_id": None,
                "asin": asin,
                "color": color,
                "size": size,
                "mapping_confidence": 1.0,
                "status": "exact",
                "is_target": asin == child_asin,
                "review_count": None,
                "rating": None,
                "verified_count": None,
                "low_star_count": None,
                "recent_count": None,
                "gap_reason": "[BLOCKED: PDP exposes only a family-level review count; per-variant review count is unavailable]",
            }
        )

    derivations = {
        "product": "parsed from PDP productTitle; charter name used only when the PDP field is empty",
        "brand": "parsed from PDP bylineInfo; charter brand used only when the byline is empty",
        "model": "no model code in the PDP title; left null instead of guessing",
        "parent_asin": "requested ASIN that is absent from dimensionValuesDisplayData",
        "child_asin": "requested ASIN that appears as a key in dimensionValuesDisplayData",
        "family_children": f"len(dimensionValuesDisplayData) = {len(variants)}",
        "mapping_confidence": "1.0 only when parent, child and variant matrix come from the same PDP family block",
        "rating_value": "PDP rating, quality context only; never consumer sentiment",
        "rating_count": "PDP total review count, quality context only; not a per-variant count",
        "per_variant_review_count": "[BLOCKED: PDP exposes only the family-level review count]",
        "tiktok_crosswalk": "[BLOCKED: no verified SKU/ASIN crosswalk]",
    }

    return {
        "product": title,
        "brand": brand,
        "model": None,
        "variant_id": child_asin,
        "sku": None,
        "color": target_color,
        "size": target_size,
        "parent_asin": parent_asin,
        "child_asin": child_asin,
        "mapping_confidence": confidence,
        "family_children": len(variants) if variants else None,
        "market": market or str(charter.get("market") or "US"),
        "language": language or str(charter.get("language") or "en"),
        "window": {"start": start, "end": end, "days": _window_days(start, end)},
        "identity_quality": identity_quality,
        "source": [
            {
                "kind": "artifact",
                "provider": "amazon",
                "endpoint": None,
                "table": None,
                "columns": None,
                "path": "identity-freeze.json",
                "sha256": None,
                "blocked_reason": None,
            },
            contract.source_ref_blocked(
                "[BLOCKED: no verified SKU/ASIN crosswalk between TikTok Shop and Amazon]",
                provider="tiktok_shop",
            ),
        ],
        "variants": {
            "items": items,
            "target_key": child_asin,
            "basis": f"PDP dimensionValuesDisplayData; {len(variants)} ASINs parsed from {len(parses)} PDP responses",
            "source": [
                {
                    "kind": "artifact",
                    "provider": "amazon",
                    "endpoint": None,
                    "table": None,
                    "columns": None,
                    "path": "identity-freeze.json",
                    "sha256": None,
                    "blocked_reason": None,
                }
            ],
        },
        "product_rating": {
            "value": ratings[0] if ratings else None,
            "review_count": counts[0] if counts else None,
            "use": "quality_context_only",
            "source": "PDP rating-out-of-text / acrCustomerReviewText",
        },
        "gaps": sorted(set(gaps)),
        "derivations": derivations,
        "parse_evidence": [p.evidence for p in parses],
        "review_queue": [
            {"asin": asin, "reason": "variant parsed from PDP only; no second source crosswalk", "confidence": None}
            for asin in sorted(variants)[:0]
        ],
    }


def identity_gap_entries(identity: dict[str, Any]) -> list[str]:
    entries = list(identity.get("gaps") or [])
    entries.append("[BLOCKED: no verified SKU/ASIN crosswalk between TikTok Shop and Amazon]")
    entries.append("[BLOCKED: per-variant review counts are not exposed by the PDP]")
    return entries
