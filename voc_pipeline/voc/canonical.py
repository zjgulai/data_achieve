"""Raw -> occurrence -> canonical, with every deduction labelled.

The canonicaliser is deterministic: identical inputs always produce identical
representatives.  Fuzzy duplicates are surfaced for review, never merged
silently.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .contracts import DataLayer, DeductionReason, Frame
from .taxonomy import TAXONOMY_VERSION
from .tiktok_shop import DEFAULT_WINDOW_END, DEFAULT_WINDOW_START, detect_language, identity_noise_reason

URL_RE = re.compile(r"https?://\S+")
WS_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9']+")


def norm_text(text: str) -> str:
    text = URL_RE.sub(" ", text.lower())
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return WS_RE.sub(" ", text).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(norm_text(text).encode("utf-8")).hexdigest()


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(norm_text(text)) if len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Occurrence:
    occurrence_id: str
    source: str
    kind: str
    external_id: str
    frame: str
    subreddit: str
    author: str
    created_utc: int
    url: str
    title: str
    text: str
    score: int
    num_comments: int
    raw_id: str
    quality_flags: list[str] = field(default_factory=list)
    source_meta: dict[str, Any] = field(default_factory=dict)

    @property
    def combined(self) -> str:
        return f"{self.title}\n{self.text}".strip()

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CanonicalRecord:
    canonical_id: str
    representative: str
    memberships: list[str]
    source: str
    external_id: str
    subreddit: str
    author: str
    created_utc: int
    url: str
    title: str
    text: str
    content_hash: str
    duplicate_group_id: str
    dedup_status: str
    frames: list[str]
    product_match: str
    data_layer: str
    content_role: str
    commerciality: str
    organic_confidence: str
    metric_eligibility: str
    quality_flags: list[str]
    language: str = "en"
    taxonomy_version: str = TAXONOMY_VERSION
    source_meta: dict[str, Any] = field(default_factory=dict)
    # E-merge §3.4: provenance for the product gate.  ``auto`` means the
    # classifier decided; ``override`` means the one-time correction ledger
    # did.  The reason is empty for auto rows.
    product_match_source: str = "auto"
    product_match_override_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _parse_created(rec: dict[str, Any]) -> int:
    if rec.get("created_utc") is not None:
        return int(rec["created_utc"])
    return 0


def _tikhub_occurrences(row: dict[str, Any]) -> list[Occurrence]:
    """Parse one persisted TikTok Shop review page into occurrences.

    The provider stores reviews under ``data.data.product_reviews``.  Review
    time is epoch milliseconds in a string; reviewer names are masked by the
    provider, so ``author`` is a display handle, not an account id.
    """
    payload = json.loads(Path(row["path"]).read_text())
    inner = (payload.get("data") or {}) if isinstance(payload, dict) else {}
    data = inner.get("data") if isinstance(inner, dict) else None
    records = data.get("product_reviews") if isinstance(data, dict) else None
    if not isinstance(records, list):
        return []
    request = row.get("request") or {}
    frame = request.get("frame", Frame.TIKTOK_SHOP_VERIFIED.value)
    product_id = str(request.get("product_id") or "")
    out: list[Occurrence] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        review_id = str(rec.get("review_id") or "")
        if not review_id:
            continue
        text = str(rec.get("review_text") or "")
        reviewer = str(rec.get("reviewer_name") or "")
        try:
            created = int(rec.get("review_time") or 0) // 1000
        except (TypeError, ValueError):
            created = 0
        out.append(
            Occurrence(
                occurrence_id=f"tiktok:review:{review_id}:{frame}",
                source="tiktok_shop",
                kind="review",
                external_id=review_id,
                frame=frame,
                subreddit="",
                author=reviewer or "[anonymous]",
                created_utc=created,
                url=f"https://www.tiktok.com/shop/pdp/{rec.get('product_id') or product_id}",
                title="",
                text=text,
                score=0,
                num_comments=0,
                raw_id=row["raw_id"],
                quality_flags=[] if text.strip() else ["deleted_or_empty"],
                source_meta={
                    "product_id": str(rec.get("product_id") or ""),
                    "sku_id": str(rec.get("sku_id") or ""),
                    "variant": str(rec.get("sku_specification") or ""),
                    "rating": rec.get("review_rating"),
                    "verified_purchase": rec.get("is_verified_purchase"),
                    "incentivized": rec.get("is_incentivized_review"),
                    "helpful_count": rec.get("helpful_count"),
                    "region": str(rec.get("review_country") or ""),
                    "product_name": str(rec.get("product_name") or ""),
                    "reviewer_masked": reviewer,
                    "review_time": _epoch_ms_to_iso(rec.get("review_time")),
                    "text_language": detect_language(text),
                    "quarantine_reason": identity_noise_reason(rec, product_id),
                },
            )
        )
    return out


def occurrences_from_ledger(ledger_path: Path | list[Path]) -> list[Occurrence]:
    paths = [ledger_path] if isinstance(ledger_path, Path) else list(ledger_path)
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(json.loads(path.read_text())["rows"])
    occurrences: list[Occurrence] = []
    for row in rows:
        if row.get("status") != "success":
            continue
        if row.get("provider") == "tikhub":
            occurrences.extend(_tikhub_occurrences(row))
            continue
        payload = json.loads(Path(row["path"]).read_text())
        records = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            continue
        req = row["request"]
        frame = req.get("frame", Frame.NATURAL.value)
        kind = req.get("kind", "posts")
        for rec in records:
            external_id = str(rec.get("id") or "")
            if not external_id:
                continue
            if kind == "posts":
                title = rec.get("title") or ""
                body = rec.get("selftext") or ""
                if body in ("[removed]", "[deleted]"):
                    body = ""
                url = "https://www.reddit.com" + (rec.get("permalink") or f"/comments/{external_id}")
                occ = Occurrence(
                    occurrence_id=f"reddit:post:{external_id}:{frame}",
                    source="reddit",
                    kind="post",
                    external_id=external_id,
                    frame=frame,
                    subreddit=rec.get("subreddit") or req.get("subreddit", ""),
                    author=rec.get("author") or "[deleted]",
                    created_utc=_parse_created(rec),
                    url=url,
                    title=title,
                    text=body,
                    score=int(rec.get("score") or 0),
                    num_comments=int(rec.get("num_comments") or 0),
                    raw_id=row["raw_id"],
                )
            else:
                body = rec.get("body") or ""
                if body in ("[removed]", "[deleted]"):
                    body = ""
                url = "https://www.reddit.com" + (rec.get("permalink") or "")
                occ = Occurrence(
                    occurrence_id=f"reddit:comment:{external_id}:{frame}",
                    source="reddit",
                    kind="comment",
                    external_id=external_id,
                    frame=frame,
                    subreddit=rec.get("subreddit") or req.get("subreddit", ""),
                    author=rec.get("author") or "[deleted]",
                    created_utc=_parse_created(rec),
                    url=url,
                    title="",
                    text=body,
                    score=int(rec.get("score") or 0),
                    num_comments=0,
                    raw_id=row["raw_id"],
                )
            if not occ.text.strip() and not occ.title.strip():
                occ.quality_flags.append("deleted_or_empty")
            occurrences.append(occ)
    return occurrences


RELEVANCE_TERMS = (
    "belly band",
    "belly support",
    "support band",
    "support belt",
    "maternity band",
    "maternity belt",
    "pregnancy band",
    "pregnancy belt",
    "bump support",
    "momcozy",
)
BRAND_TERMS = ("momcozy",)
COMMERCIAL_TERMS = ("affiliate", "sponsored", "paid partnership", "#ad", "discount code", "promo code", "use my code")
FAILURE_TERMS = (
    "doesn't work",
    "didn't work",
    "not work",
    "hurt",
    "uncomfortable",
    "slip",
    "slide",
    "roll down",
    "rolls down",
    "too tight",
    "too small",
    "too big",
    "useless",
    "waste of money",
    "returned it",
    "returning it",
    "send it back",
    "disappoint",
    "not worth",
    "no support",
    "lack of support",
    "digs into",
    "dug into",
)

PRODUCT_NOUNS = ("band", "belt", "strap", "velcro", "wrap", "momcozy", "ergonest", "cozysupport")

# E-merge §2.1 / §4.3: the product-family test used to be a substring check
# for ``band``.  That matched ``husband`` and ``band extender`` and marked a
# Momcozy diaper pail, nursing bra, breast pump and pregnancy pillow as the
# support-band family.  The rule below is word-boundary based, requires an
# explicit product-family phrase or a standalone garment noun, and treats
# same-brand other product lines as ``brand_other_product``.
PRODUCT_FAMILY_PHRASES = (
    "belly band",
    "belly bands",
    "belly support",
    "support band",
    "support belt",
    "maternity band",
    "maternity belt",
    "pregnancy band",
    "pregnancy belt",
    "pregnancy support belt",
    "bump support",
    "belly wrap",
    "belly belt",
    "belly binder",
)
# Phrases that contain a garment token but name something else.  Removing
# them before the token scan keeps ``band extender``, ``waistband`` and
# ``seat belt`` out of the support-band family.
EXCLUDED_GARMENT_PHRASES = (
    "band extender",
    "waistband",
    "waist band",
    "headband",
    "head band",
    "sweatband",
    "sweat band",
    "seat belt",
    "seatbelt",
    "band-aid",
    "bandaid",
    "wedding band",
    "rubber band",
    "hair band",
    "hairband",
)
GARMENT_TOKEN_RE = re.compile(r"\b(?:band|bands|belt|belts|binder|binders|strap|straps)\b", re.IGNORECASE)
# Same-brand product lines that are not the support band.  A brand mention
# plus one of these is ``brand_other_product`` even when another clause
# contains a garment word (for example a nursing bra that mentions a
# ``band extender``).
OTHER_PRODUCT_LINE_RE = re.compile(
    r"\b(?:diaper pail|diaper bin|diaper trash|nursing bra|nursing bras|"
    r"pumping bra|pumping bras|breast pump|breast pumps|pregnancy pillow|"
    r"maternity pillow|mommy pillow|cocoon pillow|body oil|compression socks|"
    r"baby bottle|bottles|wipe warmer|stroller|car seat|sound machine)\b",
    re.IGNORECASE,
)
# "not the Momcozy one" means the author is naming a generic support band.
NEGATED_BRAND_RE = re.compile(
    r"\b(?:not|isn'?t|wasn'?t|never)\s+(?:the\s+|a\s+)?(?:momcozy|mom cozy)\b",
    re.IGNORECASE,
)


def _product_family_mention(text: str) -> bool:
    """Whether the text names the support-band product family.

    ``text`` is already lower-cased by :func:`classify_product`.
    """
    scrubbed = text
    for phrase in EXCLUDED_GARMENT_PHRASES:
        scrubbed = scrubbed.replace(phrase, " ")
    if any(phrase in scrubbed for phrase in PRODUCT_FAMILY_PHRASES):
        return True
    return bool(GARMENT_TOKEN_RE.search(scrubbed))


def classify_product(text: str) -> tuple[str, str]:
    """Return (product_match, data_layer) for a Reddit record.

    Values follow E-merge §2.1: ``exact_current_family`` is the support-band
    family with a brand/model mention, ``category_adjacent`` is the same
    category without the brand (or a generic category discussion),
    ``brand_other_product`` is the brand on another product line, and
    ``irrelevant`` is neither.
    """
    t = text.lower()
    has_relevance = any(k in t for k in RELEVANCE_TERMS)
    brand = any(k in t for k in BRAND_TERMS)
    family = _product_family_mention(t)
    other_line = bool(OTHER_PRODUCT_LINE_RE.search(t))
    if brand and NEGATED_BRAND_RE.search(t) and family:
        return "category_adjacent", DataLayer.CONSUMER_OBSERVATION_FACT.value
    if brand and other_line and not family:
        return "brand_other_product", DataLayer.EXCLUDED_LINEAGE.value
    if brand and family:
        return "exact_current_family", DataLayer.CONSUMER_OBSERVATION_FACT.value
    if brand:
        return "brand_other_product", DataLayer.EXCLUDED_LINEAGE.value
    if has_relevance:
        # Keep the pre-E data-layer split: a generic relevance hit without a
        # concrete support-band phrase stays in the discovery hold queue.
        if any(
            key in t
            for key in (
                "belly band",
                "belly support",
                "support band",
                "maternity band",
                "support belt",
            )
        ):
            return "category_adjacent", DataLayer.CONSUMER_OBSERVATION_FACT.value
        return "category_adjacent", DataLayer.DISCOVERY_HOLD_QUEUE.value
    return "irrelevant", DataLayer.EXCLUDED_LINEAGE.value


def classify_commerciality(text: str) -> str:
    t = text.lower()
    if any(k in t for k in COMMERCIAL_TERMS):
        return "explicit_paid_or_affiliate"
    if "http" in t and ("amzn" in t or "amazon.com" in t):
        return "link_only"
    return "no_signal_observed"


def is_failure_record(text: str) -> bool:
    """Diagnostic lens: a failure term must sit in a clause that names the product.

    Generic pregnancy pain is not a product complaint.  Requiring the product
    noun in the same clause keeps the diagnostic frame from swallowing the
    whole corpus.
    """
    for clause in re.split(r"[.!?;\n]|,\s*(?:but|however|although|though)\s+", text.lower()):
        if not clause.strip():
            continue
        if any(n in clause for n in PRODUCT_NOUNS) and any(f in clause for f in FAILURE_TERMS):
            return True
    return False


def _epoch_ms_to_iso(value: Any) -> str | None:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    if millis <= 0:
        return None
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def _in_window(iso: str | None, start: str, end: str) -> bool:
    if not iso:
        return False
    try:
        moment = datetime.fromisoformat(iso)
        return datetime.fromisoformat(start) <= moment <= datetime.fromisoformat(end)
    except ValueError:
        return False


def _mergeable(a: Occurrence, b: Occurrence) -> bool:
    """Whether two occurrences are the same content asset.

    Reddit records merge on identical normalized text (reposts are one asset).
    A TikTok Shop review is one verified purchase: identical generic text from
    two buyers is two observations, not a syndicated duplicate.  Only the same
    masked reviewer posting the same text twice can merge, and empty text is
    never a duplicate signal.
    """
    if not a.combined.strip() or not b.combined.strip():
        return False
    same_author = bool(a.author) and a.author == b.author and a.author not in {"[deleted]", "[anonymous]"}
    if a.source != b.source:
        return same_author
    if a.source == "tiktok_shop":
        return same_author and a.external_id != b.external_id
    return True


PRODUCT_MATCH_VALUES = (
    "exact_current_family",
    "category_adjacent",
    "brand_other_product",
    "irrelevant",
)


def load_product_match_overrides(path: Path) -> dict[str, dict[str, str]]:
    """Read the one-time ``product_match`` correction ledger.

    E-merge §5.2 lists six records whose classification the generic rules
    cannot settle safely.  The ledger is explicit, reason-bearing and
    fail-closed: an unknown value or a missing reason raises instead of
    silently changing the cohort.
    """
    path = Path(path)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "voc-product-match-overrides/1":
        raise ValueError(f"{path}: unexpected schema {payload.get('schema')!r}")
    raw = payload.get("overrides")
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: missing overrides object")
    out: dict[str, dict[str, str]] = {}
    for canonical_id, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: {canonical_id}: override must be an object")
        value = str(entry.get("product_match") or "")
        if value not in PRODUCT_MATCH_VALUES:
            raise ValueError(
                f"{path}: {canonical_id}: invalid product_match {value!r}; "
                f"expected one of {PRODUCT_MATCH_VALUES}"
            )
        reason = str(entry.get("reason") or "").strip()
        if not reason:
            raise ValueError(f"{path}: {canonical_id}: override needs a reason")
        out[canonical_id] = {"product_match": value, "reason": reason}
    return out


def apply_product_match_override(
    product_match: str, data_layer: str, override: dict[str, str] | None
) -> tuple[str, str]:
    """Apply one ledger row and keep ``data_layer`` consistent with it."""
    if not override:
        return product_match, data_layer
    value = override["product_match"]
    if value in {"brand_other_product", "irrelevant"}:
        return value, DataLayer.EXCLUDED_LINEAGE.value
    if value == "exact_current_family":
        return value, DataLayer.CONSUMER_OBSERVATION_FACT.value
    # category_adjacent: a record that used to be consumer-visible stays
    # consumer-visible; one that was excluded is promoted to the category
    # layer.
    if data_layer == DataLayer.EXCLUDED_LINEAGE.value:
        data_layer = DataLayer.CONSUMER_OBSERVATION_FACT.value
    return value, data_layer


def build_canonical(
    occurrences: list[Occurrence],
    *,
    window_start: str = DEFAULT_WINDOW_START,
    window_end: str = DEFAULT_WINDOW_END,
    product_match_overrides: dict[str, dict[str, str]] | None = None,
) -> tuple[list[CanonicalRecord], dict[str, Any]]:
    """Group occurrences into canonical records and reconcile the counts."""
    # Level: occurrence.  Same external id + frame is one occurrence.
    uniq: dict[tuple[str, str], Occurrence] = {}
    dropped_occ = 0
    for occ in occurrences:
        key = (occ.external_id, occ.frame)
        if key in uniq:
            dropped_occ += 1
            continue
        uniq[key] = occ
    occ_list = list(uniq.values())

    # Level: canonical.  Product identity and time window are decided before
    # dedup so a quarantined row can never be merged into a target record.
    quarantine: list[dict[str, Any]] = []
    out_of_window: list[dict[str, Any]] = []
    eligible_occ: list[Occurrence] = []
    for occ in occ_list:
        if occ.source == "tiktok_shop":
            reason = occ.source_meta.get("quarantine_reason")
            if reason:
                quarantine.append(
                    {
                        "review_id": occ.external_id,
                        "variant": occ.source_meta.get("variant"),
                        "rating": occ.source_meta.get("rating"),
                        "reason": reason,
                        "raw_id": occ.raw_id,
                    }
                )
                continue
            if not _in_window(occ.source_meta.get("review_time"), window_start, window_end):
                out_of_window.append(
                    {
                        "review_id": occ.external_id,
                        "review_time": occ.source_meta.get("review_time"),
                        "review_id_group": occ.external_id,
                    }
                )
                continue
        eligible_occ.append(occ)

    # Exact duplicate groups across frames and sources.
    by_hash: dict[str, list[Occurrence]] = {}
    for occ in eligible_occ:
        if not occ.combined.strip():
            continue
        key = text_hash(occ.combined)
        by_hash.setdefault(key, []).append(occ)

    # Fuzzy candidates: same author and high textual overlap but different hash.
    parent = {id(o): o for o in eligible_occ}

    def find(o: Occurrence) -> Occurrence:
        cur = o
        while id(parent[id(cur)]) != id(cur):
            cur = parent[id(cur)]
        return cur

    def union(a: Occurrence, b: Occurrence) -> None:
        ra, rb = find(a), find(b)
        if id(ra) != id(rb):
            parent[id(rb)] = ra

    # Exact duplicates first: identical normalized text is one canonical
    # record only when the merge rule above says it is the same asset.
    for group in by_hash.values():
        roots: list[Occurrence] = []
        for occ in group:
            target = next((r for r in roots if _mergeable(r, occ)), None)
            if target is None:
                roots.append(occ)
            else:
                union(target, occ)

    by_author: dict[str, list[Occurrence]] = {}
    for occ in eligible_occ:
        if occ.source != "reddit":
            continue
        if occ.author and occ.author != "[deleted]":
            by_author.setdefault(occ.author.lower(), []).append(occ)
    fuzzy_review: list[dict[str, Any]] = []
    for author, items in by_author.items():
        if len(items) < 2:
            continue
        toks = {id(o): tokens(o.combined) for o in items}
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                sim = jaccard(toks[id(a)], toks[id(b)])
                if 0.90 <= sim < 1.0:
                    union(a, b)
                    fuzzy_review.append(
                        {"author": author, "a": a.external_id, "b": b.external_id, "jaccard": round(sim, 3)}
                    )

    comps: dict[int, list[Occurrence]] = {}
    for occ in eligible_occ:
        comps.setdefault(id(find(occ)), []).append(occ)

    records: list[CanonicalRecord] = []
    dedup_deductions = {
        DeductionReason.CROSS_FRAME_OVERLAP.value: 0,
        DeductionReason.CROSS_SOURCE_SYNDICATED.value: 0,
        DeductionReason.CROSSPOST_SAME_AUTHOR.value: 0,
        DeductionReason.PRODUCT_MISMATCH.value: len(quarantine),
        DeductionReason.OUT_OF_WINDOW.value: len(out_of_window),
    }
    for comp in comps.values():
        rep = min(comp, key=lambda o: (o.created_utc, o.external_id))
        frames = sorted({o.frame for o in comp})
        drop = len(comp) - 1
        if drop:
            same_author = len({o.author for o in comp}) == 1
            reason = (
                DeductionReason.CROSSPOST_SAME_AUTHOR.value
                if same_author
                else DeductionReason.CROSS_SOURCE_SYNDICATED.value
            )
            dedup_deductions[reason] += drop
        text = rep.combined
        if rep.source == "tiktok_shop":
            product_match, data_layer = "exact_current_family", DataLayer.CONSUMER_OBSERVATION_FACT.value
            incentivized = bool(rep.source_meta.get("incentivized"))
            commerciality = "incentivized_review" if incentivized else "no_signal_observed"
            content_role = "consumer_experience"
            organic = "medium" if incentivized else "high"
        else:
            product_match, data_layer = classify_product(text)
            commerciality = classify_commerciality(text)
            content_role = "consumer_experience"
            organic = "high" if commerciality == "no_signal_observed" else "medium"
        canonical_id = f"c-{rep.external_id}"
        override = (product_match_overrides or {}).get(canonical_id)
        product_match, data_layer = apply_product_match_override(
            product_match, data_layer, override
        )
        if commerciality in ("explicit_paid_or_affiliate",):
            content_role = "creator_testimonial"
            organic = "none"
            data_layer = DataLayer.CLAIM_ASSET_FACT.value
        flags: list[str] = []
        if commerciality == "explicit_paid_or_affiliate":
            flags.append("commercial_disclosure")
        if "momcozy" in text.lower():
            flags.append("brand_mention")
        if is_failure_record(text):
            flags.append("failure_lens")
        if len(tokens(text)) < 8:
            flags.append("low_information")
        if rep.source == "tiktok_shop":
            flags.append("verified_purchase" if rep.source_meta.get("verified_purchase") else "unverified_purchase")
            if rep.source_meta.get("incentivized"):
                flags.append("incentivized_review")
            if not text.strip():
                flags.append("no_text")
        if rep.quality_flags:
            flags.extend(rep.quality_flags)
        eligibility = "natural_sample_candidate"
        if rep.source == "tiktok_shop":
            eligibility = (
                "tiktok_verified_candidate"
                if rep.source_meta.get("verified_purchase")
                else "excluded_unverified_review"
            )
        elif product_match in {"irrelevant", "brand_other_product"}:
            eligibility = "excluded_irrelevant"
        elif data_layer == DataLayer.CLAIM_ASSET_FACT.value:
            eligibility = "content_claim_only"
        elif data_layer == DataLayer.DISCOVERY_HOLD_QUEUE.value:
            eligibility = "discovery_only"
        elif "low_information" in flags:
            eligibility = "excluded_low_information"
        membership = sorted({f for f in frames})
        if Frame.QUALITATIVE_SEED.value in membership:
            eligibility = "qualitative_seed_only"
        if "failure_lens" in flags and Frame.NATURAL.value in membership:
            membership = sorted(set(membership) | {Frame.DIAGNOSTIC.value})
        records.append(
            CanonicalRecord(
                canonical_id=canonical_id,
                representative=rep.occurrence_id,
                memberships=[f"{rep.source}:{rep.external_id}:{f}" for f in membership],
                source=rep.source,
                external_id=rep.external_id,
                subreddit=rep.subreddit,
                author=rep.author,
                created_utc=rep.created_utc,
                url=rep.url,
                title=rep.title,
                text=rep.text,
                content_hash=text_hash(text),
                duplicate_group_id=f"d-{text_hash(text)[:16]}",
                dedup_status="known_duplicate_representative" if drop else "unique",
                frames=membership,
                product_match=product_match,
                data_layer=data_layer,
                content_role=content_role,
                commerciality=commerciality,
                organic_confidence=organic,
                metric_eligibility=eligibility,
                quality_flags=sorted(set(flags)),
                language=str(rep.source_meta.get("text_language") or "en"),
                source_meta=dict(rep.source_meta),
                product_match_source="override" if override else "auto",
                product_match_override_reason=override["reason"] if override else "",
            )
        )

    frames_count: dict[str, int] = {}
    for rec in records:
        for frame in rec.frames:
            frames_count[frame] = frames_count.get(frame, 0) + 1

    raw_responses = len({o.raw_id for o in occ_list})
    summary = {
        "raw_objects": len(occurrences),
        "raw_responses": raw_responses,
        "occurrences_raw": len(occurrences),
        "occurrences_deduplicated": len(occ_list),
        "within_frame_overlap_dropped": dropped_occ,
        "canonical_records": len(records),
        "frame_memberships": sum(frames_count.values()),
        "frame_counts": frames_count,
        "deduction_reasons": dedup_deductions,
        "fuzzy_review_candidates": fuzzy_review,
        "quarantine": quarantine,
        "out_of_window_records": out_of_window,
        "raw_by_source": dict(Counter(o.source for o in occ_list)),
        "canonical_by_source": dict(Counter(r.source for r in records)),
        "excluded": {
            "irrelevant": sum(1 for r in records if r.product_match == "irrelevant"),
            "brand_other_product": sum(1 for r in records if r.product_match == "brand_other_product"),
            "low_information": sum(1 for r in records if r.metric_eligibility == "excluded_low_information"),
            "claim_asset": sum(1 for r in records if r.metric_eligibility == "content_claim_only"),
        },
    }
    summary["reconciliation"] = {
        "occurrences_to_canonical": len(occ_list) - len(records),
        "memberships_to_occurrences": summary["frame_memberships"] - len(occ_list),
    }
    summary["reconciliation"]["deducted"] = sum(dedup_deductions.values())
    if summary["reconciliation"]["deducted"] != summary["reconciliation"]["occurrences_to_canonical"]:
        raise ValueError(
            "canonical reconciliation failed: "
            f"{len(occ_list)} occurrences - {summary['reconciliation']['deducted']} deductions "
            f"!= {len(records)} canonical"
        )
    return records, summary


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
