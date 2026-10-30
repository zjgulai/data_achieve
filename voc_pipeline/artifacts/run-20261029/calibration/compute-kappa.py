#!/usr/bin/env python3
"""Compute human-vs-LLM Cohen's kappa for a blind calibration sample.

Inputs
------
``--sample``
    ``blind-sample.jsonl`` produced by ``build-calibration.py``.
``--human``
    The JSON file exported by ``label.html``.
``--mapping``
    ``mapping.json``; maps opaque item ids to corpus canonical ids.
``--coded``
    ``llm-coding/coded/ALL.jsonl``.  Only aspects at or above
    ``--min-confidence`` are used (default: ``high``).

Output
------
A Markdown report (default ``kappa-report.md``) and, optionally, a JSON
metrics file (``--json-out``).

Statistical unit
----------------
For each item and each taxonomy aspect, the pair of annotators is compared on
a binary decision: *is this aspect present in the item?*  A cell is one
(item, aspect) pair.  Kappa is computed from the resulting 2x2 table.  This is
the standard multi-label treatment: one binary kappa per aspect, plus a pooled
("micro") kappa and an average-of-aspects ("macro") kappa per source.

Polarity is reported separately: among cells where both annotators marked the
aspect present, how often did they choose the same polarity (exact and family)?

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent
DEFAULT_SAMPLE = HERE / "blind-sample.jsonl"
DEFAULT_MAPPING = HERE / "mapping.json"
DEFAULT_CODED = RUN_DIR / "llm-coding" / "coded" / "ALL.jsonl"
DEFAULT_TAXONOMY = RUN_DIR / "llm-coding" / "taxonomy.json"
DEFAULT_OUT = HERE / "kappa-report.md"

SOURCE_LABELS = {"tiktok_shop": "TikTok", "reddit": "Reddit"}
SOURCE_ORDER = ("TikTok", "Reddit")
CONF_RANK = {"low": 0, "medium": 1, "high": 2}
CONF_LABEL = {"high": "high（默认）", "medium": "high + medium", "all": "全部置信度"}

POLARITY_LABELS = {
    "positive": "正向",
    "negative": "负向",
    "qualified_positive": "有条件正向",
    "qualified_negative": "有条件负向",
    "mixed": "混合",
    "unknown": "不确定",
}
VALID_POLARITIES = set(POLARITY_LABELS)
REASON_LABELS = {
    "help_seeking": "求助",
    "third_party_event": "第三方事件",
    "other_product": "其他产品",
    "other": "其他",
}

FAMILY_ZH = {
    "SUP": "支撑",
    "FIT": "尺码与合身",
    "ADJ": "调节与结构",
    "STB": "稳定性",
    "COM": "舒适",
    "APP": "外观与衣下表现",
    "MAT": "面料与耐用",
    "VAL": "性价比",
    "CX": "退换与服务",
    "FUL": "到货状态",
    "GEN": "总体评价",
    "USE": "穿着方式",
    "ACT": "活动兼容",
    "SAF": "受力安全",
}


class CalibrationError(Exception):
    """A user-fixable input problem."""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise CalibrationError(f"找不到文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationError(f"JSON 解析失败：{path}（{exc}）") from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            rows = []
            for line_no, line in enumerate(fh, start=1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise CalibrationError(
                        f"JSONL 第 {line_no} 行解析失败：{path}（{exc}）"
                    ) from exc
            return rows
    except FileNotFoundError as exc:
        raise CalibrationError(f"找不到文件：{path}") from exc


def normalize_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"tiktok", "tiktok shop", "tiktok_shop", "tiktok-shop"}:
        return "tiktok_shop"
    if text in {"reddit", "r/reddit"}:
        return "reddit"
    return text


def source_display(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def polarity_family(polarity: str | None) -> str:
    if polarity == "qualified_positive":
        return "positive"
    if polarity == "qualified_negative":
        return "negative"
    return polarity or "unknown"


def load_taxonomy(path: Path) -> dict[str, Any]:
    data = load_json(path)
    aspects = data.get("aspects")
    if not isinstance(aspects, list) or not aspects:
        raise CalibrationError(f"taxonomy 没有 aspects 列表：{path}")
    codes: list[str] = []
    labels: dict[str, str] = {}
    families: dict[str, str] = {}
    family_labels: dict[str, str] = data.get("family_labels") or {}
    for aspect in aspects:
        code = aspect.get("code")
        if not code:
            raise CalibrationError(f"taxonomy 中有 aspect 缺少 code：{aspect}")
        if code in labels:
            raise CalibrationError(f"taxonomy 中 aspect code 重复：{code}")
        codes.append(code)
        labels[code] = aspect.get("label") or code
        families[code] = aspect.get("family") or ""
    return {
        "codes": codes,
        "labels": labels,
        "families": families,
        "family_labels": family_labels,
    }


def load_sample(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    if not rows:
        raise CalibrationError(f"样本为空：{path}")
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise CalibrationError(f"样本第 {index} 行不是对象")
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise CalibrationError(f"样本第 {index} 行缺少 item_id")
        if item_id in seen:
            raise CalibrationError(f"样本 item_id 重复：{item_id}")
        seen.add(item_id)
        source = normalize_source(row.get("source"))
        if not source:
            raise CalibrationError(f"样本 {item_id} 缺少 source")
        text = row.get("text")
        title = row.get("title")
        if not isinstance(text, str) or not isinstance(title, str):
            raise CalibrationError(f"样本 {item_id} 的 text/title 必须是字符串")
        if not text.strip() and not title.strip():
            raise CalibrationError(f"样本 {item_id} 没有正文")
        clean.append(
            {
                "item_id": item_id,
                "source": source,
                "title": title,
                "text": text,
                "rating": row.get("rating"),
            }
        )
    return clean


def load_mapping(path: Path, sample: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [
            {"item_id": key, **(value if isinstance(value, dict) else {"canonical_id": value})}
            for key, value in data.items()
        ]
    else:
        raise CalibrationError(f"mapping 格式无法识别：{path}")
    if not isinstance(items, list):
        raise CalibrationError(f"mapping.items 必须是列表：{path}")

    mapping: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise CalibrationError(f"mapping 条目不是对象：{item}")
        item_id = item.get("item_id")
        canonical_id = item.get("canonical_id")
        if not item_id or not canonical_id:
            raise CalibrationError(f"mapping 条目缺少 item_id/canonical_id：{item}")
        if item_id in mapping:
            raise CalibrationError(f"mapping item_id 重复：{item_id}")
        mapping[item_id] = {
            "canonical_id": canonical_id,
            "source": normalize_source(item.get("source")) if item.get("source") else "",
        }

    sample_ids = {row["item_id"] for row in sample}
    missing = sorted(sample_ids - set(mapping))
    extra = sorted(set(mapping) - sample_ids)
    if missing:
        raise CalibrationError(f"mapping 缺少样本 item_id：{', '.join(missing[:10])}")
    if extra:
        raise CalibrationError(
            f"mapping 包含样本中不存在的 item_id：{', '.join(extra[:10])}"
        )
    for row in sample:
        mapped_source = mapping[row["item_id"]]["source"]
        if mapped_source and mapped_source != row["source"]:
            raise CalibrationError(
                f"mapping 的 source 与样本不一致：{row['item_id']} "
                f"mapping={mapped_source}, sample={row['source']}"
            )
    return mapping


def load_human(path: Path, sample: list[dict[str, Any]], taxonomy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, dict) and "items" in data:
        if data.get("schema") and data["schema"] != "voc-human-labels-v1":
            raise CalibrationError(
                f"人工标注文件 schema 不认识：{data.get('schema')}（应为 voc-human-labels-v1）"
            )
        items = data["items"]
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [
            {"item_id": key, **(value if isinstance(value, dict) else {})}
            for key, value in data.items()
        ]
    else:
        raise CalibrationError(f"人工标注文件格式无法识别：{path}")
    if not isinstance(items, list):
        raise CalibrationError("人工标注文件的 items 必须是列表")

    sample_ids = {row["item_id"] for row in sample}
    human: dict[str, dict[str, Any]] = {}
    for raw in items:
        if not isinstance(raw, dict):
            raise CalibrationError(f"人工标注条目不是对象：{raw}")
        item_id = raw.get("item_id")
        if not item_id:
            raise CalibrationError(f"人工标注条目缺少 item_id：{raw}")
        if item_id in human:
            raise CalibrationError(f"人工标注 item_id 重复：{item_id}")
        if item_id not in sample_ids:
            raise CalibrationError(f"人工标注包含样本中不存在的 item_id：{item_id}")

        gate = raw.get("is_product_experience")
        if not isinstance(gate, bool):
            raise CalibrationError(
                f"{item_id} 的 is_product_experience 必须是 true/false（当前：{gate!r}）"
            )
        reason = raw.get("experience_reason")
        if gate:
            if reason not in (None, ""):
                # Not fatal: the HTML never exports this, but keep it visible.
                reason = None
        else:
            if reason not in REASON_LABELS:
                raise CalibrationError(
                    f"{item_id} 判定为「否」但原因无效：{reason!r}；"
                    f"可选：{', '.join(REASON_LABELS)}"
                )

        aspects_raw = raw.get("aspects", [])
        if aspects_raw is None:
            aspects_raw = []
        if not isinstance(aspects_raw, list):
            raise CalibrationError(f"{item_id} 的 aspects 必须是列表")
        aspects: dict[str, dict[str, Any]] = {}
        for aspect in aspects_raw:
            if not isinstance(aspect, dict):
                raise CalibrationError(f"{item_id} 的 aspect 条目不是对象：{aspect}")
            code = aspect.get("code")
            if code not in taxonomy["codes"]:
                raise CalibrationError(f"{item_id} 含 taxonomy 中不存在的 aspect code：{code!r}")
            if code in aspects:
                raise CalibrationError(f"{item_id} 的 aspect 重复：{code}")
            polarity = aspect.get("polarity")
            if polarity not in VALID_POLARITIES:
                raise CalibrationError(
                    f"{item_id} 的 {code} 极性无效：{polarity!r}；"
                    f"可选：{', '.join(POLARITY_LABELS)}"
                )
            evidence = aspect.get("evidence", aspect.get("evidence_span", ""))
            if evidence is None:
                evidence = ""
            if not isinstance(evidence, str):
                raise CalibrationError(f"{item_id} 的 {code} evidence 必须是字符串")
            aspects[code] = {"polarity": polarity, "evidence": evidence}

        if not gate and aspects:
            raise CalibrationError(
                f"{item_id} 判定为「否」却带了 {len(aspects)} 个 aspect；"
                "盲标页不会导出这种组合，请重新导出或清空该项 aspect"
            )

        human[item_id] = {"gate": gate, "reason": reason, "aspects": aspects}

    missing = sorted(sample_ids - set(human))
    if missing:
        raise CalibrationError(
            "人工标注缺了样本条目："
            + ", ".join(missing[:10])
            + ("…" if len(missing) > 10 else "")
            + "。请确认 20 条都标完后再导出。"
        )

    return human


def load_llm(
    path: Path,
    sample: list[dict[str, Any]],
    mapping: dict[str, dict[str, Any]],
    taxonomy: dict[str, Any],
    min_confidence: str,
) -> dict[str, dict[str, Any]]:
    rows = load_jsonl(path)
    by_canonical = {row.get("canonical_id"): row for row in rows if row.get("canonical_id")}
    threshold = -1 if min_confidence == "all" else CONF_RANK[min_confidence]
    clean: dict[str, dict[str, Any]] = {}
    for item in sample:
        item_id = item["item_id"]
        canonical_id = mapping[item_id]["canonical_id"]
        row = by_canonical.get(canonical_id)
        if row is None:
            raise CalibrationError(
                f"LLM 编码文件里找不到 {item_id} 对应的 canonical_id={canonical_id}"
            )
        aspects: dict[str, dict[str, Any]] = {}
        for aspect in row.get("aspects") or []:
            code = aspect.get("code")
            if code not in taxonomy["codes"]:
                raise CalibrationError(
                    f"LLM 文件 {canonical_id} 含 taxonomy 中不存在的 aspect code：{code!r}"
                )
            confidence = aspect.get("confidence", "high")
            if CONF_RANK.get(confidence, -1) < threshold:
                continue
            if code in aspects:
                raise CalibrationError(
                    f"LLM 文件 {canonical_id} 的 {code} 出现多次；"
                    "请检查是否重复标注"
                )
            polarity = aspect.get("polarity")
            if polarity not in VALID_POLARITIES:
                raise CalibrationError(
                    f"LLM 文件 {canonical_id} 的 {code} 极性无效：{polarity!r}"
                )
            aspects[code] = {
                "polarity": polarity,
                "evidence_span": aspect.get("evidence_span") or "",
            }
        clean[item_id] = {
            "gate": bool(row.get("is_product_experience")),
            "aspects": aspects,
            "canonical_id": canonical_id,
        }
    return clean


def cohen_kappa(a: int, b: int, c: int, d: int) -> dict[str, Any]:
    """2x2 Cohen's kappa.

    a = both present, b = human only, c = LLM only, d = both absent.
    """
    n = a + b + c + d
    if n == 0:
        return {
            "n": 0,
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "observed_agreement": None,
            "expected_agreement": None,
            "kappa": None,
        }
    observed = (a + d) / n
    expected = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    if abs(1.0 - expected) < 1e-12:
        kappa = None
    else:
        kappa = (observed - expected) / (1.0 - expected)
    return {
        "n": n,
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "observed_agreement": observed,
        "expected_agreement": expected,
        "kappa": kappa,
    }


def interpretation(kappa: float | None) -> str:
    if kappa is None:
        return "无法计算（无方差）"
    if kappa >= 0.80:
        return "almost perfect（几乎完全一致）"
    if kappa >= 0.60:
        return "substantial（实质一致）"
    if kappa >= 0.40:
        return "moderate（中等）"
    if kappa >= 0.20:
        return "fair（一般）"
    if kappa >= 0.0:
        return "slight（轻微）"
    return "poor（差，低于随机）"


def analyze_subset(
    items: list[dict[str, Any]],
    human: dict[str, dict[str, Any]],
    llm: dict[str, dict[str, Any]],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    codes = taxonomy["codes"]
    labels = taxonomy["labels"]
    families = taxonomy["families"]
    per_aspect: dict[str, dict[str, Any]] = {}
    pooled_a = pooled_b = pooled_c = pooled_d = 0

    for code in codes:
        a = b = c = d = 0
        both = 0
        exact = 0
        family_match = 0
        mismatches: list[dict[str, Any]] = []
        for item in items:
            item_id = item["item_id"]
            human_aspect = human[item_id]["aspects"].get(code)
            llm_aspect = llm[item_id]["aspects"].get(code)
            has_human = human_aspect is not None
            has_llm = llm_aspect is not None
            if has_human and has_llm:
                a += 1
                both += 1
                human_polarity = human_aspect["polarity"]
                llm_polarity = llm_aspect["polarity"]
                if human_polarity == llm_polarity:
                    exact += 1
                if polarity_family(human_polarity) == polarity_family(llm_polarity):
                    family_match += 1
                if human_polarity != llm_polarity:
                    mismatches.append(
                        {
                            "item_id": item_id,
                            "kind": "polarity",
                            "human": human_aspect,
                            "llm": llm_aspect,
                        }
                    )
            elif has_human:
                b += 1
                mismatches.append(
                    {
                        "item_id": item_id,
                        "kind": "presence",
                        "human": human_aspect,
                        "llm": None,
                    }
                )
            elif has_llm:
                c += 1
                mismatches.append(
                    {
                        "item_id": item_id,
                        "kind": "presence",
                        "human": None,
                        "llm": llm_aspect,
                    }
                )
            else:
                d += 1

        stats = cohen_kappa(a, b, c, d)
        stats.update(
            {
                "code": code,
                "label": labels.get(code, code),
                "family": families.get(code, ""),
                "family_label": FAMILY_ZH.get(families.get(code, ""), families.get(code, "")),
                "human_positive": a + b,
                "llm_positive": a + c,
                "both_positive": a,
                "human_only": b,
                "llm_only": c,
                "neither": d,
                "presence_mismatch": b + c,
                "both_present": both,
                "polarity_exact": exact,
                "polarity_family": family_match,
                "polarity_mismatch": both - exact,
                "polarity_family_mismatch": both - family_match,
                "polarity_exact_rate": (exact / both) if both else None,
                "polarity_family_rate": (family_match / both) if both else None,
                "total_mismatch": (b + c) + (both - exact),
                "active": (a + b + c) > 0,
                "mismatches": mismatches,
            }
        )
        per_aspect[code] = stats
        pooled_a += a
        pooled_b += b
        pooled_c += c
        pooled_d += d

    pooled = cohen_kappa(pooled_a, pooled_b, pooled_c, pooled_d)
    defined_kappas = [
        stats["kappa"]
        for stats in per_aspect.values()
        if stats["kappa"] is not None
    ]
    macro = statistics.fmean(defined_kappas) if defined_kappas else None

    return {
        "n_items": len(items),
        "n_cells": pooled["n"],
        "per_aspect": per_aspect,
        "pooled": pooled,
        "kappa_micro": pooled["kappa"],
        "raw_agreement": pooled["observed_agreement"],
        "kappa_macro": macro,
        "defined_aspects": len(defined_kappas),
        "active_aspects": sum(1 for stats in per_aspect.values() if stats["active"]),
    }


def analyze_gate(
    sample: list[dict[str, Any]],
    human: dict[str, dict[str, Any]],
    llm: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    a = b = c = d = 0
    for item in sample:
        item_id = item["item_id"]
        human_yes = human[item_id]["gate"]
        llm_yes = llm[item_id]["gate"]
        if human_yes and llm_yes:
            a += 1
        elif human_yes and not llm_yes:
            b += 1
        elif (not human_yes) and llm_yes:
            c += 1
        else:
            d += 1
    stats = cohen_kappa(a, b, c, d)
    stats["interpretation"] = interpretation(stats["kappa"])
    return stats


def format_number(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def format_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{100.0 * value:.{digits}f}%"


def md_escape(value: Any) -> str:
    text = str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def truncate(text: str, limit: int = 110) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_annotation(annotation: dict[str, Any] | None) -> str:
    if not annotation:
        return "未标注"
    polarity = POLARITY_LABELS.get(annotation.get("polarity"), annotation.get("polarity") or "未选极性")
    evidence = annotation.get("evidence", annotation.get("evidence_span", ""))
    if evidence:
        return f"{polarity} · “{truncate(evidence)}”"
    return polarity


def summary_row(name: str, stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "n_items": stats["n_items"],
        "n_cells": stats["n_cells"],
        "human_positive": stats["pooled"]["a"] + stats["pooled"]["b"],
        "llm_positive": stats["pooled"]["a"] + stats["pooled"]["c"],
        "both_positive": stats["pooled"]["a"],
        "human_only": stats["pooled"]["b"],
        "llm_only": stats["pooled"]["c"],
        "raw_agreement": stats["raw_agreement"],
        "kappa_micro": stats["kappa_micro"],
        "kappa_macro": stats["kappa_macro"],
        "interpretation_micro": interpretation(stats["kappa_micro"]),
        "interpretation_macro": interpretation(stats["kappa_macro"]),
        "active_aspects": stats["active_aspects"],
        "defined_aspects": stats["defined_aspects"],
    }


def ranked_disagreements(per_aspect: dict[str, dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    ranked = [
        stats
        for stats in per_aspect.values()
        if stats["total_mismatch"] > 0
    ]

    def sort_key(stats: dict[str, Any]) -> tuple[Any, ...]:
        kappa = stats["kappa"] if stats["kappa"] is not None else 2.0
        return (-stats["total_mismatch"], kappa, -stats["presence_mismatch"], stats["code"])

    ranked.sort(key=sort_key)
    return ranked[:top_n]


def build_report(
    args: argparse.Namespace,
    sample: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    overall: dict[str, Any],
    by_source: dict[str, dict[str, Any]],
    gate_stats: dict[str, Any],
    top_disagreements: list[dict[str, Any]],
    trigger_top5: bool,
    min_aspect_kappa: float | None,
    aspects_below_060: list[dict[str, Any]],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    all_stats = overall
    micro = all_stats["kappa_micro"]
    macro = all_stats["kappa_macro"]
    sample_counts = {
        name: sum(1 for item in sample if source_display(item["source"]) == name)
        for name in SOURCE_ORDER
    }

    lines: list[str] = []
    lines.append("# VOC 人工双盲校准 — Cohen's kappa 报告")
    lines.append("")
    lines.append(f"- 生成时间：{now}")
    lines.append(f"- 盲样本：`{args.sample}`（{len(sample)} 条）")
    lines.append(f"- 人工标注：`{args.human}`")
    lines.append(f"- LLM 参考：`{args.coded}`")
    lines.append(f"- taxonomy：`{args.taxonomy}`")
    lines.append(
        f"- 参考口径：LLM `confidence` = {CONF_LABEL[args.min_confidence]} 的 aspect；"
        "低于门槛的 aspect 不计入。"
    )
    lines.append(
        "- 样本分布："
        + "，".join(f"{name} {sample_counts.get(name, 0)} 条" for name in SOURCE_ORDER)
    )
    lines.append(
        "- 统计单元：每条 × 每个 taxonomy aspect 的「是否标注」二值判断；"
        "极性单独报告。"
    )
    lines.append(
        "- 主口径：**micro κ**（同一信源内所有 item×aspect 单元格池化）；"
        "同时报 **macro κ**（逐 aspect κ 的算术平均）。"
    )
    lines.append("")
    lines.append("> 此前的 87.0% 是 LLM 对 LLM 的一致性，不是人工验证。")
    lines.append("> 本报告用于人工双盲校准；TikTok 与 Reddit 必须分开看，不能用一个 ALL 数字糊过去。")
    lines.append("")

    lines.append("## 1 结论摘要")
    lines.append("")
    lines.append(
        "| 信源 | 条数 | 单元格 | 人+ | LLM+ | 双方+ | 人独有 | LLM 独有 | 一致率 | κ (micro) | κ (macro) | 等级 (micro) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for name in SOURCE_ORDER:
        if name not in by_source:
            continue
        row = summary_row(name, by_source[name])
        lines.append(
            "| {name} | {n_items} | {n_cells} | {human_positive} | {llm_positive} | "
            "{both_positive} | {human_only} | {llm_only} | {raw} | {micro} | {macro} | {grade} |".format(
                name=row["name"],
                n_items=row["n_items"],
                n_cells=row["n_cells"],
                human_positive=row["human_positive"],
                llm_positive=row["llm_positive"],
                both_positive=row["both_positive"],
                human_only=row["human_only"],
                llm_only=row["llm_only"],
                raw=format_pct(row["raw_agreement"]),
                micro=format_number(row["kappa_micro"]),
                macro=format_number(row["kappa_macro"]),
                grade=row["interpretation_micro"],
            )
        )
    all_row = summary_row("ALL（仅汇总）", all_stats)
    lines.append(
        "| {name} | {n_items} | {n_cells} | {human_positive} | {llm_positive} | "
        "{both_positive} | {human_only} | {llm_only} | {raw} | {micro} | {macro} | {grade} |".format(
            name=all_row["name"],
            n_items=all_row["n_items"],
            n_cells=all_row["n_cells"],
            human_positive=all_row["human_positive"],
            llm_positive=all_row["llm_positive"],
            both_positive=all_row["both_positive"],
            human_only=all_row["human_only"],
            llm_only=all_row["llm_only"],
            raw=format_pct(all_row["raw_agreement"]),
            micro=format_number(all_row["kappa_micro"]),
            macro=format_number(all_row["kappa_macro"]),
            grade=all_row["interpretation_micro"],
        )
    )
    lines.append("")
    lines.append(
        "**总体 κ（micro）= {}；macro = {}。** ALL 行只用于汇总，不能替代分信源结论。".format(
            format_number(micro), format_number(macro)
        )
    )
    if aspects_below_060:
        lines.append("")
        lines.append(
            "- κ < 0.60 的 aspect：{} 个；最低 κ = {}。涉及：{}{}。".format(
                len(aspects_below_060),
                format_number(min_aspect_kappa),
                "、".join(
                    f"{stats['label']}（{stats['code']}）"
                    for stats in aspects_below_060[:5]
                ),
                " 等" if len(aspects_below_060) > 5 else "",
            )
        )
    lines.append("")
    lines.append(
        "> 注意：micro κ 对低阳性比例很敏感。样本里绝大多数 item×aspect 单元格是"
        "「双方都没标」，这些单元格会抬高一致率。即使漏掉三分之一的正向 aspect，"
        "micro κ 仍可能看起来不低。因此必须同时看逐 aspect κ、macro κ 和第 7 节的分歧清单。"
    )
    lines.append("")
    lines.append("等级按 Landis & Koch 常用分档：≥0.80 almost perfect；≥0.60 substantial；"
                 "≥0.40 moderate；≥0.20 fair；≥0 slight；<0 poor。")
    lines.append("")

    lines.append("## 2 分信源")
    lines.append("")
    for name in SOURCE_ORDER:
        if name not in by_source:
            continue
        stats = by_source[name]
        lines.append(f"### {name}（{stats['n_items']} 条，{stats['n_cells']} 个判断单元格）")
        lines.append("")
        lines.append(
            f"- 人类标注阳性：{stats['pooled']['a'] + stats['pooled']['b']}；"
            f"LLM 阳性：{stats['pooled']['a'] + stats['pooled']['c']}；"
            f"双方都标：{stats['pooled']['a']}。"
        )
        lines.append(
            f"- 一致率：{format_pct(stats['raw_agreement'])}；"
            f"κ (micro)：{format_number(stats['kappa_micro'])}（{interpretation(stats['kappa_micro'])}）；"
            f"κ (macro)：{format_number(stats['kappa_macro'])}（{interpretation(stats['kappa_macro'])}）。"
        )
        lines.append(
            f"- 有阳性的 aspect：{stats['active_aspects']} 个；"
            f"κ 可计算的 aspect：{stats['defined_aspects']} 个。"
        )
        lines.append("")

    lines.append("## 3 逐 aspect（ALL 20 条）")
    lines.append("")
    lines.append("| Aspect | 系列 | 人+ | LLM+ | 双方+ | 不一致 | 一致率 | κ | 等级 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for code in taxonomy["codes"]:
        stats = all_stats["per_aspect"][code]
        if not stats["active"]:
            lines.append(
                "| {} | {} | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |".format(
                    md_escape(f"{stats['label']}（{code}）"),
                    md_escape(stats["family_label"]),
                )
            )
            continue
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                md_escape(f"{stats['label']}（{code}）"),
                md_escape(stats["family_label"]),
                stats["human_positive"],
                stats["llm_positive"],
                stats["both_positive"],
                stats["total_mismatch"],
                format_pct(stats["observed_agreement"]),
                format_number(stats["kappa"]),
                interpretation(stats["kappa"]),
            )
        )
    lines.append("")
    lines.append(
        "「不一致」= 一方标了另一方没标（presence）+ 双方都标但极性不同（polarity）。"
        "κ 只使用 presence 二值；极性差异不计入 κ，但在「不一致」列和 top 5 中单列。"
    )
    lines.append("")

    lines.append("## 4 分信源逐 aspect κ")
    lines.append("")
    header = "| Aspect | TikTok κ | TikTok 一致率 | Reddit κ | Reddit 一致率 | ALL κ |"
    lines.append(header)
    lines.append("|---|---:|---:|---:|---:|---:|")
    for code in taxonomy["codes"]:
        cells = []
        for name in ("TikTok", "Reddit"):
            if name in by_source:
                stats = by_source[name]["per_aspect"][code]
                if stats["active"]:
                    cells.append(format_number(stats["kappa"]))
                    cells.append(format_pct(stats["observed_agreement"]))
                else:
                    cells.append("—")
                    cells.append("—")
            else:
                cells.append("—")
                cells.append("—")
        all_stats_aspect = all_stats["per_aspect"][code]
        all_kappa = (
            format_number(all_stats_aspect["kappa"])
            if all_stats_aspect["active"]
            else "—"
        )
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                md_escape(f"{all_stats_aspect['label']}（{code}）"),
                cells[0],
                cells[1],
                cells[2],
                cells[3],
                all_kappa,
            )
        )
    lines.append("")
    lines.append(
        f"TikTok 每格 n={sample_counts.get('TikTok', 0)} 条；"
        f"Reddit 每格 n={sample_counts.get('Reddit', 0)} 条；ALL 每格 n={len(sample)} 条。"
        "n/a 表示该 aspect 在该信源里没有阳性或没有方差。"
    )
    lines.append("")

    lines.append("## 5 极性一致率")
    lines.append("")
    lines.append(
        "只统计双方都标了同一个 aspect 的单元格。exact = 极性字符串完全相同；"
        "family = 把 qualified_positive/qualified_negative 折叠成正/负后再比。"
    )
    lines.append("")
    lines.append("| Aspect | 双方都标 | 极性 exact | exact 一致率 | family 一致 | family 一致率 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    polarity_rows = 0
    for code in taxonomy["codes"]:
        stats = all_stats["per_aspect"][code]
        if stats["both_present"] == 0:
            continue
        polarity_rows += 1
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                md_escape(f"{stats['label']}（{code}）"),
                stats["both_present"],
                stats["polarity_exact"],
                format_pct(stats["polarity_exact_rate"]),
                stats["polarity_family"],
                format_pct(stats["polarity_family_rate"]),
            )
        )
    if polarity_rows == 0:
        lines.append("| — | 0 | 0 | — | 0 | — |")
    lines.append("")

    lines.append("## 6 产品体验判定一致性")
    lines.append("")
    lines.append("这一项只看「这条在评价产品吗？」的是/否，不看 aspect。")
    lines.append("")
    lines.append("| | LLM 是 | LLM 否 |")
    lines.append("|---|---:|---:|")
    lines.append(f"| 人 是 | {gate_stats['a']} | {gate_stats['b']} |")
    lines.append(f"| 人 否 | {gate_stats['c']} | {gate_stats['d']} |")
    lines.append("")
    lines.append(
        f"一致率：{format_pct(gate_stats['observed_agreement'])}；"
        f"κ：{format_number(gate_stats['kappa'])}（{gate_stats['interpretation']}）。"
    )
    lines.append("")

    lines.append(f"## 7 分歧最大的 top {args.top_n} aspect")
    lines.append("")
    if trigger_top5:
        lines.append(
            "> 触发条件：总体 κ < 0.60，或至少一个 aspect 的 κ < 0.60。"
            "本次 micro κ = {}，macro κ = {}，最低 aspect κ = {}。".format(
                format_number(micro),
                format_number(macro),
                format_number(min_aspect_kappa),
            )
        )
        lines.append("")
        if not top_disagreements:
            lines.append("没有发现 aspect 级分歧。")
            lines.append("")
        for index, stats in enumerate(top_disagreements, start=1):
            lines.append(
                f"### {index}. {stats['label']}（{stats['code']}）"
            )
            lines.append("")
            lines.append(
                f"- κ(ALL)：{format_number(stats['kappa'])}；"
                f"人+：{stats['human_positive']}；LLM+：{stats['llm_positive']}；"
                f"双方+：{stats['both_positive']}。"
            )
            lines.append(
                f"- 存在分歧的单元格：{stats['total_mismatch']} 个"
                f"（presence {stats['presence_mismatch']} + polarity {stats['polarity_mismatch']}）。"
            )
            lines.append("")
            lines.append("| 题目 | 人工标注 | LLM 标注 |")
            lines.append("|---|---|---|")
            for mismatch in stats["mismatches"]:
                lines.append(
                    "| {} | {} | {} |".format(
                        md_escape(mismatch["item_id"]),
                        md_escape(format_annotation(mismatch["human"])),
                        md_escape(format_annotation(mismatch["llm"])),
                    )
                )
            lines.append("")
    else:
        lines.append(
            "> 未触发：总体 κ 不低于 0.60（micro = {}，macro = {}）。".format(
                format_number(micro), format_number(macro)
            )
        )
        lines.append("")

    lines.append("## 8 怎么读这份报告")
    lines.append("")
    lines.append(
        "- κ ≥ 0.60 是 substantial，κ ≥ 0.80 是 almost perfect。低于 0.60 时，"
        "先看第 7 节的分歧条目，判断是 taxonomy 定义不清、极性判断不同，还是 LLM 确实标错。"
    )
    lines.append(
        "- 20 条样本很小，逐 aspect κ 很不稳定；它用于发现系统性问题，不适合当作精确的精度估计。"
    )
    lines.append(
        "- micro κ 会被大量「双方都没标」的单元格抬高。判断 LLM 是否漏标时，"
        "优先看逐 aspect κ、macro κ 和 top 5 中的 presence 分歧，不要只报一个 micro κ。"
    )
    lines.append(
        "- 样本只抽了「至少有一个 high aspect」的记录，因此这里的 κ 是 high-only 输出的"
        "一致性审计，不是全语料的 precision/recall。"
    )
    lines.append(
        "- 不要根据这份报告改 gold set，也不要改 claim 评级逻辑。若发现定义歧义，"
        "改 taxonomy 定义并重新抽样，而不是在这 20 条上反复调参。"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("gold set 未改动；counting / evidence / claims 逻辑未改动。")
    lines.append("")
    return "\n".join(lines)


def build_json(
    args: argparse.Namespace,
    sample: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    overall: dict[str, Any],
    by_source: dict[str, dict[str, Any]],
    gate_stats: dict[str, Any],
    top_disagreements: list[dict[str, Any]],
    trigger_top5: bool,
    min_aspect_kappa: float | None,
    aspects_below_060: list[dict[str, Any]],
) -> dict[str, Any]:
    sample_counts = {
        name: sum(1 for item in sample if source_display(item["source"]) == name)
        for name in SOURCE_ORDER
    }

    def clean_stats(stats: dict[str, Any]) -> dict[str, Any]:
        out = dict(stats)
        out["interpretation"] = interpretation(stats["kappa"])
        return out

    return {
        "schema": "voc-kappa-metrics-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "sample": str(args.sample),
            "human": str(args.human),
            "mapping": str(args.mapping),
            "coded": str(args.coded),
            "taxonomy": str(args.taxonomy),
            "min_confidence": args.min_confidence,
            "top_n": args.top_n,
        },
        "sample": {
            "total": len(sample),
            "by_source": sample_counts,
        },
        "source_summary": {
            name: summary_row(name, stats) for name, stats in by_source.items()
        },
        "overall": summary_row("ALL", overall),
        "per_aspect": {
            code: {
                "label": stats["label"],
                "family": stats["family"],
                "family_label": stats["family_label"],
                "ALL": clean_stats(overall["per_aspect"][code]),
                "TikTok": clean_stats(by_source["TikTok"]["per_aspect"][code])
                if "TikTok" in by_source
                else None,
                "Reddit": clean_stats(by_source["Reddit"]["per_aspect"][code])
                if "Reddit" in by_source
                else None,
            }
            for code, stats in overall["per_aspect"].items()
        },
        "experience_gate": gate_stats,
        "top_disagreements": [
            {
                "code": stats["code"],
                "label": stats["label"],
                "kappa": stats["kappa"],
                "total_mismatch": stats["total_mismatch"],
                "presence_mismatch": stats["presence_mismatch"],
                "polarity_mismatch": stats["polarity_mismatch"],
                "mismatches": stats["mismatches"],
            }
            for stats in top_disagreements
        ],
        "top_disagreements_triggered": trigger_top5,
        "min_aspect_kappa": min_aspect_kappa,
        "aspects_below_060": [
            {
                "code": stats["code"],
                "label": stats["label"],
                "kappa": stats["kappa"],
                "presence_mismatch": stats["presence_mismatch"],
                "polarity_mismatch": stats["polarity_mismatch"],
            }
            for stats in aspects_below_060
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="计算人工标注与 LLM 标注的 Cohen's kappa（仅标准库）"
    )
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE, help="blind-sample.jsonl")
    parser.add_argument("--human", type=Path, required=True, help="label.html 导出的 JSON")
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING, help="mapping.json")
    parser.add_argument("--coded", type=Path, default=DEFAULT_CODED, help="coded/ALL.jsonl")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY, help="taxonomy.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Markdown 报告输出路径")
    parser.add_argument("--json-out", type=Path, default=None, help="可选：机器可读指标 JSON")
    parser.add_argument(
        "--min-confidence",
        choices=("high", "medium", "all"),
        default="high",
        help="LLM 参考口径；默认 high（只采信 high 置信度）",
    )
    parser.add_argument("--top-n", type=int, default=5, help="分歧最大的 aspect 数量")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top_n < 1:
        print("错误：--top-n 必须 >= 1", file=sys.stderr)
        return 2

    try:
        taxonomy = load_taxonomy(args.taxonomy)
        sample = load_sample(args.sample)
        mapping = load_mapping(args.mapping, sample)
        human = load_human(args.human, sample, taxonomy)
        llm = load_llm(args.coded, sample, mapping, taxonomy, args.min_confidence)

        # Optional guard: if the human export carries a sample_id and mapping
        # carries one too, they must agree.
        try:
            human_raw = load_json(args.human)
            mapping_raw = load_json(args.mapping)
            human_sample_id = human_raw.get("sample_id") if isinstance(human_raw, dict) else None
            mapping_sample_id = mapping_raw.get("sample_id") if isinstance(mapping_raw, dict) else None
            if human_sample_id and mapping_sample_id and human_sample_id != mapping_sample_id:
                raise CalibrationError(
                    "人工标注文件的 sample_id 与 mapping 不一致："
                    f"{human_sample_id} != {mapping_sample_id}。"
                    "请确认导出文件属于本样本。"
                )
        except CalibrationError:
            raise
        except Exception:
            pass

        by_source: dict[str, dict[str, Any]] = {}
        for name in SOURCE_ORDER:
            items = [item for item in sample if source_display(item["source"]) == name]
            if items:
                by_source[name] = analyze_subset(items, human, llm, taxonomy)
        overall = analyze_subset(sample, human, llm, taxonomy)
        gate_stats = analyze_gate(sample, human, llm)

        micro = overall["kappa_micro"]
        macro = overall["kappa_macro"]
        defined_aspect_stats = [
            stats
            for stats in overall["per_aspect"].values()
            if stats["kappa"] is not None
        ]
        min_aspect_kappa = (
            min(stats["kappa"] for stats in defined_aspect_stats)
            if defined_aspect_stats
            else None
        )
        aspects_below_060 = sorted(
            [
                stats
                for stats in defined_aspect_stats
                if stats["kappa"] < 0.60
            ],
            key=lambda stats: (stats["kappa"], -stats["total_mismatch"], stats["code"]),
        )
        trigger_top5 = (
            (micro is not None and micro < 0.60)
            or (macro is not None and macro < 0.60)
            or bool(aspects_below_060)
        )
        top_disagreements = ranked_disagreements(overall["per_aspect"], args.top_n) if trigger_top5 else []

        report = build_report(
            args,
            sample,
            taxonomy,
            overall,
            by_source,
            gate_stats,
            top_disagreements,
            trigger_top5,
            min_aspect_kappa,
            aspects_below_060,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8", newline="\n")

        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            payload = build_json(
                args,
                sample,
                taxonomy,
                overall,
                by_source,
                gate_stats,
                top_disagreements,
                trigger_top5,
                min_aspect_kappa,
                aspects_below_060,
            )
            with args.json_out.open("w", encoding="utf-8", newline="\n") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.write("\n")

    except CalibrationError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    print(f"报告：{args.out}")
    for name in SOURCE_ORDER:
        if name not in by_source:
            continue
        stats = by_source[name]
        print(
            f"{name}: n={stats['n_items']}, raw={format_pct(stats['raw_agreement'])}, "
            f"kappa_micro={format_number(stats['kappa_micro'])}, "
            f"kappa_macro={format_number(stats['kappa_macro'])}"
        )
    print(
        f"ALL: n={overall['n_items']}, raw={format_pct(overall['raw_agreement'])}, "
        f"kappa_micro={format_number(overall['kappa_micro'])}, "
        f"kappa_macro={format_number(overall['kappa_macro'])}, "
        f"min_aspect_kappa={format_number(min_aspect_kappa)}, "
        f"top5_triggered={trigger_top5}"
    )
    if args.json_out:
        print(f"JSON：{args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
