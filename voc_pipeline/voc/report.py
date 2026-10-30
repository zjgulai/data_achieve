"""Standalone HTML report renderer.

Every heading is a claim.  Every claim carries Observed / Interpretation /
Counterevidence / Decision implication.  Every exhibit carries Basis / Unit /
Limit / Status.  No third-party runtime, no pie chart, no net score.
"""

from __future__ import annotations

import html
from collections import Counter
from pathlib import Path
from typing import Any

from .contracts import FORBIDDEN_CONCLUSIONS, Claim, EvidenceGrade
from .taxonomy import ALL_CODES

LABELS = {c.code: c.label for c in ALL_CODES}
GRADE_CLASS = {
    EvidenceGrade.CONFIRMED.value: "g-confirmed",
    EvidenceGrade.DIRECTIONAL.value: "g-directional",
    EvidenceGrade.SUPPORTED_HYPOTHESIS.value: "g-hypothesis",
    EvidenceGrade.GAP.value: "g-gap",
    EvidenceGrade.BLOCKED.value: "g-blocked",
    EvidenceGrade.NOT_AUTHORIZED.value: "g-notauth",
}
GRADE_VALUES = tuple(GRADE_CLASS)

# Frozen evaluation numbers from artifacts/run-20261029/llm-coding/eval-result-high.json.
# The published report applies the high-confidence gate: medium/low aspects are
# abstentions, not evidence.  "strict" means aspect code and polarity both match.
# Precision is published per source.  The merged row is a comparison only: it
# overstates Reddit (50.0%) and understates TikTok Shop (90.5%).  The gold set is
# itself an LLM annotation, so these measure inter-LLM precision, not
# human-verified accuracy; the sample is 50 records / 85 gold aspects.
# Cross-model agreement is a third basis: model-vs-model agreement from the
# calibration blind labels.  It is not human accuracy either.
LLM_STRICT_PRECISION_PCT = 87.0
LLM_STRICT_RECALL_PCT = 47.1
LLM_TIKTOK_PRECISION_PCT = 90.5
LLM_TIKTOK_RECALL_PCT = 49.4
LLM_TIKTOK_HIGH_ASPECTS = 42
LLM_REDDIT_PRECISION_PCT = 50.0
LLM_REDDIT_RECALL_PCT = 25.0
LLM_REDDIT_HIGH_ASPECTS = 4
LLM_ALL_HIGH_ASPECTS = 46
# Regression comparison only; not the published headline.
LLM_ALL_MODE_STRICT_PRECISION_PCT = 79.7
LLM_ALL_MODE_STRICT_RECALL_PCT = 60.0
# Gold-set abstentions under the frozen high-only policy.
LLM_HIGH_ONLY_ABSTENTIONS_GOLD = 18
LLM_ALL_MODE_CODER_ASPECTS_GOLD = 64
LLM_HIGH_ONLY_ABSTENTION_SHARE_PCT = 28.1
# Build-level sensitivity: high confidence AND a decidable polarity.
LLM_BUILD_STRICT_PRECISION_PCT = 86.7
LLM_BUILD_STRICT_RECALL_PCT = 45.9
RULE_STRICT_PRECISION_PCT = 63.4
RULE_STRICT_RECALL_PCT = 30.6
PRECISION_THRESHOLD_PCT = 90.0

SOURCE_LABELS = {
    "tiktok_shop": "TikTok Shop",
    "reddit": "Reddit",
    "amazon_pdp": "Amazon PDP",
    "tikhub_video": "TikHub 视频层",
    "mixed": "合并来源",
    "none": "无编码信源",
    "unknown": "UNKNOWN",
}


def _fallback_precision() -> dict[str, Any]:
    """Frozen eval numbers, used when no eval artifact is passed in."""
    return {
        "gate": "high",
        "rule": "strict",
        "match": "code+polarity",
        "threshold_pct": PRECISION_THRESHOLD_PCT,
        "sources": {
            "tiktok_shop": {
                "label": "TikTok Shop",
                "high_aspects": LLM_TIKTOK_HIGH_ASPECTS,
                "precision_pct": LLM_TIKTOK_PRECISION_PCT,
                "recall_pct": LLM_TIKTOK_RECALL_PCT,
            },
            "reddit": {
                "label": "Reddit",
                "high_aspects": LLM_REDDIT_HIGH_ASPECTS,
                "precision_pct": LLM_REDDIT_PRECISION_PCT,
                "recall_pct": LLM_REDDIT_RECALL_PCT,
            },
            "all": {
                "label": "合并",
                "high_aspects": LLM_ALL_HIGH_ASPECTS,
                "precision_pct": LLM_STRICT_PRECISION_PCT,
                "recall_pct": LLM_STRICT_RECALL_PCT,
            },
        },
    }


def _rule_precision() -> dict[str, Any]:
    """Rule-coder baseline from gold/metrics.json; the Reddit cell is empty."""
    return {
        "gate": "all",
        "rule": "strict",
        "match": "code+polarity",
        "threshold_pct": PRECISION_THRESHOLD_PCT,
        "sources": {
            "tiktok_shop": {
                "label": "TikTok Shop",
                "high_aspects": 41,
                "precision_pct": RULE_STRICT_PRECISION_PCT,
                "recall_pct": 33.8,
            },
            "reddit": {
                "label": "Reddit",
                "high_aspects": 0,
                "precision_pct": 0.0,
                "recall_pct": 0.0,
            },
            "all": {
                "label": "合并",
                "high_aspects": 41,
                "precision_pct": RULE_STRICT_PRECISION_PCT,
                "recall_pct": RULE_STRICT_RECALL_PCT,
            },
        },
    }


CSS = """
:root{
  --paper:#faf9f7;--surface:#fff;--surface2:#f3f1ee;--ink:#1f1d1b;--ink2:#5c5752;--ink3:#8a827b;
  --line:#e2ddd7;--line2:#cfc7bf;--brand:#6f4e57;--brand-soft:#f3e9ec;--green:#3f6b57;
  --green-soft:#e8f0eb;--red:#9c4f45;--red-soft:#f7eae7;--amber:#8a6428;--amber-soft:#f6efe1;
  --blue:#3f5f75;--blue-soft:#e9eff4;--radius:14px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased}
.wrap{width:min(1120px,calc(100% - 40px));margin:0 auto}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}
.micro{font-size:12px;color:var(--ink3)}
.muted{color:var(--ink2)}
header.hero{padding:56px 0 36px;border-bottom:1px solid var(--line)}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--brand);font-weight:700}
h1{font-size:clamp(28px,4.2vw,46px);line-height:1.25;letter-spacing:-.02em;margin:14px 0 18px;font-weight:800}
.lede{font-size:17px;color:var(--ink2);max-width:820px}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0}
.badge{font-size:12px;padding:5px 10px;border-radius:999px;background:var(--surface2);border:1px solid var(--line);color:var(--ink2)}
.badge.mode{background:var(--brand-soft);border-color:#e3cfd5;color:var(--brand);font-weight:700}
.badge.blocked{background:var(--red-soft);border-color:#eccfc9;color:var(--red);font-weight:700}
section{padding:46px 0;border-bottom:1px solid var(--line)}
.sec-kicker{font-size:12px;letter-spacing:.12em;color:var(--ink3);font-weight:700;text-transform:uppercase}
h2{font-size:clamp(22px,2.6vw,30px);line-height:1.35;letter-spacing:-.015em;margin:10px 0 12px;font-weight:800;max-width:900px}
h3{font-size:18px;margin:26px 0 10px}
p{margin:10px 0}
.claim{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:24px 26px;margin:22px 0;
  box-shadow:0 6px 24px rgba(40,30,26,.04)}
.claim-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.grade{font-size:11px;font-weight:800;letter-spacing:.05em;padding:4px 9px;border-radius:999px;text-transform:uppercase}
.g-confirmed{background:var(--green-soft);color:var(--green);border:1px solid #cfe0d6}
.g-directional{background:var(--blue-soft);color:var(--blue);border:1px solid #cfdde7}
.g-hypothesis{background:var(--amber-soft);color:var(--amber);border:1px solid #e8d9ba}
.g-gap{background:var(--surface2);color:var(--ink2);border:1px solid var(--line2)}
.g-blocked{background:var(--red-soft);color:var(--red);border:1px solid #eccfc9}
.g-notauth{background:#efe9f4;color:#5c4770;border:1px solid #ddd0e8}
.claim h2.headline{font-size:20px;font-weight:750;line-height:1.45;margin:0 0 6px;max-width:none}
.grid4{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:16px}
.claim-grade{display:flex;flex-wrap:wrap;gap:8px 22px;margin-top:14px;padding-top:12px;border-top:1px dashed var(--line2);font-size:12px;color:var(--ink2)}
.claim-grade b{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink3);margin-right:7px}
.claim-source{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line2);font-size:12px;color:var(--ink2)}
.claim-source b{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink3);margin-right:7px}
.cell{background:var(--surface2);border-radius:10px;padding:14px 16px}
.cell b{display:block;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink3);margin-bottom:6px}
.cell p{margin:0;font-size:14px}
figure{margin:26px 0 0;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:22px 24px}
figcaption{font-weight:750;font-size:17px;line-height:1.45;margin-bottom:6px}
figcaption .ex{font-size:11px;letter-spacing:.12em;color:var(--brand);font-weight:800;margin-right:8px}
.figure-note{font-size:13px;color:var(--ink2);margin:2px 0 16px}
.bars{display:flex;flex-direction:column;gap:9px;margin:14px 0 6px}
.bar-row{display:grid;grid-template-columns:150px 1fr 1fr 58px;gap:10px;align-items:center;font-size:13px}
.bar-row .lab{color:var(--ink2);text-align:right}
.track{height:14px;background:var(--surface2);border-radius:4px;position:relative;overflow:hidden}
.track .fill{position:absolute;top:0;bottom:0;border-radius:4px}
.fill.neg{right:0;background:var(--red)}
.fill.pos{left:0;background:var(--green)}
.axis{height:1px;background:var(--line2);margin:4px 0}
.meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:16px;border-top:1px dashed var(--line2);padding-top:12px}
.meta div{font-size:12px;color:var(--ink2)}
.meta b{display:block;color:var(--ink3);font-size:10px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:3px}
.recon{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:18px 0}
.recon .step{background:var(--surface2);border-radius:10px;padding:14px;text-align:center;position:relative}
.recon .n{font-size:26px;font-weight:800;line-height:1.1}
.recon .t{font-size:11px;color:var(--ink3);margin-top:4px}
.recon .d{font-size:11px;color:var(--red);margin-top:5px}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:13.5px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink3);font-weight:700}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;font-size:11px;padding:2px 7px;border-radius:999px;background:var(--surface2);border:1px solid var(--line);color:var(--ink2)}
.pill.red{background:var(--red-soft);color:var(--red);border-color:#eccfc9}
.pill.green{background:var(--green-soft);color:var(--green);border-color:#cfe0d6}
.pill.amber{background:var(--amber-soft);color:var(--amber);border-color:#e8d9ba}
.note{border-left:3px solid var(--brand);background:var(--brand-soft);padding:12px 16px;border-radius:0 10px 10px 0;font-size:14px;margin:18px 0}
.forbidden{background:var(--red-soft);border:1px solid #eccfc9;border-radius:var(--radius);padding:22px 24px}
.forbidden ul{margin:8px 0 0;padding-left:20px}
.forbidden li{margin:5px 0}
details.forbidden-zone{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px 24px;margin-top:26px}
details.forbidden-zone summary{cursor:pointer;font-size:17px;font-weight:800;color:var(--brand);list-style:none}
details.forbidden-zone summary::-webkit-details-marker{display:none}
details.forbidden-zone summary::before{content:"▸ ";font-weight:800}
details.forbidden-zone[open] summary::before{content:"▾ "}
details.forbidden-zone table{font-size:12.5px}
details.forbidden-zone td{color:var(--ink2)}
.forbidden-tail{padding:28px 0 10px;border-bottom:none}
.fc-cite{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;background:var(--red-soft);border:1px solid #eccfc9;color:var(--red);font-weight:700}
.cols2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px}
.card h4{margin:0 0 8px;font-size:15px}
.stack{display:flex;flex-direction:column;gap:6px}
.mini{font-size:12.5px;color:var(--ink2)}
.tag{font-size:11px;color:var(--ink3);border:1px solid var(--line);border-radius:6px;padding:2px 6px;margin-right:5px}
footer{padding:36px 0 60px;font-size:12px;color:var(--ink3)}
@media(max-width:820px){
  .grid4,.cols2,.meta{grid-template-columns:1fr}
  .recon{grid-template-columns:1fr 1fr}
  .bar-row{grid-template-columns:110px 1fr 1fr 44px}
}
"""


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def fmt_int(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return esc(n)


def grade_badge(claim: Claim) -> str:
    return f'<span class="grade {GRADE_CLASS.get(claim.grade.value, "g-gap")}">{esc(claim.grade.value)}</span>'


def _counts_text(claim: Claim) -> str:
    """The three counts every claim publishes; a missing count is UNKNOWN.

    ``agreement_pct=None`` means the claim is a count fact, not a direction
    claim, so the renderer prints ``N/A`` instead of inventing a percentage.
    """
    counts = claim.counts or {}
    values = []
    for key in ("n_records", "n_authors", "agreement_pct"):
        value = counts.get(key)
        if key == "agreement_pct" and value is None:
            values.append("N/A")
        elif value is None:
            values.append("UNKNOWN")
        elif key == "agreement_pct" and isinstance(value, (int, float)):
            values.append(f"{value:g}%")
        else:
            values.append(str(value))
    return (
        f"n_records={values[0]} · n_authors={values[1]} · agreement={values[2]}"
    )


CLAIM_SOURCE_SPEC: dict[str, dict[str, str]] = {
    "C01": {
        "primary": "amazon_pdp",
        "kind": "artifact",
        "reason": "Amazon PDP 身份抓取，不经过 LLM 编码",
    },
    "C02": {
        "primary": "mixed",
        "kind": "counting",
        "reason": "全语料计数（Reddit + TikTok Shop），不依赖编码精度",
    },
    "C03": {
        "primary": "reddit",
        "kind": "coded",
        "reason": "Reddit 关键词召回的 product_match 记录",
    },
    "C11": {
        "primary": "reddit",
        "kind": "coded",
        "reason": "Reddit 关键词召回的 journey/outcome 标注",
    },
    "C04": {
        "primary": "reddit",
        "kind": "coded",
        "reason": "natural frame 本人使用体验（全部来自 Reddit）",
    },
    "C05": {
        "primary": "reddit",
        "kind": "coded",
        "reason": "natural frame 共现记录（全部来自 Reddit）",
    },
    "C07": {
        "primary": "none",
        "kind": "gate",
        "reason": "G7 gate 状态，不依赖编码",
    },
    "C08": {
        "primary": "mixed",
        "kind": "coded",
        "reason": "medical self-report 标注",
    },
    "C10": {
        "primary": "none",
        "kind": "gate",
        "reason": "报告级限制，不依赖编码",
    },
    "C12": {
        "primary": "tiktok_shop",
        "kind": "counting",
        "reason": "TikTok Shop 采集账本计数，不依赖编码精度",
    },
    "C13": {
        "primary": "tiktok_shop",
        "kind": "coded",
        "reason": "TikTok Shop SUP.* aspect 编码",
    },
    "C14": {
        "primary": "tiktok_shop",
        "kind": "rule",
        "reason": "TikTok Shop quarantine 规则判定，不依赖编码精度",
    },
    "C15": {
        "primary": "tikhub_video",
        "kind": "artifact",
        "reason": "TikHub 视频搜索、详情与达人档案的关联产物",
    },
    "C16": {
        "primary": "tikhub_video",
        "kind": "derived",
        "reason": "视频层互动基线的分层统计",
    },
    "C17": {
        "primary": "tikhub_video",
        "kind": "derived",
        "reason": "高表现视频的共同特征计数",
    },
    "C18": {
        "primary": "tikhub_video",
        "kind": "derived",
        "reason": "内容形态字段可用性与关联缺口",
    },
}


def build_claim_source_profiles(
    claims: list[Claim],
    records: list[Any] | None = None,
    coded: list[Any] | None = None,
    corpus: dict[str, Any] | None = None,
    precision: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Attach a source dependency and a confidence label to each claim.

    The mapping is a rendering contract, not a grading rule: no claim grade
    changes here.  Counts come from the claim's own ``numbers`` block and from
    the canonical records, so the table cannot drift from the artifacts.
    """
    source_by_id = {r.canonical_id: r.source for r in (records or [])}
    medical_sources = Counter(
        source_by_id.get(c.canonical_id, "unknown")
        for c in (coded or [])
        if getattr(c, "medical_flags", None)
    )
    canonical_by_source = (corpus or {}).get("canonical_by_source") or {}
    profiles: dict[str, dict[str, Any]] = {}
    for claim in claims:
        spec = CLAIM_SOURCE_SPEC.get(
            claim.claim_id,
            {"primary": "unknown", "kind": "unknown", "reason": "未声明信源"},
        )
        primary = spec["primary"]
        kind = spec["kind"]
        numbers = claim.numbers or {}
        sources: dict[str, int] = {}
        if claim.claim_id == "C01":
            sources = {"amazon_pdp": 1}
        elif claim.claim_id == "C02":
            sources = {k: int(v) for k, v in canonical_by_source.items()}
        elif claim.claim_id == "C08":
            sources = dict(medical_sources)
        elif claim.claim_id == "C11":
            sources = {"reddit": int(numbers.get("relevant_records", 0) or 0)}
        elif claim.claim_id == "C04":
            sources = {"reddit": int(numbers.get("friction_records", 0) or 0)}
        elif claim.claim_id == "C05":
            sources = {"reddit": int(numbers.get("comfort_positive_records", 0) or 0)}
        elif claim.claim_id == "C03":
            sources = {"reddit": int(numbers.get("momcozy_records", 0) or 0)}
        elif claim.claim_id == "C12":
            sources = {"tiktok_shop": int(numbers.get("canonical_records", 0) or 0)}
        elif claim.claim_id == "C13":
            sources = {"tiktok_shop": int(numbers.get("support_decisive", 0) or 0)}
        elif claim.claim_id == "C14":
            sources = {"tiktok_shop": int(numbers.get("quarantined_records", 0) or 0)}
        elif claim.claim_id in {"C15", "C16", "C17", "C18"}:
            sources = {"tikhub_video": int(numbers.get("videos_total", 0) or 0)}
        total = sum(sources.values())
        reddit_share = (sources.get("reddit", 0) / total) if total else 0.0
        coded_claim = kind == "coded"
        profiles[claim.claim_id] = {
            "primary": primary,
            "kind": kind,
            "reason": spec["reason"],
            "sources": sources,
            "coded": coded_claim,
            "low_confidence": bool(coded_claim and reddit_share >= 0.5),
            "reddit_share": round(reddit_share, 3) if total else 0.0,
        }
    return profiles


def _precision_sources(precision: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return (precision or _fallback_precision()).get("sources") or {}


def _gold_abstentions(precision: dict[str, Any] | None) -> tuple[int, int, float]:
    """Gold-set abstention counts for the hero copy.

    v1 carries them in the frozen constants.  A v2 eval file may supply its own
    block, because the confidence gate drops a different number of aspects on
    the same 50 gold records.  A malformed block falls back to v1 rather than
    rendering a broken sentence.
    """
    block = (precision or {}).get("gold_set_abstentions") or {}
    try:
        return (
            int(block["abstained_aspects"]),
            int(block["coder_aspects"]),
            float(block["abstention_share_pct"]),
        )
    except (KeyError, TypeError, ValueError):
        return (
            LLM_HIGH_ONLY_ABSTENTIONS_GOLD,
            LLM_ALL_MODE_CODER_ASPECTS_GOLD,
            LLM_HIGH_ONLY_ABSTENTION_SHARE_PCT,
        )


def _inherited_precision_note(precision: dict[str, Any] | None) -> str:
    """Say out loud when a v2 report inherits the v1 precision table.

    A v2 artifact with no human gold must not present v1's measured numbers as
    if they described v2 coding.  The eval file carries the verification block;
    this helper turns it into one visible sentence.
    """
    verification = (precision or {}).get("verification") or {}
    if verification.get("status") != "unverified_inherited_from_v1":
        return ""
    return (
        " 本报告为 v2 编码；v2 未做人工 gold 评测，上述精度数字沿用 v1，"
        "标注为未验证，不能作为 v2 的精度证据。"
    )


def _precision_verdict(source: str, precision: dict[str, Any] | None) -> tuple[str, str]:
    """Verdict and pill class for one row of the split precision table."""
    rows = _precision_sources(precision)
    row = rows.get(source) or {}
    pct = float(row.get("precision_pct") or 0.0)
    if source == "tiktok_shop":
        return (
            ("达到门槛" if pct >= PRECISION_THRESHOLD_PCT else "未达门槛"),
            "green" if pct >= PRECISION_THRESHOLD_PCT else "red",
        )
    if source == "reddit":
        if int(row.get("high_aspects") or 0) == 0:
            return ("无输出", "red")
        return ("不足以编码（样本过小）", "red")
    if source == "all":
        tiktok_pct = float((rows.get("tiktok_shop") or {}).get("precision_pct") or 0.0)
        reddit_pct = float((rows.get("reddit") or {}).get("precision_pct") or 0.0)
        if tiktok_pct >= PRECISION_THRESHOLD_PCT > reddit_pct:
            return ("合并值会同时高估 Reddit、低估 TikTok", "amber")
        return ("合并值只作对照，不作为采信依据", "amber")
    return ("不适用", "")


def _precision_aspect_word(precision: dict[str, Any] | None) -> str:
    p = precision or _fallback_precision()
    return "high aspect" if p.get("gate") == "high" else "aspect"


def precision_source_table(precision: dict[str, Any] | None = None) -> str:
    """Three-row precision table: each source, then the merged comparison row."""
    p = precision or _fallback_precision()
    aspect_word = _precision_aspect_word(p)
    rows = []
    for source in ("tiktok_shop", "reddit", "all"):
        row = (p.get("sources") or {}).get(source) or {}
        if not row:
            continue
        verdict, pill = _precision_verdict(source, p)
        rows.append(
            f'<tr data-source="{esc(source)}" data-precision="{float(row["precision_pct"]):.1f}"'
            f' data-high-aspects="{int(row["high_aspects"])}">'
            f'<td>{esc(row.get("label", SOURCE_LABELS.get(source, source)))}</td>'
            f'<td class="num">{int(row["high_aspects"])}</td>'
            f'<td class="num">{float(row["precision_pct"]):.1f}%</td>'
            f'<td class="num">{float(row["recall_pct"]):.1f}%</td>'
            f'<td><span class="pill {pill}">{esc(verdict)}</span></td></tr>'
        )
    gate_label = "high-only" if p.get("gate") == "high" else "all aspects"
    return (
        '<table data-precision-table="source-split">'
        f"<thead><tr><th>信源</th><th class='num'>{aspect_word} 数</th>"
        "<th class='num'>strict precision</th><th class='num'>strict recall</th>"
        "<th>该不该采信</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        f"<div class='micro'>{esc(gate_label)}、strict code+polarity；"
        "gold set 本身也是 LLM 标注，这些是单编码对 gold 的 precision，"
        "不是人工双盲 agreement，也不是人工准确率。"
        "合并行只作对照，不作为任何 claim 的采信依据。"
        f"{esc(_inherited_precision_note(p))}</div>"
    )


def _cross_model_numbers(cross_model: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize the calibration artifact for rendering; None means not run."""
    if not cross_model:
        return None
    fleiss = cross_model.get("fleiss_all") or {}
    by_source = cross_model.get("fleiss_by_source") or {}
    consensus = cross_model.get("consensus") or {}
    kappa = fleiss.get("kappa")
    if kappa is None:
        return None
    strong = int(consensus.get("strong") or 0)
    weak = int(consensus.get("weak") or 0)
    disagreement = int(consensus.get("disagreement") or 0)
    annotated = strong + weak + disagreement
    return {
        "kappa": float(kappa),
        "tiktok_kappa": float((by_source.get("TikTok") or {}).get("kappa") or 0.0),
        "reddit_kappa": float((by_source.get("Reddit") or {}).get("kappa") or 0.0),
        "strong": strong,
        "annotated": annotated,
        "strong_share_pct": (100.0 * strong / annotated) if annotated else 0.0,
        "n_items": int(cross_model.get("n_items") or 0),
        "n_cells": int(cross_model.get("n_cells") or 0),
        "prevalence_pct": float(fleiss.get("prevalence") or 0.0) * 100.0,
    }


def evidence_basis_table(
    precision: dict[str, Any] | None = None,
    cross_model: dict[str, Any] | None = None,
) -> str:
    """Three-row evidence basis: LLM-vs-gold, same-model multi-prompt, human validation.

    The rows must stay separate.  The gold row is self-证 (LLM labels checked
    against an LLM-built gold set); the second row is same-model agreement
    under different identity prompts, not independent model agreement; the
    human row is still missing while G7 is blocked.  None of the three is a
    human accuracy estimate.
    """
    p = precision or _fallback_precision()
    rows = _precision_sources(p)
    tiktok_pct = float((rows.get("tiktok_shop") or {}).get("precision_pct") or 0.0)
    reddit_pct = float((rows.get("reddit") or {}).get("precision_pct") or 0.0)
    all_pct = float((rows.get("all") or {}).get("precision_pct") or 0.0)
    gate_label = "high-only" if p.get("gate") == "high" else "all aspects"
    cm = _cross_model_numbers(cross_model)
    if cm:
        cross_numbers = (
            f"Fleiss κ={cm['kappa']:.4f}（ALL；TikTok {cm['tiktok_kappa']:.4f} / "
            f"Reddit {cm['reddit_kappa']:.4f}）；"
            f"强共识 {cm['strong']}/{cm['annotated']} = {cm['strong_share_pct']:.1f}%"
            "（有标注格）"
        )
        cross_meaning = (
            "5 个标注身份（sol / terra / luna / g55 / mini）全部运行在 DeepSeek Flash 同一族"
            "（group/auto-deepseek-flash:max[1m]，实际为 deepseek-flash / deepseek-v4.1-flash），"
            "所以这是同族自一致，不是跨模型独立验证。"
            "它比单次自证多出的信息是：同一模型族在 5 个不同身份提示下仍能稳定复现同一批 aspect 的 present/absent 判断；"
            f"{cm['n_items']} 条 / {cm['n_cells']} 个 item×aspect 格；"
            f"有标注 {cm['annotated']} 格，present 仅 {cm['prevalence_pct']:.1f}%，"
            "κ 主要由共同未标注驱动。它不是独立验证，也不是人工准确率。"
        )
    else:
        cross_numbers = "未做（没有 cross-model artifact）"
        cross_meaning = "同模型多提示一致率未做；不能用它替代人工准确率。"
    cross_agreement = "true" if cm else "false"
    inherited_note = _inherited_precision_note(p)
    gold_label = "LLM vs LLM gold set（旧）" + (" · v2 沿用 v1，未验证" if inherited_note else "")
    gold_meaning = "单模型对自建 gold 的一致性，<b>自证</b>；不是人工准确率。"
    if inherited_note:
        gold_meaning += "本报告是 v2，但 v2 未做人工 gold 评测；该行数字沿用 v1，标注为未验证。"
    return (
        '<table data-cross-model-table="evidence-basis">'
        "<thead><tr><th>证据基础</th><th>数字</th><th>含义</th></tr></thead><tbody>"
        '<tr data-evidence-basis="llm-gold" data-cross-model-agreement="false">'
        f"<td>{gold_label}</td>"
        f"<td>strict precision（{esc(gate_label)}）：TikTok Shop {tiktok_pct:.1f}% / "
        f"Reddit {reddit_pct:.1f}% / ALL {all_pct:.1f}%</td>"
        f"<td>{gold_meaning}</td></tr>"
        f'<tr data-evidence-basis="cross-model" data-cross-model-agreement="{cross_agreement}">'
        "<td>同模型多提示一致率（新）</td>"
        f"<td>{esc(cross_numbers)}</td>"
        f"<td>{esc(cross_meaning)}</td></tr>"
        '<tr data-evidence-basis="human" data-cross-model-agreement="false">'
        "<td>人工验证</td><td><b>未做</b></td>"
        "<td>G7 仍 BLOCKED；没有人工准确率。</td></tr>"
        "</tbody></table>"
        "<div class='micro'>同族自一致不是人工准确率；共识不是 truth oracle。"
        "三行并列是为了区分“单次自证”“同模型多提示稳定性”和“人工验证”，不能互相替代。</div>"
    )


def _source_counts_text(profile: dict[str, Any]) -> str:
    sources = profile.get("sources") or {}
    if not sources:
        return "无编码记录"
    return "、".join(
        f"{SOURCE_LABELS.get(source, source)} {count} 条"
        for source, count in sorted(sources.items(), key=lambda kv: (-kv[1], kv[0]))
    )


def _source_precision_text(profile: dict[str, Any], precision: dict[str, Any] | None) -> str:
    if not profile.get("coded"):
        if profile.get("primary") == "amazon_pdp":
            return "Amazon PDP artifact；不经过 LLM 编码，精度门槛不适用"
        if profile.get("kind") == "gate":
            return "gate / ledger 状态；不经过 LLM 编码，精度门槛不适用"
        reason = profile.get("reason") or "计数或规则来源"
        return f"{reason}；不经过 LLM 编码，精度门槛不适用"
    rows = _precision_sources(precision)
    tiktok = rows.get("tiktok_shop") or {}
    reddit = rows.get("reddit") or {}
    aspect_word = _precision_aspect_word(precision)
    primary = profile.get("primary")
    if primary == "tiktok_shop":
        return (
            f"TikTok Shop strict precision {float(tiktok.get('precision_pct', 0)):.1f}%"
            f"（{int(tiktok.get('high_aspects', 0))} 个 {aspect_word}）"
        )
    if primary == "reddit":
        aspects = int(reddit.get("high_aspects", 0))
        if aspects == 0:
            return "Reddit 无编码输出（0 个 aspect）；precision 不适用"
        return (
            f"Reddit strict precision {float(reddit.get('precision_pct', 0)):.1f}%"
            f"（仅 {aspects} 个 {aspect_word}）"
        )
    share = float(profile.get("reddit_share") or 0.0)
    reddit_aspects = int(reddit.get("high_aspects", 0))
    reddit_basis = (
        f"Reddit {float(reddit.get('precision_pct', 0)):.1f}%（仅 {reddit_aspects} 个 {aspect_word}）"
        if reddit_aspects
        else "Reddit 无编码输出（0 个 aspect）"
    )
    return (
        f"分信源 strict precision：TikTok Shop {float(tiktok.get('precision_pct', 0)):.1f}%"
        f"（{int(tiktok.get('high_aspects', 0))} 个 {aspect_word}）、"
        f"{reddit_basis}；Reddit 占 {share:.0%}"
    )


def claim_source_html(
    claim: Claim,
    profile: dict[str, Any] | None,
    precision: dict[str, Any] | None = None,
) -> str:
    """Visible provenance line: source, precision basis, and trust label."""
    if not profile or profile.get("primary") in (None, "unknown"):
        return (
            '<div class="claim-source" data-source="unknown" data-source-precision=""'
            ' data-low-confidence="unknown"><b>证据来源</b>'
            "UNKNOWN · 精度基准不适用</div>"
        )
    primary = profile["primary"]
    label = SOURCE_LABELS.get(primary, primary)
    precision_text = _source_precision_text(profile, precision)
    if profile.get("low_confidence"):
        pill = '<span class="pill red">低可信</span>'
    elif profile.get("coded") and primary == "tiktok_shop":
        pill = '<span class="pill green">达到门槛</span>'
    elif profile.get("coded") and primary == "mixed":
        pill = '<span class="pill amber">分信源采信</span>'
    else:
        pill = '<span class="pill">精度门槛不适用</span>'
    rows = _precision_sources(precision)
    if primary == "reddit":
        precision_attr = f"{float((rows.get('reddit') or {}).get('precision_pct', 0)):.1f}"
    elif primary == "tiktok_shop":
        precision_attr = f"{float((rows.get('tiktok_shop') or {}).get('precision_pct', 0)):.1f}"
    elif primary == "mixed":
        precision_attr = (
            f"{float((rows.get('tiktok_shop') or {}).get('precision_pct', 0)):.1f}/"
            f"{float((rows.get('reddit') or {}).get('precision_pct', 0)):.1f}"
        )
    else:
        precision_attr = ""
    return (
        f'<div class="claim-source" data-source="{esc(primary)}"'
        f' data-source-precision="{esc(precision_attr)}"'
        f' data-low-confidence="{esc(str(bool(profile.get("low_confidence"))).lower())}">'
        f"<b>证据来源</b>{esc(label)} · {esc(_source_counts_text(profile))} · "
        f"{esc(precision_text)} {pill}</div>"
    )


def claim_source_table(
    claims: list[Claim],
    claim_sources: dict[str, dict[str, Any]] | None,
    precision: dict[str, Any] | None = None,
) -> str:
    """One row per claim: primary source, supporting records, precision, verdict."""
    rows = []
    for claim in claims:
        profile = (claim_sources or {}).get(claim.claim_id) or {
            "primary": "unknown",
            "sources": {},
            "coded": False,
            "low_confidence": False,
            "kind": "unknown",
            "reddit_share": 0.0,
        }
        primary = profile.get("primary", "unknown")
        if profile.get("low_confidence"):
            pill = '<span class="pill red">低可信</span>'
        elif profile.get("coded") and primary == "tiktok_shop":
            pill = '<span class="pill green">达到门槛</span>'
        elif profile.get("coded") and primary == "mixed":
            pill = '<span class="pill amber">分信源采信</span>'
        else:
            pill = '<span class="pill">精度门槛不适用</span>'
        rows.append(
            f'<tr data-claim-id="{esc(claim.claim_id)}" data-source="{esc(primary)}"'
            f' data-low-confidence="{esc(str(bool(profile.get("low_confidence"))).lower())}">'
            f"<td class='mono'>{esc(claim.claim_id)}</td>"
            f"<td>{esc(SOURCE_LABELS.get(primary, primary))}</td>"
            f"<td>{esc(_source_counts_text(profile))}</td>"
            f"<td>{esc(_source_precision_text(profile, precision))}</td>"
            f"<td>{pill}</td></tr>"
        )
    return (
        "<table data-claim-source-table='true'>"
        "<thead><tr><th>claim</th><th>主要信源</th><th>支撑记录</th>"
        "<th>编码精度基础</th><th>采信判断</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def claim_block(
    claim: Claim,
    source: dict[str, Any] | None = None,
    precision: dict[str, Any] | None = None,
) -> str:
    counts_text = _counts_text(claim)
    return f"""
<article class="claim" data-claim-id="{esc(claim.claim_id)}" data-grade="{esc(claim.grade.value)}" data-grade-reason="{esc(claim.grade_reason)}" data-counts="{esc(counts_text)}">
  <div class="claim-head">{grade_badge(claim)}<span class="micro mono">{esc(claim.claim_id)}</span></div>
  <h2 class="headline">{esc(claim.headline)}</h2>
  <div class="grid4">
    <div class="cell"><b>Observed</b><p>{esc(claim.observed)}</p></div>
    <div class="cell"><b>Interpretation</b><p>{esc(claim.interpretation)}</p></div>
    <div class="cell"><b>Counterevidence</b><p>{esc(claim.counterevidence)}</p></div>
    <div class="cell"><b>Decision implication</b><p>{esc(claim.decision)}</p></div>
  </div>
  <div class="claim-grade"><span><b>Grade</b>{esc(claim.grade.value)}</span><span><b>Why this grade</b>{esc(claim.grade_reason)}</span><span class="mono"><b>Counts</b>{esc(counts_text)}</span></div>
  {claim_source_html(claim, source, precision)}
</article>"""


def fc_cite(fc_id: str, label: str) -> str:
    """Inline pointer to the forbidden catalog; never restates the banned shape."""
    return f'<span class="fc-cite" data-fc="{esc(fc_id)}">禁写 {esc(fc_id)} · {esc(label)}</span>'


def forbidden_section() -> str:
    """Collapsed tail block: the contract lives at the bottom, not in the body."""
    rows = "".join(
        f'<tr data-fc-row="{esc(fc.id)}"><td class="mono">{esc(fc.id)}</td>'
        f"<td>{esc(fc.pattern)}</td><td>{esc(fc.why)}</td>"
        f'<td class="mono micro">{esc(fc.detected_by.describe())}</td>'
        f"<td>{esc(fc.ref_origin)}</td></tr>"
        for fc in FORBIDDEN_CONCLUSIONS
    )
    return f"""
<section id="forbidden-conclusions-zone" class="forbidden-tail">
  <details class="forbidden-zone" id="forbidden-conclusions" data-forbidden-count="{len(FORBIDDEN_CONCLUSIONS)}">
    <summary>这份报告不能说的事：{len(FORBIDDEN_CONCLUSIONS)} 类</summary>
    <p class="muted">这是一个可执行契约，不是风格提醒：渲染后 <span class="mono">validate_report</span> 会扫描正文与 <span class="mono">claims.numbers</span>，命中任一规则即 fail closed。正文只在必要处内联引用最关键的 3 条。</p>
    <table>
      <thead><tr><th>ID</th><th>禁止的形态</th><th>为什么禁止</th><th>机器检测</th><th>来源</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <p class="micro">成熟度是状态，不是评分；清单本身不授权任何结论。</p>
  </details>
</section>"""


class ExhibitLog:
    """Registry of exhibits and their missing basis declarations.

    A missing Basis / Unit / Limit / Status is rendered as ``UNKNOWN`` and is
    listed in the report's "未声明口径" block.  The row is never omitted.
    """

    def __init__(self) -> None:
        self.total = 0
        self.undeclared: list[dict[str, Any]] = []

    def register(self, exhibit: str, missing: list[str]) -> None:
        self.total += 1
        if missing:
            self.undeclared.append({"exhibit": exhibit, "missing": missing})

    @property
    def declared(self) -> int:
        return self.total - len(self.undeclared)

    @property
    def coverage_pct(self) -> float:
        return round(100.0 * self.declared / self.total, 1) if self.total else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "exhibits": self.total,
            "declared": self.declared,
            "undeclared": len(self.undeclared),
            "coverage_pct": self.coverage_pct,
        }

    def undeclared_html(self) -> str:
        if not self.undeclared:
            return (
                "<p class='micro'>未声明口径清单为空："
                f"{self.total} 张 exhibit 的 Basis / Unit / Limit / Status 全部已声明。</p>"
            )
        rows = "".join(
            f"<tr><td class='mono'>{esc(u['exhibit'])}</td><td>{esc('、'.join(u['missing']))}</td></tr>"
            for u in self.undeclared
        )
        return (
            "<table><thead><tr><th>exhibit</th><th>缺失字段（按 UNKNOWN 渲染）</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )


def figure(
    exhibit: str,
    title: str,
    note: str,
    body: str,
    *,
    basis: str | None = None,
    unit: str | None = None,
    limit: str | None = None,
    status: str | None = None,
    claim: Claim | None = None,
    log: ExhibitLog | None = None,
) -> str:
    """Render one exhibit with its four-part footnote.

    ``status`` is taken from the associated claim's grade whenever a claim is
    supplied; a hand-written status is not accepted as a substitute.  Any of
    the four declarations that is empty is rendered as ``UNKNOWN`` and counted
    in the report's undeclared-basis list.
    """
    declared: dict[str, str | None] = {"Basis": basis, "Unit": unit, "Limit": limit, "Status": status}
    if claim is not None:
        declared["Status"] = claim.grade.value
    missing = [name for name, value in declared.items() if value is None or not str(value).strip()]
    for name in missing:
        declared[name] = "UNKNOWN"
    if log is not None:
        log.register(exhibit, missing)
    claim_attr = f' data-claim-id="{esc(claim.claim_id)}"' if claim is not None else ""
    return f"""
<figure data-exhibit="{esc(exhibit)}"{claim_attr} data-basis="{esc(declared['Basis'])}" data-unit="{esc(declared['Unit'])}" data-limit="{esc(declared['Limit'])}" data-status="{esc(declared['Status'])}">
  <figcaption><span class="ex">{esc(exhibit)}</span>{esc(title)}</figcaption>
  <div class="figure-note">{esc(note)}</div>
  {body}
  <div class="meta">
    <div><b>Basis</b>{esc(declared['Basis'])}</div>
    <div><b>Unit</b>{esc(declared['Unit'])}</div>
    <div><b>Limit</b>{esc(declared['Limit'])}</div>
    <div><b>Status</b>{esc(declared['Status'])}</div>
  </div>
</figure>"""


def _num(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pct(value: Any, digits: int = 2) -> str:
    try:
        return f"{100.0 * float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return "UNKNOWN"


def _multiple(value: Any) -> str:
    try:
        return f"{float(value):.2f}x"
    except (TypeError, ValueError):
        return "UNKNOWN"


def _p_value(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "UNKNOWN"


def _ci_text(ci: Any) -> str:
    try:
        return f"[{float(ci[0]):.2f}, {float(ci[1]):.2f}]"
    except (TypeError, ValueError, IndexError):
        return "UNKNOWN"


def _cv_population_table(cv: dict[str, Any]) -> str:
    confidence = cv.get("relation_confidence") or {}
    relation_types = cv.get("relation_types") or {}
    rows = [
        ("唯一视频", cv.get("videos_total"), "video_id 去重"),
        ("有详情快照", cv.get("videos_with_detail"), "fetch_post_detail"),
        ("只有搜索快照", cv.get("videos_search_only"), "fetch_video_search_result"),
        ("唯一达人", cv.get("creators_total"), "author uid 去重"),
        ("有达人档案", cv.get("creators_with_profile"), "fetch_user_profile"),
        ("high 关联", confidence.get("high"), "anchor product_id == 目标商品"),
        ("medium 关联", confidence.get("medium"), "重复 listing 锚点或文案品牌+品类"),
        ("low 关联", confidence.get("low"), "只命中品类或话题"),
        ("no_signal", confidence.get("none"), "没有商品信号"),
        ("进入基线", cv.get("baseline_n"), "high + medium"),
        ("目标商品 exact", cv.get("target_exact_n"), "anchor product_id == 目标商品"),
        ("基线 target_exact", relation_types.get("target_exact"), "锚点精确命中"),
        ("基线 duplicate_listing_anchor", relation_types.get("duplicate_listing_anchor"), "同品牌同系列的其他 listing；product_id 不同"),
        ("基线 text_brand_and_category", relation_types.get("text_brand_and_category"), "文案品牌+品类，无锚点"),
    ]
    body = "".join(
        f"<tr><td>{esc(label)}</td><td class='num'>{fmt_int(value)}</td>"
        f"<td>{esc(note)}</td></tr>"
        for label, value, note in rows
    )
    return (
        "<table><thead><tr><th>类别</th><th class='num'>数量</th><th>判定</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _cv_layer_table(cv: dict[str, Any]) -> str:
    dimension_labels = {
        "duration_bucket": "时长档",
        "has_link": "购买链接",
        "ad_disclosure": "广告披露",
    }
    rows: list[str] = []
    excluded: list[str] = []
    for dimension, label in dimension_labels.items():
        layer = (cv.get("layers") or {}).get(dimension) or {}
        for name, group in (layer.get("groups") or {}).items():
            if group.get("status") != "ok":
                excluded.append(f"{label}/{name} n={fmt_int(group.get('n'))}（{group.get('status')}）")
                continue
            rows.append(
                "<tr>"
                f"<td>{esc(label)}</td><td>{esc(name)}</td>"
                f"<td class='num'>{fmt_int(group.get('n'))}</td>"
                f"<td class='num'>{fmt_int(group.get('play_median'))}</td>"
                f"<td class='num'>{_pct(group.get('interaction_median'))}</td>"
                f"<td class='num'>{_pct(group.get('complement_median'))}</td>"
                f"<td class='num'>{_multiple(group.get('multiple'))}</td>"
                f"<td class='num'>{_p_value(group.get('p_value'))}</td>"
                f"<td class='mono'>{_ci_text(group.get('ci95'))}</td>"
                "</tr>"
            )
    if not rows:
        return "<p class='muted'>没有 n>=8 的层，不能计算分层基线。</p>"
    note = (
        "<div class='micro'>只列 status=ok（n>=8）的层。"
        + (f"未列层：{esc('；'.join(excluded))}。" if excluded else "")
        + (
            "comparison 与 demo 没有 n>=8 的层，不进入本表。"
            if {"comparison", "demo"} & set((cv.get("layers") or {}).keys())
            else ""
        )
        + "同一视频可出现在多个维度中，各层不能相加；unknown 不进入分母。</div>"
    )
    return (
        "<table><thead><tr><th>维度</th><th>层</th><th class='num'>n</th>"
        "<th class='num'>播放中位</th><th class='num'>互动率中位</th>"
        "<th class='num'>补充组中位</th><th class='num'>倍数</th>"
        "<th class='num'>p</th><th>95% CI</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>{note}"
    )


def _cv_high_performer_table(cv: dict[str, Any]) -> str:
    hp = cv.get("high_performers") or {}
    hp_n = _num(hp.get("n"))
    rows = []
    for row in hp.get("rows") or []:
        low = "是" if row.get("low_denominator_flag") else "否"
        relation = f"{row.get('relation_confidence')}/{row.get('relation_type')}"
        rows.append(
            "<tr>"
            f"<td class='mono'>{esc(row.get('video_id'))}</td>"
            f"<td>{esc(row.get('duration_bucket'))}</td>"
            f"<td class='num'>{fmt_int(row.get('play_count'))}</td>"
            f"<td class='num'>{_pct(row.get('interaction_rate'))}</td>"
            f"<td class='num'>{_multiple(row.get('multiple'))}</td>"
            f"<td class='mono micro'>{esc(relation)}</td>"
            f"<td>{esc(row.get('has_link'))}</td>"
            f"<td>{esc(row.get('ad_disclosure'))}</td>"
            f"<td>{low}</td></tr>"
        )
    if not rows:
        return "<p class='muted'>没有高表现视频。</p>"
    feature_labels = {
        "duration_bucket": "时长档",
        "has_link": "购买链接",
        "ad_disclosure": "广告披露",
        "platform_is_ad": "平台广告标记",
        "relation_confidence": "关联置信度",
        "relation_type": "关联类型",
    }
    feature_rows = "".join(
        "<tr>"
        f"<td>{esc(feature_labels.get(row.get('field'), row.get('field')))}</td>"
        f"<td>{esc(row.get('value'))}</td>"
        f"<td class='num'>{fmt_int(row.get('count'))}/{hp_n}</td>"
        f"<td class='num'>{_pct(row.get('share_high'), 1)}</td>"
        f"<td class='num'>{fmt_int(row.get('population_count'))}/{fmt_int(cv.get('baseline_n'))}</td>"
        f"<td class='num'>{_pct(row.get('share_population'), 1)}</td>"
        "</tr>"
        for row in hp.get("common_features") or []
    )
    return (
        "<table><thead><tr><th>video_id</th><th>时长档</th><th class='num'>播放</th>"
        "<th class='num'>互动率</th><th class='num'>档内倍数</th><th>关联</th>"
        "<th>链接</th><th>广告披露</th><th>低播放</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "<h3>共同特征计数：高表现组与全池对照</h3>"
        "<table><thead><tr><th>特征</th><th>取值</th><th class='num'>高表现组</th>"
        "<th class='num'>高表现占比</th><th class='num'>全池</th>"
        "<th class='num'>全池占比</th></tr></thead>"
        f"<tbody>{feature_rows}</tbody></table>"
        "<div class='micro'>只做共现计数，不做因果解释；unknown 行不列出，"
        "unknown 计数见 C18。每行占比要与全池同值占比对照。</div>"
    )


def creator_video_section(
    cv: dict[str, Any] | None,
    cb: Any,
    claim_by_id: dict[str, Claim],
    log: ExhibitLog | None = None,
) -> str:
    """Render the creator/video snapshot section.

    The lead claim is C16: the video layer can compute a layered baseline, but
    no content form passes the support gate.  C15, C17 and C18 carry the
    population, high-performer and field-availability facts.  When the
    artifacts are missing, only the C15 gap claim is rendered.
    """
    if not cv or not cv.get("available"):
        expected = (cv or {}).get("expected_paths") or {}
        expected_text = "、".join(f"<span class='mono'>{esc(v)}</span>" for v in expected.values())
        return f"""
<section id="creator-video">
  <div class="sec-kicker">05 / Creator video snapshot</div>
  {cb("C15")}
  <div class="note"><b>证据缺口：</b>没有 creator/video 快照产物。
  期望路径：{expected_text or 'creator-video/baseline/baseline.json'}。
  视频层问题不能用评论层代替。</div>
</section>"""

    hp = cv.get("high_performers") or {}
    hp_n = _num(hp.get("n"))
    threshold = _num(hp.get("threshold_multiple")) or 2
    gap_items = "".join(f"<li>{esc(item)}</li>" for item in cv.get("gaps") or [])
    baseline_n = _num(cv.get("baseline_n"))
    baseline_medium = _num(cv.get("baseline_medium_n"))
    target_exact = _num(cv.get("target_exact_n"))
    return f"""
<section id="creator-video">
  <div class="sec-kicker">05 / Creator video snapshot</div>
  <p class="muted">视频层与评论层是两个总体：视频以 video_id 为单位，商品评论以 review_id 为单位。两层没有可用关联键，不合并分母。</p>
  <p class="micro">口径：视频层不进入六级 consumer 计数链。Directional 的定义是同一 frame 内的方向一致度；本节是组间对比，不能借用 Directional。对比支持门槛未通过时，按 Evidence gap 记录。</p>
  {cb("C16")}
  {cb("C15")}
  {figure(
      "EXHIBIT 07",
      f"{fmt_int(cv.get('videos_total'))} 条唯一视频里只有 {baseline_n} 条进入高/中置信商品关联基线，{target_exact} 条锚定目标商品。",
      "视频、达人与商品关联各自计数；medium 关联包含重复 listing 锚量与文案品牌+品类两种证据。",
      _cv_population_table(cv),
      claim=claim_by_id["C15"],
      basis=(
          "creator-video/relations/coverage.json + baseline/baseline.json；分母 = "
          f"{fmt_int(cv.get('videos_total'))} 条唯一视频"
      ),
      unit="video / creator（video_id 与 creator_id 去重）",
      limit="关键词搜索非概率样本；单次快照",
      log=log,
  )}
  {figure(
      "EXHIBIT 08",
      "三个维度各有 n>=8 的层，但没有一层的 bootstrap 95% CI 排除 1。",
      "互动率 =（点赞+评论+分享+收藏）/ 播放；中位数按层内视频计算，补充组是同维度其余可判值。",
      _cv_layer_table(cv),
      claim=claim_by_id["C16"],
      basis=(
          "creator-video/baseline/baseline.json layers；分母 = 各层 n 条视频（只列 n>=8）；"
          "补充组 = 同维度其余可判值"
      ),
      unit="video（互动率 =（点赞+评论+分享+收藏）/ 播放）",
      limit=(
          f"medium 关联占 {baseline_medium}/{baseline_n}；维度之间重叠，不能相加；单次快照"
      ),
      log=log,
  )}
  {cb("C17")}
  {figure(
      "EXHIBIT 09",
      f"{hp_n} 条视频达到自身时长档 {threshold} 倍中位互动率，其中 {fmt_int(hp.get('low_play_n'))} 条播放低于 5000。",
      "高表现定义是档内互动率 >= 2 倍中位数；共同特征只做共现计数。",
      _cv_high_performer_table(cv),
      claim=claim_by_id["C17"],
      basis=(
          "creator-video/baseline/baseline.json high_performers.videos；分母 = "
          f"{hp_n} 条高表现视频（时长档内 >= {threshold} 倍中位数）"
      ),
      unit="video",
      limit=f"{hp_n} 条不是总体；高表现定义是档内 {threshold} 倍中位数",
      log=log,
  )}
  {cb("C18")}
  <div class="note"><b>证据缺口（显式，不用相邻数据代替）：</b><ul>{gap_items}</ul></div>
  <p class="micro">口径提醒：内容形态标签是派生编码，不是厂商字段；本节只报告相关性与计数，不写因果。</p>
</section>"""



    items = []
    for code, counts in polarity.items():
        pos = counts.get("positive", 0)
        neg = counts.get("negative", 0)
        if pos + neg == 0:
            continue
        items.append((code, pos, neg, pos + neg))
    items.sort(key=lambda x: (-x[2], -x[3], x[0]))
    return items[:limit]


def _bar_items(polarity: dict[str, dict[str, int]], limit: int = 10) -> list[tuple[str, int, int, int]]:
    items = []
    for code, counts in polarity.items():
        pos = counts.get("positive", 0)
        neg = counts.get("negative", 0)
        if pos + neg == 0:
            continue
        items.append((code, pos, neg, pos + neg))
    items.sort(key=lambda x: (-x[2], -x[3], x[0]))
    return items[:limit]


def _polarity_peak(polarity: dict[str, dict[str, int]], limit: int = 10) -> int:
    """Largest single bar in the rendered figure; bar widths normalise to this."""
    return max((max(p, n) for _, p, n, _ in _bar_items(polarity, limit)), default=1) or 1


def diverging_bars(polarity: dict[str, dict[str, int]], limit: int = 10) -> str:
    items = _bar_items(polarity, limit)
    peak = max((max(p, n) for _, p, n, _ in items), default=1) or 1
    rows = []
    for code, pos, neg, _ in items:
        wneg = (neg / peak) * 100
        wpos = (pos / peak) * 100
        rows.append(
            f'<div class="bar-row"><div class="lab">{esc(LABELS.get(code, code))} '
            f'<span class="micro mono">{esc(code)}</span></div>'
            f'<div class="track"><div class="fill neg" style="width:{wneg:.1f}%"></div></div>'
            f'<div class="track"><div class="fill pos" style="width:{wpos:.1f}%"></div></div>'
            f'<div class="mono micro">−{neg} / +{pos}</div></div>'
        )
    return (
        '<div class="bars">'
        '<div class="bar-row"><div class="lab micro">负向 ←</div><div class="track"></div>'
        '<div class="track"></div><div class="micro">合计</div></div>'
        + "".join(rows)
        + "</div>"
        + '<div class="micro">按 negative annotation hits 排序；左侧为负向、右侧为正向。'
        f"条宽按图内最大单项值 {peak} 归一，不是占比、不是记录数，也不构成净分。</div>"
    )


def reconciliation_chain(corpus: dict[str, Any], metric: dict[str, Any]) -> str:
    steps = [
        ("raw object", corpus["raw_objects"], f"{corpus.get('raw_responses', '?')} 个响应"),
        ("occurrence", corpus["occurrences_deduplicated"], f"−{corpus['within_frame_overlap_dropped']} 同 frame 重复"),
        ("canonical", corpus["canonical_records"], f"−{corpus['reconciliation']['occurrences_to_canonical']} 按 reason code 扣减"),
        ("membership", corpus["frame_memberships"], f"+{corpus['frame_memberships'] - corpus['canonical_records']} 跨 frame"),
        ("metric row", len(metric["metric_rows"]), "G7 未执行"),
    ]
    cells = "".join(
        f'<div class="step"><div class="n">{fmt_int(n)}</div><div class="t">{esc(name)}</div>'
        f'<div class="d">{esc(d)}</div></div>'
        for name, n, d in steps
    )
    return f'<div class="recon">{cells}</div>'


def chain_table(chain: dict[str, Any]) -> str:
    """Six-level count table for one frame; every decrease carries a code."""
    if not chain:
        return "<p class='muted'>该 frame 没有可展示的计数链。</p>"
    annotation_ded = chain["annotation"]["record_deductions"]
    rows = [
        ("raw object", chain["raw_object"]["count"], chain["raw_object"]["note"]),
        (
            "occurrence",
            chain["occurrence"]["count"],
            "duplicate_external_id " + str(chain["occurrence"]["deductions"]["duplicate_external_id"]),
        ),
        (
            "canonical",
            chain["canonical"]["count"],
            "product_mismatch " + str(chain["canonical"]["deductions"]["product_mismatch"])
            + "、out_of_window " + str(chain["canonical"]["deductions"]["out_of_window"]),
        ),
        ("frame membership", chain["frame_membership"]["count"], chain["frame_membership"]["note"]),
        (
            "annotation",
            chain["annotation"]["count"],
            "no_text_low_information " + str(annotation_ded["no_text_low_information"])
            + "、language_uncodable " + str(annotation_ded["language_uncodable"])
            + "、no_decisive_aspect " + str(annotation_ded["no_decisive_aspect"]),
        ),
        ("metric row", chain["metric_row"]["count"], chain["metric_row"]["reason"]),
    ]
    body = "".join(
        f"<tr><td>{esc(level)}</td><td class='num'>{fmt_int(count)}</td><td>{esc(note)}</td></tr>"
        for level, count, note in rows
    )
    return (
        "<table><thead><tr><th>层级</th><th class='num'>计数</th><th>扣减 / reason code</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _c13_hero_clause(grade: EvidenceGrade) -> str:
    """Hero sentence for the direction claim, rendered from its computed grade.

    The rule-coder hero is static prose, but the grade it names is not: a run
    whose direction agreement falls below 70% must not keep saying the claim
    reached Directional while its badge says Supported hypothesis.
    """
    if grade is EvidenceGrade.DIRECTIONAL:
        return "verified-purchase 评论把支撑方向抬到 Directional"
    if grade is EvidenceGrade.SUPPORTED_HYPOTHESIS:
        return (
            "verified-purchase 评论未达 Directional 门槛，"
            "支撑方向按 Supported hypothesis 记录"
        )
    return f"verified-purchase 评论的支撑方向档位为 {grade.value}"


def render_report(
    out_path: Path,
    *,
    generated_at: str,
    identity: dict[str, Any],
    corpus: dict[str, Any],
    metric: dict[str, Any],
    claims: list[Claim],
    gate_status: dict[str, str],
    run_id: str,
    recommendations: list[dict[str, Any]] | None = None,
    coder_id: str = "llm-v1",
    precision: dict[str, Any] | None = None,
    cross_model: dict[str, Any] | None = None,
    claim_sources: dict[str, dict[str, Any]] | None = None,
    creator_video: dict[str, Any] | None = None,
) -> Path:
    claim_by_id = {c.claim_id: c for c in claims}
    if precision is None:
        precision = _rule_precision() if coder_id == "rule-v1" else _fallback_precision()
    claim_sources = claim_sources or build_claim_source_profiles(claims)

    def cb(claim_id: str) -> str:
        return claim_block(claim_by_id[claim_id], claim_sources.get(claim_id), precision)

    recommendations = recommendations or []
    child = identity.get("asins", ["B0HC2FG4QC"])[-1]
    product = identity.get("products", {}).get(child, {})
    variants = product.get("variants", {})
    variant_rows = "".join(
        f"<tr><td class='mono'>{esc(asin)}</td><td>{esc(v[0] if len(v) > 0 else '')}</td>"
        f"<td>{esc(v[1] if len(v) > 1 else '')}</td></tr>"
        for asin, v in sorted(variants.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    )
    variant_matrix = (
        "<table><thead><tr><th>ASIN</th><th>颜色</th><th>尺码</th></tr></thead>"
        f"<tbody>{variant_rows}</tbody></table>"
        if variant_rows
        else "<p class='muted'>PDP 未返回可解析的变体集合。</p>"
    )

    polarity = metric.get("aspect_polarity_counts_natural") or metric["aspect_polarity_counts"]
    total_neg = sum(v.get("negative", 0) for v in polarity.values())
    total_pos = sum(v.get("positive", 0) for v in polarity.values())
    aspect_hits = total_pos + total_neg
    annot_total = metric["annotation_totals"]
    co = metric["cooccurrence"]

    frame_rows = "".join(
        f"<tr><td>{esc(frame)}</td><td class='num'>{fmt_int(count)}</td>"
        f"<td>{esc(_frame_purpose(frame))}</td></tr>"
        for frame, count in sorted(metric["frame_inventory"]["counts"].items())
    )

    grade_rows = _grade_table(claims)
    grade_legend_rows = _grade_legend()
    recommendation_rows = (
        "".join(
            f"<tr><td><b>{esc(row.get('title', ''))}</b><span class='micro mono'> "
            f"{esc(row.get('recommendation_id', ''))}</span></td>"
            f"<td>{esc(row.get('premise', ''))}</td>"
            f"<td>{esc(row.get('next_step', ''))}</td>"
            f"<td>{esc(row.get('kpi', ''))}</td>"
            f"<td>{esc(row.get('guardrail', ''))}</td>"
            f"<td><span class='pill amber'>{esc(row.get('status', 'Proposed'))}</span></td></tr>"
            for row in recommendations
        )
        or "<tr><td colspan='6'>本轮没有建议。</td></tr>"
    )
    exhibits = ExhibitLog()
    polarity_peak = _polarity_peak(polarity)
    tt_chain = corpus.get("frame_chains", {}).get("tiktok_shop_verified", {})
    tt_dir = claim_by_id["C13"].numbers
    tt_quarantine_rows = corpus.get("quarantine", [])
    tt_corpus_numbers = claim_by_id["C12"].numbers
    direction_total = int(tt_dir.get("support_same_direction", 0)) + int(
        tt_dir.get("support_opposite_direction", 0)
    )
    direction_pct = (
        round(100.0 * int(tt_dir.get("support_same_direction", 0)) / direction_total, 1)
        if direction_total
        else 0.0
    )
    inherited_precision_note = _inherited_precision_note(precision)
    precision_badge = (
        '<span class="badge blocked">precision: v1 沿用 · 未验证</span>'
        if inherited_precision_note
        else ""
    )

    if coder_id == "rule-v1":
        coder_label = "规则词典"
    else:
        coder_label = "LLM"

    confidence_dropped = int(
        (corpus.get("confidence_filter") or {}).get("dropped_aspects", 0) or 0
    )
    gold_abstained, gold_total, gold_abstention_share = _gold_abstentions(precision)
    cross_numbers = _cross_model_numbers(cross_model)
    if cross_numbers:
        cross_h1 = (
            f"；同模型多提示一致率另列为 presence Fleiss κ={cross_numbers['kappa']:.4f}"
            f"（{cross_numbers['n_items']} 条 / {cross_numbers['n_cells']} 格；"
            "5 个身份同一模型族），但这不是独立验证，也不是人工准确率"
        )
        cross_note = (
            f"同模型多提示 presence Fleiss κ={cross_numbers['kappa']:.4f}"
            f"（ALL；TikTok {cross_numbers['tiktok_kappa']:.4f} / "
            f"Reddit {cross_numbers['reddit_kappa']:.4f}）是同一模型族"
            "（deepseek-flash / deepseek-v4.1-flash）在 5 个身份提示下的自一致率，"
            "不是跨模型验证，也不是人工准确率；三行证据基础见 Trust & limits。"
        )
    else:
        cross_h1 = "；同模型多提示一致率未做，不能用它替代人工准确率"
        cross_note = "同模型多提示一致率未做，不能用它替代人工准确率；三行证据基础见 Trust & limits。"

    c13_grade = claim_by_id["C13"].grade
    if coder_id == "rule-v1":
        direction_clause = _c13_hero_clause(c13_grade)
        hero_h1 = f"商品身份可以确认，{direction_clause}，正式指标仍然为零。"
        precision_note = (
            "<p class='micro'>编码器精度复核：50 条 gold set（25 TikTok / 25 Reddit）"
            "严格 code+polarity；TikTok 63.4% / 33.8%，Reddit 0 条输出、recall 0%；"
            f"合并 {RULE_STRICT_PRECISION_PCT}% / {RULE_STRICT_RECALL_PCT}% 只作对照。"
            f"C13 的 {direction_pct:.1f}% 是规则编码器内部方向一致度，不是人工复核准确率；"
            "详见 gold/metrics.json。</p>"
        )
    else:
        hero_h1 = (
            "LLM 单编码只采信 high 置信度后方向线索仍成立：TikTok Shop strict precision "
            f"{LLM_TIKTOK_PRECISION_PCT}%（LLM vs LLM gold set，自证）达到门槛；Reddit 只有 "
            f"{LLM_REDDIT_HIGH_ASPECTS} 个 high aspect、{LLM_REDDIT_PRECISION_PCT}%（同为自证），"
            f"不足以编码{cross_h1}；正式指标仍为零。"
        )
        precision_note = (
            "<p class='micro'>编码器精度复核（high-only，strict code+polarity）："
            f"TikTok Shop {LLM_TIKTOK_PRECISION_PCT}% / {LLM_TIKTOK_RECALL_PCT}%"
            f"（{LLM_TIKTOK_HIGH_ASPECTS} 个 high aspect，达到 90% 门槛）；"
            f"Reddit {LLM_REDDIT_PRECISION_PCT}% / {LLM_REDDIT_RECALL_PCT}%"
            f"（仅 {LLM_REDDIT_HIGH_ASPECTS} 个 high aspect，单个 FP 就移动 12.5 个百分点，"
            "不足以编码）；"
            f"合并 {LLM_STRICT_PRECISION_PCT}% / {LLM_STRICT_RECALL_PCT}% 只作对照，"
            "会同时高估 Reddit、低估 TikTok。"
            f"all 模式对照为 {LLM_ALL_MODE_STRICT_PRECISION_PCT}% / {LLM_ALL_MODE_STRICT_RECALL_PCT}%。"
            f"按 build 后 annotations 口径（high 且极性可判）为 "
            f"{LLM_BUILD_STRICT_PRECISION_PCT}% / {LLM_BUILD_STRICT_RECALL_PCT}%，结论不变。"
            f"置信度弃权：本轮 high 门槛弃权 {confidence_dropped} 个 aspect；"
            f"在 50 条 gold set 上弃权 {gold_abstained}/"
            f"{gold_total}（{gold_abstention_share}%）。"
            "弃权逐条可审计：confidence-dropped.jsonl 记录 code、polarity、span 与原因，"
            "llm-coding/eval-result-high.json 记录 gold 子集的 strict 命运。"
            "这是单编码输出对 gold 的 precision，不是人工双盲 agreement，"
            "也不是人工准确率：gold set 本身也是 LLM 标注，50 条样本、85 个 gold aspect。"
            f"C13 的 {direction_pct:.1f}% 是 LLM 编码器内部方向一致度，不是人工复核准确率；"
            f"详见 llm-coding/eval-result-high.json。{cross_note}"
            f"{inherited_precision_note}</p>"
        )

    creator_video_html = creator_video_section(
        creator_video, cb, claim_by_id, exhibits
    )
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="description" content="{esc(claim_by_id['C02'].headline)}">
<title>VOC 洞察报告 · {esc(run_id)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <div class="kicker">VOC Consumer Insight · progress snapshot</div>
  <h1>{hero_h1}</h1>
  <p class="lede">{esc(claim_by_id["C02"].headline)} 报告停在 G6：编码已跑通，但 G7 双盲校准没有执行，所以体验结论只能停在方向性或证据缺口，不是正式指标。</p>
  <p class="micro">置信度门槛 high：全语料有 {confidence_dropped} 个 aspect 因低于门槛被弃权；在 50 条 gold set 上弃权 {gold_abstained}/{gold_total}（{gold_abstention_share}%）。弃权不是删除记录，也不进入任何 claim 计数；逐条审计见 confidence-dropped.jsonl。</p>
  <div class="badges">
    <span class="badge mode">report_mode: progress_snapshot</span>
    <span class="badge">minimum gate: G6 PASS</span>
    <span class="badge blocked">G7 BLOCKED → 0 metric rows</span>
    <span class="badge">confidence gate: high · {confidence_dropped} aspects abstained</span>
    {precision_badge}
    <span class="badge">run {esc(run_id)}</span>
    <span class="badge">generated {esc(generated_at)}</span>
  </div>
</header>

<section id="identity">
  <div class="sec-kicker">01 / Identity</div>
  {cb("C01")}
  {figure(
      "EXHIBIT 01",
      f"线上 PDP 的 {len(variants)} 个 ASIN 变体可以逐一枚举，但归档只记录了 12 个。",
      "变体矩阵来自 PDP 的 dimensionValuesDisplayData；只记录页面直接给出的组合。",
      variant_matrix,
      claim=claim_by_id["C01"],
      basis=(
          "amazon-identity-raw.json（PDP HTML sha256）；分母 = 页面返回的 ASIN 组合 "
          f"{len(variants)} 个，不是归档的 12 个 children"
      ),
      unit="ASIN / 颜色 × 尺码组合",
      limit="单时点、单地区（US）、未登录会话",
      log=exhibits,
  )}
</section>

<section id="corpus">
  <div class="sec-kicker">02 / Counting</div>
  {cb("C02")}
  {figure(
      "EXHIBIT 02",
      "raw、occurrence、canonical、membership、metric row 是五个不同的数。",
      "每一级只回答自己的问题；扣减理由见下表，不把覆盖当成逐级转化。",
      reconciliation_chain(corpus, metric)
      + "<table><thead><tr><th>扣减</th><th>数量</th><th>理由</th></tr></thead><tbody>"
      + f"<tr><td>同 frame 重复</td><td class='num'>{corpus['within_frame_overlap_dropped']}</td><td>同一 external_id 在同一 frame 被多次写入</td></tr>"
      + f"<tr><td>重复内容合并（canonical）</td><td class='num'>{corpus['reconciliation']['occurrences_to_canonical'] - corpus['deduction_reasons'].get('product_mismatch', 0) - corpus['deduction_reasons'].get('out_of_window', 0)}</td><td>同一内容跨 frame / 作者转发，合并为一个 canonical</td></tr>"
      + f"<tr><td>产品身份不匹配</td><td class='num'>{corpus['deduction_reasons'].get('product_mismatch', 0)}</td><td>YB003 等其他型号混入目标 listing，进入 quarantine</td></tr>"
      + f"<tr><td>超出窗口</td><td class='num'>{corpus['deduction_reasons'].get('out_of_window', 0)}</td><td>review_time 在 2026-07-01 至 2026-10-29 之外</td></tr>"
      + f"<tr><td>低信息 / 无关 / 其他产品 / 商业内容</td><td class='num'>{sum(corpus['excluded'].values())}</td><td>{esc(_excluded_text(corpus['excluded']))}</td></tr>"
      + "</tbody></table>",
      claim=claim_by_id["C02"],
      basis=(
          "collection-run-ledger.json + canonical-records.jsonl；分母 = raw objects "
          f"{corpus['raw_objects']} 条，逐级扣减见下表（不是到指标的转化率）"
      ),
      unit="条 / 记录（只给计数，不换算百分比）",
      limit="关键词检索样本，非概率抽样",
      log=exhibits,
  )}
  {figure(
      "EXHIBIT 03",
      f"annotation 共 {fmt_int(sum(annot_total.values()))} 条，远大于记录数，不能当作人数。",
      "多标签结构：一条记录可以同时有 aspect、context、journey、outcome、gap 标注。",
      "<table><thead><tr><th>轴</th><th class='num'>annotation hits</th></tr></thead><tbody>"
      + "".join(f"<tr><td>{esc(k)}</td><td class='num'>{fmt_int(v)}</td></tr>" for k, v in sorted(annot_total.items()))
      + "</tbody></table>",
      claim=claim_by_id["C02"],
      basis=(
          "coded-corpus.jsonl；分母 = "
          f"{fmt_int(sum(annot_total.values()))} 条 annotation hit（来自 "
          f"{corpus['canonical_records']} 条 canonical），不是人数"
      ),
      unit="annotation hits（多标签，一条记录可贡献多个）",
      limit="单编码、" + coder_label + "、pre-G7；不可用于 rate",
      log=exhibits,
  )}
</section>

<section id="frames">
  <div class="sec-kicker">03 / Frames</div>
  <p class="muted">自然样本与诊断镜头回答不同问题，合并相加会制造一个不存在的总体。frame membership 可重叠；下表是 membership 数，不是去重人数。</p>
  <table><thead><tr><th>frame</th><th class="num">memberships</th><th>用途</th></tr></thead><tbody>{frame_rows}</tbody></table>
  <p class="micro">上一版把 natural 的 149 条与 diagnostic 的 8 条原始负向计数放在同一根轴上比较，违反 frame 规则；该比较已删除。本表只给 membership 计数，不跨 frame 比较比例。</p>
</section>

<section id="verified-reviews">
  <div class="sec-kicker">04 / Verified reviews</div>
  <p class="muted">第二来源是 TikTok Shop 美国站的 verified-purchase 评论。它回答的是“买过的人在说什么方向”，不是一个可以外推的人群样本；它与 natural / diagnostic frame 并列，不合并、不比较比例。</p>
  {cb("C12")}
  {figure(
      "EXHIBIT 04",
      f"TikTok Shop 的 {tt_corpus_numbers.get('raw_rows', 0)} 条记录按六级计数走到 "
      f"{tt_corpus_numbers.get('canonical_records', 0)} 条 canonical 和 "
      f"{tt_chain.get('annotation', {}).get('count', 0)} 条 annotation，metric row 仍为 0。",
      "每一级只回答自己的问题；扣减带 reason code，不把逐级计数当成转化链。",
      chain_table(tt_chain),
      claim=claim_by_id["C12"],
      basis=(
          "frame-chains.json（tiktok_shop_verified）；分母 = raw "
          f"{tt_corpus_numbers.get('raw_rows', 0)} 条 provider rows，"
          "逐级扣减见下表"
      ),
      unit="条 / record / annotation hits（不换算百分比）",
      limit="单商品、单窗口（2026-07-01 至 2026-10-29）；G7 未执行",
      log=exhibits,
  )}
  {cb("C14")}
  {figure(
      "EXHIBIT 05",
      f"{len(tt_quarantine_rows)} 条 YB003 评论被隔离，未进入 YB001 的任何计数。",
      "隔离记录保留 review_id、variant 与 rating，便于复核规则是否漏判。",
      "<table><thead><tr><th>review_id</th><th>variant</th><th class='num'>rating</th><th>reason</th></tr></thead><tbody>"
      + (
          "".join(
              f"<tr><td class='mono'>{esc(row.get('review_id'))}</td><td>{esc(row.get('variant'))}</td>"
              f"<td class='num'>{esc(row.get('rating'))}</td><td class='mono micro'>{esc(row.get('reason'))}</td></tr>"
              for row in tt_quarantine_rows
          )
          or "<tr><td colspan='4'>没有隔离记录。</td></tr>"
      )
      + "</tbody></table>",
      claim=claim_by_id["C14"],
      basis=(
          "tiktok-shop-quarantine.jsonl；分母 = "
          f"{len(tt_quarantine_rows)} 条隔离记录，进入 canonical 的 0 条"
      ),
      unit="review records",
      limit="规则判定（sku_specification / product_name 文本）；无人工复核",
      log=exhibits,
  )}
  {cb("C13")}
  {figure(
      "EXHIBIT 06",
      f"在 {direction_total} 条有明确支撑方向的评论里，"
      f"{tt_dir.get('support_same_direction', 0)} 条同向、"
      f"{tt_dir.get('support_opposite_direction', 0)} 条反向，方向一致度 {direction_pct}%。",
      "mixed 记录同时出现同向与反向表述，不进入分子或分母；一致度只在本 frame 内计算。",
      "<table><thead><tr><th>方向</th><th class='num'>canonical records</th></tr></thead><tbody>"
      + f"<tr><td>同向</td><td class='num'>{fmt_int(tt_dir.get('support_same_direction', 0))}</td></tr>"
      + f"<tr><td>反向</td><td class='num'>{fmt_int(tt_dir.get('support_opposite_direction', 0))}</td></tr>"
      + f"<tr><td>同时出现两向（mixed）</td><td class='num'>{fmt_int(tt_dir.get('support_mixed', 0))}</td></tr>"
      + f"<tr><td>有文本但无可判定方向</td><td class='num'>{fmt_int(tt_dir.get('support_no_direction', 0))}</td></tr>"
      + "</tbody></table>",
      claim=claim_by_id["C13"],
      basis=(
          "coded-corpus.jsonl（SUP.* aspect × polarity）；分母 = "
          f"{direction_total} 条有明确方向的 canonical records（同向 + 反向），"
          "mixed 与无方向记录不计入"
      ),
      unit="canonical records（一条记录最多计一个方向）",
      limit="单编码、" + coder_label + "、pre-G7；reviewer 为掩码名",
      log=exhibits,
  )}
</section>

{creator_video_html}

<section id="friction">
  <div class="sec-kicker">06 / Friction</div>
  {cb("C04")}
  {figure(
      "EXHIBIT 10",
      f"负向与正向标注并存：{fmt_int(total_neg)} 次负向、{fmt_int(total_pos)} 次正向。",
      f"这里是 natural frame 全部 aspect 的 annotation hits，不是净分，也不是比例；C04 只统计其中四类摩擦，"
      f"摩擦记录 pooled {fmt_int(claim_by_id['C04'].numbers.get('friction_records', 0))} 条"
      f"（full {fmt_int(claim_by_id['C04'].numbers.get('friction_records_full', 0))}、"
      f"partial {fmt_int(claim_by_id['C04'].numbers.get('friction_records_partial', 0))}）；pooled 不是分布。",
      diverging_bars(polarity),
      claim=claim_by_id["C04"],
      basis=(
          f"aspect_polarity_counts；分母 = {aspect_hits} 条 aspect annotation hit"
          f"（+{total_pos} / −{total_neg}）；条宽按图内最大单项值 {polarity_peak} 归一，"
          f"不按 {aspect_hits} 条 hit、记录数或显示上限换算"
      ),
      unit="aspect annotation hits（不是人数、不是占比）",
      limit="多标签、单编码、pre-G7；不可读作 prevalence",
      log=exhibits,
  )}
  <p class="micro">口径提醒：{fc_cite("FC-01", "情绪占比")}；任何正负百分比都不进入本报告。</p>
</section>

<section id="tension">
  <div class="sec-kicker">07 / Core tension</div>
  {cb("C05")}
  <div class="cols2">
    <div class="card"><h4>full 层：主动分享的舒适正向</h4>
      <p class="mini">{fmt_int(co['full']['comfort_positive_records'])} 条；其中共现 {fmt_int(co['full']['comfort_positive_with_friction'])} 条</p>
      <div class="stack">{_sample_rows(co, True, 'full')}</div>
      <div class="stack">{_sample_rows(co, False, 'full')}</div></div>
    <div class="card"><h4>partial 层：附带或未定评价</h4>
      <p class="mini">{fmt_int(co['partial']['comfort_positive_records'])} 条；其中共现 {fmt_int(co['partial']['comfort_positive_with_friction'])} 条</p>
      <div class="stack">{_sample_rows(co, True, 'partial')}</div>
      <div class="stack">{_sample_rows(co, False, 'partial')}</div></div>
  </div>
  <p class="micro">pooled {fmt_int(co['comfort_positive_records'])} 条舒适正向、{fmt_int(co['comfort_positive_with_friction'])} 条共现；pooled 不是分布，full 与 partial 的分母不能合并。</p>
</section>

<section id="coverage">
  <div class="sec-kicker">08 / Coverage</div>
  {cb("C03")}
  {cb("C11")}
  <div class="note">
    <b>未取得的证据（显式缺口，不用相邻数据代替）：</b><br>
    [Evidence gap] Amazon 评论正文：product-reviews 需要登录态，当前返回 302。<br>
    [Evidence gap] r/pregnant 帖子与 BabyBumps 评论：Arctic Shift 返回 422 超时，失败请求保留在 ledger。<br>
    [Evidence gap] G7 逐字段 agreement：没有第二编码员。
  </div>
  {figure(
      "EXHIBIT 11",
      f"{fmt_int(sum(metric.get('product_match_counts', {}).values()))} 条 canonical 里只有 "
      f"{metric.get('product_match_counts', {}).get('exact_current_family', 0)} 条与支撑带同族相关，"
      f"{claim_by_id['C03'].numbers.get('momcozy_records', 0)} 条 Momcozy 提及多数是别的产品。",
      "product_match 由文本规则判定；它决定一条记录能否进入品类问题，不决定情绪。",
      _count_table(metric.get("product_match_counts", {}), _PRODUCT_MATCH_LABELS),
      claim=claim_by_id["C03"],
      basis=(
          "canonical-records.jsonl；分母 = "
          f"{corpus['canonical_records']} 条 canonical records（按 product_match 规则分类）"
      ),
      unit="canonical records",
      limit="规则判定、无人工复核",
      log=exhibits,
  )}
  <p class="micro">样本口径：{fc_cite("FC-10", "求助帖当体验")}；求助/求推荐记录只有存在当前产品的可归属评价时才进入 partial 层，full 层单独报告；pooled 不是分布，不能合并。</p>
</section>

<section id="gate">
  <div class="sec-kicker">09 / Evidence state</div>
  {cb("C07")}
  <h3>六级证据状态：每条结论只能落在其中一级，先命中先停。</h3>
  <table><thead><tr><th>等级</th><th>看到什么就归这一级</th><th>可以用于</th><th>不能用于</th></tr></thead>
  <tbody>{grade_legend_rows}</tbody></table>
  <p class="micro">每条 claim 的 Counts 行：n_records / n_authors 取自该结论自己的证据集；agreement 只在存在方向判定时给出。计数事实没有方向一致度时渲染 N/A，不拿集合包含或校验标记冒充一致度；其余 Confirmed 的 agreement 是身份 / ledger 校验通过标记。</p>
  <h3>本报告的结论分布</h3>
  {figure(
      "EXHIBIT 12",
      f"{_grade_sentence(claims)}；本轮没有出现的等级按零计，不省略。",
      "等级由机械规则判定，不由作者选择；同一个 run 里可以同时存在六种状态。",
      _count_table(_grade_counts(claims), _GRADE_WORDS),
      claim=claim_by_id["C07"],
      basis=(
          "claims.json；分母 = "
          f"{len(claims)} 条 claim，六种状态各按计数呈现，缺席按 0 计"
      ),
      unit="claims",
      limit="等级是状态，不是绩效分；由验证器复核",
      log=exhibits,
  )}
  <table><thead><tr><th>结论</th><th>等级</th><th>能用来做什么</th><th>不能用来做什么</th></tr></thead>
  <tbody>{grade_rows}</tbody></table>
  <div class="note">第六级是 <b>Not authorized</b>。参考报告表面只列了五级，但表格里同时出现 Confirmed、Directional、Supported hypothesis、Evidence gap、Blocked 与 Not authorized；医疗与因果禁写区必须显式成一级，否则会被误当作 Blocked 的一种。</div>
  <h3>未声明口径清单：缺任何一项都渲染为 UNKNOWN，不省略整行。</h3>
  <p class="micro">exhibit 脚注覆盖率 {exhibits.declared}/{exhibits.total} = {exhibits.coverage_pct}%；Status 一律取自该图关联 claim 的 grade。</p>
  {exhibits.undeclared_html()}
  {cb("C08")}
  <p class="micro">医学口径：{fc_cite("FC-09", "医学结论")}；self-report 只进 review queue，不升级为疗效或安全结论。</p>
</section>

<section id="decision">
  <div class="sec-kicker">10 / Recommendations（建议，不是证据）</div>
  <p class="muted">以下三条是建议，不参与六级证据分布，也不占用任何 claim 档位。每条建议都绑定它要补的证据缺口；没有 owner、预算与审批，不得当作已验证结论。</p>
  <table><thead><tr><th>建议</th><th>前置证据状态</th><th>最小验证</th><th>KPI</th><th>Guardrail / stop</th><th>状态</th></tr></thead>
  <tbody>{recommendation_rows}</tbody></table>
</section>

<section id="limits">
  <div class="sec-kicker">11 / Trust & limits</div>
  {cb("C10")}
  <div class="cols2">
    <div class="card"><h4>已经做到</h4>
      <div class="stack mini">
        <div>G0 决策与 frame 用途已写死；G1 线上一手身份已核对；G2 权利状态已登记；G3 inspect→run→对账已留痕；G4 taxonomy 已冻结；G5 分层采集；G6 去重与血缘对账。</div>
      </div>
    </div>
    <div class="card"><h4>还没有做</h4>
      <div class="stack mini">
        <div>G7 双盲编码与 agreement；G8 正式 metric；G9 实验审批；G10 结果复盘。没有第二编码员，也没有 owner 签名。</div>
      </div>
    </div>
  </div>
  <h3>证据基础：单次自证、同模型多提示稳定性、人工验证是三件事</h3>
  <p class="muted">旧的 precision 是 LLM 对 LLM gold set 的自证；新加的 κ 是同一模型族（deepseek-flash / deepseek-v4.1-flash）在 5 个身份提示下的稳定性，不是跨模型独立验证；人工验证仍未做。三者不能互相替代，同模型一致率也不能写成准确率。</p>
  {evidence_basis_table(precision, cross_model)}
  <h3>编码可信度：分信源 strict precision（high-only）</h3>
  <p class="muted">精度按信源分开报。合并数字只作对照，不作为采信依据：TikTok Shop 达到门槛，Reddit 样本过小，不足以编码。</p>
  {precision_source_table(precision)}
  <h3>每条 claim 的信源依赖与采信判断</h3>
  <p class="muted">凡是主要靠 Reddit 编码支撑的 claim，即使 grade 是 Confirmed，也标为低可信；grade 本身不变。</p>
  {claim_source_table(claims, claim_sources, precision)}
  {precision_note}
</section>

{forbidden_section()}

<footer>
  <div>VOC pipeline · run {esc(run_id)} · generated {esc(generated_at)}</div>
  <div>Structure and claim grammar follow the reference SOP; all numbers are produced by this run's artifacts and can be recomputed with <span class="mono">python3 -m voc.cli build --run {esc(run_id)}</span>.</div>
  <div>方法规格：<a href="../../spec/spec.html">spec/spec.html</a> · 代码：<span class="mono">voc_pipeline/voc</span> · 本报告为 internal progress snapshot，未提交、未发布。</div>
</footer>
</div>
</body>
</html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path


_PRODUCT_MATCH_LABELS = {
    "exact_current_family": "目标家族 / 同族支撑带",
    "brand_category": "品牌品类提及",
    "brand_other_product": "Momcozy 其他产品",
    "category_adjacent": "品类相邻（通用支撑带）",
    "irrelevant": "无关",
    "unknown": "无法判定",
}


def _count_table(counts: dict[str, int], labels: dict[str, str]) -> str:
    rows = "".join(
        f"<tr><td>{esc(labels.get(k, k))}</td><td class='num'>{fmt_int(v)}</td></tr>"
        for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    return (
        "<table><thead><tr><th>类别</th><th class='num'>记录数</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "<div class='micro'>只给计数，不给比例；这些记录不是消费者总体，也不跨 frame 比较。</div>"
    )


_GRADE_WORDS = {
    "Confirmed": "确认事实",
    "Directional": "方向性",
    "Supported hypothesis": "可支持假设",
    "Evidence gap": "缺口",
    "Blocked": "阻断",
    "Not authorized": "禁写",
}


def _grade_sentence(claims: list[Claim]) -> str:
    counts = _grade_counts(claims)
    order = ["Confirmed", "Directional", "Supported hypothesis", "Evidence gap", "Blocked", "Not authorized"]
    parts = [f"{counts.get(g, 0)} 条{_GRADE_WORDS[g]}" for g in order if counts.get(g, 0)]
    return "、".join(parts) if parts else "没有任何结论"


def _grade_counts(claims: list[Claim]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in claims:
        out[c.grade.value] = out.get(c.grade.value, 0) + 1
    return out


def _excluded_text(excluded: dict[str, int]) -> str:
    labels = {
        "irrelevant": "无关",
        "brand_other_product": "Momcozy 其他产品",
        "low_information": "低信息",
        "claim_asset": "商业内容",
    }
    return "；".join(f"{labels.get(k, k)} {v}" for k, v in excluded.items())


def _frame_purpose(frame: str) -> str:
    return {
        "natural": "方向性观察；有明确关键词分母，但不是概率样本",
        "diagnostic": "失败模式发现；不得估计发生率",
        "qualitative_seed": "假设与种子；不进入 consumer metric",
        "tiktok_shop_verified": "购买者方向验证；单商品、verified-purchase、掩码作者名",
        "claim_asset": "品牌 / 创作者承诺审计",
        "discovery": "待确认身份，留在 hold queue",
        "excluded": "血缘保留，不进入任何分母",
    }.get(frame, "")


def _sample_rows(co: dict[str, Any], comfort_only: bool, scope: str | None = None) -> str:
    rows = co["rows"]
    if scope is not None:
        rows = [r for r in rows if r.get("experience_scope") == scope]
    if comfort_only:
        rows = [r for r in rows if r["comfort_positive"]][:3]
    else:
        rows = [r for r in rows if r["both"]][:3]
    if not rows:
        return '<div class="mini muted">本轮没有可展示的样本。</div>'
    return "".join(
        f'<div class="mini"><span class="tag mono">{esc(r["canonical_id"])}</span>{esc(r["text"][:140])}</div>'
        for r in rows
    )


def _grade_legend() -> str:
    rules = [
        ("Not authorized", "涉及医学功效、安全、因果或诊断。", "只记录 self-report。", "疗效、安全率、因果、诊断。"),
        ("Blocked", "所需 gate 未通过，或分母不存在。", "说明为什么不能说。", "任何比率、排名、总体结论。"),
        ("Evidence gap", "要求的 cell 记录数为 0、关键字段缺失，或对比支持门槛未通过。", "指出缺口与补证动作。", "用 family 或其他 variant 推断。"),
        ("Confirmed", "直接事实，带 artifact hash、精确身份与时间戳。", "身份、计数、成本、字段值。", "外推成体验或因果。"),
        ("Directional", "同一 frame ≥8 条、≥2 作者、方向一致度 ≥70%，但仍单编码。", "方向判断、实验设计。", "prevalence、对外承诺。"),
        ("Supported hypothesis", "3–7 条，或一致度 55–70%，或只有 1 个作者，或 ≥8 条但方向一致度 <70%。", "提出假设、下一轮采集。", "写成发现或据此改款。"),
    ]
    return "".join(
        f"<tr><td><span class='grade {GRADE_CLASS[g]}'>{esc(g)}</span></td><td>{esc(seen)}</td>"
        f"<td>{esc(use)}</td><td>{esc(bad)}</td></tr>"
        for g, seen, use, bad in rules
    )


def _grade_table(claims: list[Claim]) -> str:
    rows = []
    for c in claims:
        usage = {
            EvidenceGrade.CONFIRMED: ("身份、计数、成本、字段值", "外推成体验或因果"),
            EvidenceGrade.DIRECTIONAL: ("方向判断、实验设计", "prevalence、对外承诺"),
            EvidenceGrade.SUPPORTED_HYPOTHESIS: ("提出假设、下一轮采集", "写成发现或据此改款"),
            EvidenceGrade.GAP: ("说明缺口与补证动作", "用其他 variant 推断"),
            EvidenceGrade.BLOCKED: ("解释为什么不能说", "任何比率或排名"),
            EvidenceGrade.NOT_AUTHORIZED: ("记录 self-report", "疗效、安全、诊断、因果"),
        }[c.grade]
        rows.append(
            f"<tr><td>{esc(c.headline[:70])}</td>"
            f"<td><span class='grade {GRADE_CLASS[c.grade.value]}'>{esc(c.grade.value)}</span></td>"
            f"<td>{esc(usage[0])}</td><td>{esc(usage[1])}</td></tr>"
        )
    return "".join(rows)
