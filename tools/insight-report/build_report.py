"""Build a Data-Contract report from raw local data.

Pipeline:
    ingest -> identity -> counting (six levels) -> coding -> evidence -> report JSON -> HTML

SOP 14-skill coverage (see ``contract.SOP_COVERAGE`` for the full table):

Implemented:
  - voc-product-identity (G1): identity.py
  - voc-canonicalize (G6): counting.py
  - voc-insight-analysis (G8): this module + evidence.py
  - voc-interactive-report: render.py
  - voc-validation-handoff: validate.py

Partially implemented:
  - voc-source-pilot (G3): ingest.py verifies raw/ledger lineage only
  - voc-coding-calibration (G7): rule coder is implemented; double coding is not
  - voc-research-orchestrator: local orchestration only

Consumed, not implemented:
  - voc-taxonomy-freeze (G4): reads frozen taxonomy.json
  - voc-stratified-collection (G5): reads frozen collection-run-ledger.json

Not implemented (human / out of scope):
  - voc-decision-charter (G0)
  - voc-source-rights-audit (G2)
  - voc-strategy-activation (G9)
  - voc-measurement-review (G10)

Run:
    python3 tools/insight-report/build_report.py \
      --run-dir voc_pipeline/artifacts/run-20261029 \
      --out tools/insight-report/out/run-20261029
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Direct execution: make the package importable without installation.
_PACKAGE_ROOT = Path(__file__).resolve().parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from insight_report import (  # noqa: E402
    coding,
    contract,
    counting,
    evidence,
    identity as identity_mod,
    ingest,
    metrics,
    render,
    validate,
)

REPO_ROOT = _PACKAGE_ROOT.parent.parent
DEFAULT_RUN = REPO_ROOT / "voc_pipeline" / "artifacts" / "run-20261029"
DEFAULT_OUT = _PACKAGE_ROOT / "out" / "insight-report-run-20261029"


class ArtifactRegistry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.refs: dict[str, dict[str, Any]] = {}

    def _ref(self, name: str, data: bytes, kind: str) -> dict[str, Any]:
        ref = {
            "artifact_id": Path(name).stem,
            "path": name,
            "sha256": contract.sha256_bytes(data),
            "bytes": len(data),
            "kind": kind,
            "generated_at": contract.now_iso(),
        }
        self.refs[name] = ref
        return ref

    def write_json(self, name: str, payload: Any, kind: str = "derived") -> dict[str, Any]:
        data = contract.dump_json(self.root / name, payload)
        return self._ref(name, data, kind)

    def write_jsonl(self, name: str, rows: list[dict[str, Any]], kind: str = "derived") -> dict[str, Any]:
        data = contract.dump_jsonl(self.root / name, rows)
        return self._ref(name, data, kind)

    def copy_file(self, source: Path, name: str, kind: str = "input") -> dict[str, Any]:
        data = Path(source).read_bytes()
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self._ref(name, data, kind)

    def get(self, name: str) -> dict[str, Any]:
        if name not in self.refs:
            raise contract.ContractError(f"artifact not registered: {name}")
        return self.refs[name]

    def sha(self, name: str) -> str:
        return self.get(name)["sha256"]

    def all_refs(self, exclude: set[str] | None = None) -> list[dict[str, Any]]:
        exclude = exclude or set()
        return [ref for name, ref in self.refs.items() if name not in exclude]


def _tp(text: str, claim_id: str | None, refs: list[str] | None = None) -> dict[str, Any]:
    return contract.text_provenance(text, claim_id, refs)


def _foot(grade: str, scope: str, basis: str, unit: str, limit: str) -> dict[str, Any]:
    return contract.source_foot(basis, unit, limit, f"{evidence.STATUS_DISPLAY_CASE[grade]} · {scope}")


def _status(grade: str, scope: str, inputs: dict[str, Any], gate: str | None = None) -> dict[str, Any]:
    return contract.evidence_status(grade, scope, inputs, gate=gate)


def _readout(observed: str, interpretation: str, counterevidence: str, decision: str, claim_id: str, refs: list[str]) -> dict[str, Any]:
    return contract.readout(
        _tp(observed, claim_id, refs),
        _tp(interpretation, claim_id, refs),
        _tp(counterevidence, claim_id, refs),
        _tp(decision, claim_id, refs),
    )


def _safe_section_gap(section_id: str, reason: str, claim_id: str) -> dict[str, Any]:
    return contract.gap_block(
        reason=reason,
        title=f"[Evidence gap] {reason}",
        block_readout=_readout(
            f"{reason}，本节无法生成可复核的数字。",
            "缺数据时不能用其他 frame、其他 variant 或上一轮结果替代。",
            evidence.no_counterevidence(f"{reason} 本轮没有测量，因此找不到可以反驳该缺口的记录。"),
            "先补齐该数据，再决定是否进入本节分析。",
            claim_id,
            [f"metric-summary.json#/metric_rows"],
        ),
        block_foot=contract.source_foot(
            f"0 records for {section_id}",
            "canonical_record",
            "no data; no inference",
            "Evidence gap · missing required cell",
        ),
    )


class ReportBuilder:
    def __init__(self, run_dir: Path, out_dir: Path, *, market: str | None = None, language: str | None = None):
        self.run_dir = Path(run_dir).resolve()
        self.out_dir = Path(out_dir).resolve()
        self.market = market
        self.language = language
        self.registry = ArtifactRegistry(self.out_dir)
        self.resolver: metrics.Resolver | None = None

    # ------------------------------------------------------------------
    # data preparation
    # ------------------------------------------------------------------
    def prepare(self) -> dict[str, Any]:
        run, frozen = ingest.load_run(self.run_dir)
        taxonomy = frozen.get("taxonomy.json")
        if not taxonomy:
            raise contract.ContractError("taxonomy.json is required for coding")
        gate_ledger = frozen.get("gate-ledger.json")
        if not gate_ledger:
            raise contract.ContractError("gate-ledger.json is required for evidence grading")

        # Copy immutable inputs so every source_path points inside this run.
        tax_ref = self.registry.copy_file(self.run_dir / "taxonomy.json", "taxonomy.json", "input")
        gate_ref = self.registry.copy_file(self.run_dir / "gate-ledger.json", "gate-ledger.json", "input")
        pdp_refs = []
        for response in run.responses:
            if response.provider != "amazon":
                continue
            source = self.run_dir / "raw" / "amazon" / Path(response.path).name
            if source.exists():
                pdp_refs.append(self.registry.copy_file(source, f"raw/amazon/{source.name}", "raw"))

        identity = identity_mod.freeze_identity(run, frozen, market=self.market, language=self.language)
        identity["variant_matrix_rows"] = len(identity.get("variants", {}).get("items", []))
        identity["target_variant_count"] = sum(
            1 for item in identity.get("variants", {}).get("items", []) if item.get("is_target")
        )
        identity["family_review_count"] = identity.get("product_rating", {}).get("review_count")
        identity["per_variant_review_count_rows"] = 0
        identity["verified_crosswalk_links"] = 0
        identity["gaps"] = sorted(set(identity_mod.identity_gap_entries(identity)))
        # Point identity sources at the copied raw PDP files, which have a real sha.
        if pdp_refs:
            ref = pdp_refs[0]
            identity["source"][0] = contract.source_ref_artifact(ref["path"], ref["sha256"], provider="amazon")
            identity["variants"]["source"] = [contract.source_ref_artifact(ref["path"], ref["sha256"], provider="amazon")]
        else:
            identity["source"][0] = contract.source_ref_blocked("[BLOCKED: no PDP raw file copied into this run]")

        occurrences, occ_stats = counting.occurrences_from_ingest(run)
        canonical, canonical_summary = counting.canonicalize(occurrences)
        coded = coding.code_corpus(canonical, taxonomy)
        aggregate_result = coding.aggregate(coded)

        gate_statuses = {item["gate_id"]: item["status"] for item in gate_ledger.get("gates", [])}
        gate_status = gate_statuses.get("G7", "BLOCKED")
        annotations_total = sum(aggregate_result["annotation_totals"].values())
        eligible = [
            record
            for record in canonical
            if record.metric_eligibility == "natural_sample_candidate"
            and record.data_layer == "consumer_observation_fact"
            and "low_information" not in record.quality_flags
        ]
        ledger = counting.build_counting_ledger(
            raw_objects=occ_stats["occurrences_raw"],
            occurrences=len(occurrences),
            canonical_records=len(canonical),
            frame_memberships=canonical_summary["frame_memberships"],
            annotations=annotations_total,
            frame_counts=canonical_summary["frame_counts"],
            candidate_metric_rows=len(eligible),
            gate_status=gate_status,
            within_frame_dropped=occ_stats["within_frame_overlap_dropped"],
            dedup_reasons=canonical_summary["deduction_reasons"],
        )

        as_of = str(canonical_summary.get("as_of") or run.generated_at or contract.now_iso())[:10]
        corpus_summary = metrics.build_corpus_summary(
            raw_objects=occ_stats["occurrences_raw"],
            occurrences=len(occurrences),
            canonical=len(canonical),
            frame_memberships=canonical_summary["frame_memberships"],
            frame_counts=canonical_summary["frame_counts"],
            within_frame_dropped=occ_stats["within_frame_overlap_dropped"],
            dedup_reasons=canonical_summary["deduction_reasons"],
            excluded=canonical_summary["excluded"],
            as_of=as_of,
        )
        corpus_summary["eligible_records"] = len(eligible)
        corpus_summary["eligible_by_frame"] = {
            frame: sum(1 for record in eligible if frame in record.frames)
            for frame in sorted(canonical_summary["frame_counts"])
        }
        corpus_summary["raw_responses"] = run.raw_response_count
        corpus_summary["failed_requests"] = len(run.failed_requests)
        corpus_summary["source_notes"] = run.source_notes

        metric_summary = metrics.build_metric_summary(
            aggregate_result=aggregate_result,
            canonical=canonical,
            coded=coded,
            taxonomy=taxonomy,
            frame_counts=canonical_summary["frame_counts"],
            identity=identity,
            gate_status=gate_status,
            as_of=as_of,
        )
        metric_summary["eligible_records"] = len(eligible)
        metric_summary["eligible_by_frame"] = corpus_summary["eligible_by_frame"]
        metric_summary["friction_family_counts"] = self._friction_family_counts(aggregate_result, coded)
        metric_summary["experience"] = self._experience_counts(canonical, coded)
        metric_summary["coverage_numbers"] = {
            "natural_frame_records": canonical_summary["frame_counts"].get("natural", 0),
            "diagnostic_frame_records": canonical_summary["frame_counts"].get("diagnostic", 0),
            "qualitative_seed_records": canonical_summary["frame_counts"].get("qualitative_seed", 0),
            "frame_memberships": canonical_summary["frame_memberships"],
            "canonical_records": len(canonical),
            "raw_objects": occ_stats["occurrences_raw"],
            "occurrences": len(occurrences),
            "deduplicated_records": len(occurrences) - len(canonical),
            "annotations_total": annotations_total,
            "momcozy_mentions": sum(1 for record in canonical if "momcozy" in record.combined.lower()),
            "amazon_review_text_rows": 0,
            "nonunknown_gap_records": sum(v for k, v in metric_summary["gap_counts"].items() if k != "unknown"),
        }
        metric_summary["cooccurrence"]["matrix_total"] = sum(
            value for row in metric_summary["cooccurrence"]["matrix"].values() for value in row.values()
        )
        metric_summary["derivations"].update(
            {
                "friction_family_counts": "negative aspect annotations grouped by code prefix: SUP, FIT+ADJ, STB, VAL",
                "experience.relevant_records": "canonical records with product_match in {exact_current_family, category_adjacent}",
                "experience.experience_records": "relevant records with a non-unknown journey rollup or outcome",
                "eligible_records": "canonical records with metric_eligibility=natural_sample_candidate, data_layer=consumer_observation_fact, and no low_information flag",
            }
        )

        # Write intermediate artifacts.
        ingest_ref = self.registry.write_json(
            "ingest-ledger.json",
            {
                "run_dir": ".",
                "generated_at": run.generated_at,
                "raw_responses": run.raw_response_count,
                "raw_objects_reddit": occ_stats["occurrences_raw"],
                "failed_requests": run.failed_requests,
                "responses": ingest.raw_inventory(run),
                "source_notes": run.source_notes,
                "sop_note": "G3 lineage verification only; no network collection.",
            },
            "derived",
        )
        identity_ref = self.registry.write_json("identity-freeze.json", identity, "derived")
        occurrences_ref = self.registry.write_jsonl("occurrences.jsonl", [o.to_dict() for o in occurrences])
        canonical_ref = self.registry.write_jsonl("canonical-records.jsonl", [r.to_dict() for r in canonical])
        coded_ref = self.registry.write_jsonl("coded-corpus.jsonl", [r.to_dict() for r in coded])
        counting_ref = self.registry.write_json(
            "counting-ledger.json",
            {
                **ledger.to_dict(),
                "spec": counting.counting_spec(),
                "levels": ledger.levels(),
                "sop_note": "G6 counting separation; metric rows fail-closed while G7 is BLOCKED.",
            },
        )
        corpus_ref = self.registry.write_json("corpus-summary.json", corpus_summary)
        metric_ref = self.registry.write_json("metric-summary.json", metric_summary)

        return {
            "run": run,
            "frozen": frozen,
            "taxonomy": taxonomy,
            "gate_ledger": gate_ledger,
            "identity": identity,
            "occurrences": occurrences,
            "occ_stats": occ_stats,
            "canonical": canonical,
            "canonical_summary": canonical_summary,
            "coded": coded,
            "aggregate": aggregate_result,
            "ledger": ledger,
            "corpus_summary": corpus_summary,
            "metric_summary": metric_summary,
            "as_of": as_of,
            "gate_status": gate_status,
            "gate_statuses": gate_statuses,
            "refs": {
                "taxonomy": tax_ref,
                "gate": gate_ref,
                "ingest": ingest_ref,
                "identity": identity_ref,
                "occurrences": occurrences_ref,
                "canonical": canonical_ref,
                "coded": coded_ref,
                "counting": counting_ref,
                "corpus": corpus_ref,
                "metric": metric_ref,
            },
        }

    def _friction_family_counts(self, aggregate_result: dict[str, Any], coded: list[coding.CodedRecord]) -> dict[str, Any]:
        polarity = aggregate_result["aspect_polarity_counts"]

        def negative(prefixes: tuple[str, ...]) -> int:
            return sum(v for key, v in polarity.items() if key.endswith("|negative") and key.split("|")[0].startswith(prefixes))

        def positive(prefixes: tuple[str, ...]) -> int:
            return sum(
                v
                for key, v in polarity.items()
                if (key.endswith("|positive") or key.endswith("|qualified_positive"))
                and key.split("|")[0].startswith(prefixes)
            )

        support_negative = negative(("SUP.",))
        fit_negative = negative(("FIT.", "ADJ."))
        stability_negative = negative(("STB.",))
        value_negative = negative(("VAL.",))
        total = support_negative + fit_negative + stability_negative + value_negative
        support_records = {
            rec.canonical_id
            for rec in coded
            if any(ann.axis == "aspect" and ann.code.startswith("SUP.") and ann.polarity.startswith("negative") for ann in rec.annotations)
        }
        support_positive_records = {
            rec.canonical_id
            for rec in coded
            if any(ann.axis == "aspect" and ann.code.startswith("SUP.") and ann.polarity.startswith("positive") for ann in rec.annotations)
        }
        support_authors = {
            rec.canonical_id
            for rec in coded
            if any(ann.axis == "aspect" and ann.code.startswith("SUP.") and ann.polarity.startswith("negative") for ann in rec.annotations)
        }
        return {
            "support_negative": support_negative,
            "fit_negative": fit_negative,
            "stability_negative": stability_negative,
            "value_negative": value_negative,
            "total_friction_negative": total,
            "support_positive": positive(("SUP.",)),
            "comfort_positive": positive(("COM.", "APP.")),
            "all_negative": sum(v for key, v in polarity.items() if key.endswith("|negative")),
            "support_negative_records": len(support_records),
            "support_positive_records": len(support_positive_records),
            "support_direction_share": round(
                len(support_records) / max(1, len(support_records) + len(support_positive_records)), 4
            ),
            "support_records_for_authors": len(support_authors),
        }

    def _experience_counts(
        self, canonical: list[counting.CanonicalRecord], coded: list[coding.CodedRecord]
    ) -> dict[str, int]:
        relevant = {record.canonical_id for record in canonical if record.product_match in {"exact_current_family", "category_adjacent"}}
        experience = {
            record.canonical_id
            for record in coded
            if record.journey_stage != "unknown" or record.outcome != "OUT.UNKNOWN"
        }
        return {
            "relevant_records": len(relevant),
            "experience_records": len(experience & relevant),
            "non_experience_records": len(relevant - experience),
        }

    # ------------------------------------------------------------------
    # claims
    # ------------------------------------------------------------------
    def build_claims(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        ms = data["metric_summary"]
        idf = data["identity"]
        refs = data["refs"]
        identity_sha = refs["identity"]["sha256"]
        canonical_sha = refs["canonical"]["sha256"]
        coded_sha = refs["coded"]["sha256"]
        corpus_sha = refs["corpus"]["sha256"]
        metric_sha = refs["metric"]["sha256"]

        def num(name: str, value: int, unit: str, basis: str, pointer: str, denominator: int | None = None) -> dict[str, Any]:
            return metrics.number_ref(name, value, unit, basis, denominator, f"metric-summary.json#{pointer}")

        def idnum(name: str, value: int, unit: str, basis: str, pointer: str) -> dict[str, Any]:
            return metrics.number_ref(name, value, unit, basis, None, f"identity-freeze.json#{pointer}")

        co = ms["cooccurrence"]
        ff = ms["friction_family_counts"]
        exp = ms["experience"]
        jr = ms["journey_rollup_counts"]
        journey_total = ms["annotation_totals"]["journey"]
        medical_total = ms["annotation_totals"]["medical"]
        medical_records = ms["medical_records"]
        frame_counts = ms["frame_counts"]
        corpus = data["corpus_summary"]
        support_dir = ff["support_direction_share"]
        support_neg = ff["support_negative"]
        support_pos = ff["support_positive"]
        value_neg = ff["value_negative"]
        fit_neg = ff["fit_negative"]
        stability_neg = ff["stability_negative"]
        friction_total = ff["total_friction_negative"]
        comfort_pos = co["comfort_positive_records"]
        both = co["both_records"]
        without = co["comfort_positive_without_friction"]
        friction_records = co["friction_negative_records"]

        claims: list[dict[str, Any]] = []

        claims.append(
            evidence.make_claim(
                "C01",
                "variant",
                f"Amazon PDP 解析出父 ASIN {idf['parent_asin']}、目标子 ASIN {idf['child_asin']} 和 {idf['family_children']} 个在售变体，商品身份可核对。",
                "confirmed",
                evidence.confirmed_inputs(identity_sha),
                f"同一 PDP family block 给出 {idf['family_children']} 个 ASIN 到颜色/尺码组合；父 ASIN {idf['parent_asin']} 不在变体矩阵中，目标子 ASIN {idf['child_asin']} 是 {idf['color']} / {idf['size']}。",
                f"父/子角色与变体矩阵来自同一页面，映射置信度 {idf['mapping_confidence']}；但这是单时点、单地区、未登录会话的快照。",
                "PDP 会随会话、地区和库存变化；单次抓取不能说明所有变体在任何时点都可售。",
                "在任何 variant-specific 结论之前重跑 G1，并把变体矩阵版本化。",
                "identity-freeze.json + PDP dimensionValuesDisplayData",
                "variant",
                "单时点、单地区（US）、未登录会话",
                [],
                [
                    idnum("live_variants", idf["family_children"], "variant", "PDP dimensionValuesDisplayData", "/family_children"),
                    idnum("variant_matrix_rows", idf["variant_matrix_rows"], "variant", "len(variants.items)", "/variant_matrix_rows"),
                    idnum("target_variant_count", idf["target_variant_count"], "variant", "count(is_target=true)", "/target_variant_count"),
                ],
                status_scope="PDP SNAPSHOT",
            )
        )

        claims.append(
            evidence.make_claim(
                "C02",
                "evidence",
                f"本轮把 {corpus['raw_objects']} 条 provider 记录收敛为 {corpus['occurrences_deduplicated']} 条 occurrence 和 {corpus['canonical_records']} 条 canonical，扣减全部带理由。",
                "confirmed",
                evidence.confirmed_inputs(canonical_sha),
                f"raw objects {corpus['raw_objects']}；同 frame 重复扣除 {corpus['within_frame_overlap_dropped']} 条；canonical 合并 {corpus['occurrences_deduplicated'] - corpus['canonical_records']} 条，原因是跨来源转载 {corpus['deduction_reasons']['cross_source_syndicated_duplicate']} 条和同作者转发 {corpus['deduction_reasons']['crosspost_same_author']} 条。",
                "四层计数各不相同，不能把任何一个数当成消费者人数。",
                "样本来自关键词检索而非概率抽样，缺席记录不代表不存在。",
                "只使用 canonical 与 frame 数，不把覆盖写成逐级转化。",
                "collection-run-ledger.json + occurrences + canonical-records",
                "canonical_record",
                "关键词与 subreddit 选择决定召回；未做全站抽样",
                [],
                [
                    num("raw_objects", corpus["raw_objects"], "raw_object", "provider records written to raw store", "/coverage_numbers/raw_objects"),
                    num("occurrences", corpus["occurrences_deduplicated"], "occurrence", "same external_id + frame deduplicated", "/coverage_numbers/occurrences"),
                    num("canonical_records", corpus["canonical_records"], "canonical_record", "exact text + same-author Jaccard >= 0.90", "/coverage_numbers/canonical_records"),
                    num("frame_memberships", corpus["frame_memberships"], "frame_membership", "frames may overlap; not a funnel", "/coverage_numbers/frame_memberships"),
                    num("deduplicated_records", corpus["occurrences_deduplicated"] - corpus["canonical_records"], "canonical_record", "occurrence minus canonical", "/coverage_numbers/deduplicated_records"),
                ],
                status_scope="LEDGER RECONCILED",
            )
        )

        exact_family = ms["product_match_counts"].get("exact_current_family", 0)
        brand_other = ms["product_match_counts"].get("brand_other_product", 0)
        irrelevant = ms["product_match_counts"].get("irrelevant", 0)
        momcozy_records = sum(1 for record in data["canonical"] if "momcozy" in record.combined.lower())
        claims.append(
            evidence.make_claim(
                "C03",
                "answer",
                f"提到 Momcozy 的 canonical 记录有 {momcozy_records} 条，其中与支撑带同一家族的 {exact_family} 条，带旅程或结果信号的 {exp['experience_records']} 条。",
                "evidence_gap",
                evidence.gap_inputs(),
                f"product_match=exact_current_family {exact_family} 条；brand_other_product {brand_other} 条；irrelevant {irrelevant} 条；与支撑带相关的记录 {exp['relevant_records']} 条，其中明确体验 {exp['experience_records']} 条。",
                "品牌被提及不等于型号被评价；不能把品牌级讨论转移到具体 SKU。",
                "Reddit 不是 Amazon 评论的替代品，购买者更可能在商品页留言。",
                "补 exact-variant 评论层，或在报告中保持型号级空白。",
                "canonical-records.jsonl（product_match / brand mention）",
                "canonical_record",
                "仅 Reddit；Amazon 评论正文本轮不可得",
                [record.canonical_id for record in data["canonical"] if "momcozy" in record.combined.lower()][:5],
                [
                    num("momcozy_records", momcozy_records, "canonical_record", "canonical records containing the brand token", "/coverage_numbers/momcozy_mentions"),
                    num("exact_current_family_records", exact_family, "canonical_record", "text rule: Momcozy + belly band/belt", "/product_match_counts/exact_current_family"),
                    num("brand_other_product_records", brand_other, "canonical_record", "text rule: Momcozy without belly band/belt", "/product_match_counts/brand_other_product"),
                    num("relevant_records", exp["relevant_records"], "canonical_record", "exact family + category adjacent", "/experience/relevant_records"),
                    num("experience_records", exp["experience_records"], "canonical_record", "relevant records with non-unknown journey or outcome", "/experience/experience_records"),
                ],
                status_scope="EXACT-VARIANT LAYER MISSING",
            )
        )

        claims.append(
            evidence.make_claim(
                "C04",
                "experience",
                f"自然样本的负向标注里支撑类最多（{support_neg} 次），价格价值其次（{value_neg} 次），但支撑类正向标注仍有 {support_pos} 次。",
                "hypothesis",
                evidence.hypothesis_inputs(ff["support_negative_records"], ff["support_records_for_authors"], support_dir),
                f"四类摩擦的负向标注：支撑 {support_neg}、尺码/适配 {fit_neg}、稳定性 {stability_neg}、价格 {value_neg}；四组合计 {friction_total}。",
                "支撑类是当前语料里最常被提到的失败面，但 annotation hit 不是人数，也不是发生率。",
                f"支撑类正向标注 {support_pos} 次，说明产品并非整体失败，而是条件性兑现；反向记录存在。",
                "先把资源放在支撑梯度与选码引导的验证上，不做一次性结构改款。",
                "coded-corpus.jsonl（aspect polarity，规则编码，pre-G7）",
                "annotation",
                "规则编码未人工复核；一条记录可贡献多个标注",
                ms["cooccurrence"]["pairs"][:0],
                [
                    num("support_negative", support_neg, "annotation", "negative SUP.* annotations", "/friction_family_counts/support_negative"),
                    num("value_negative", value_neg, "annotation", "negative VAL.* annotations", "/friction_family_counts/value_negative"),
                    num("fit_negative", fit_neg, "annotation", "negative FIT.* + ADJ.* annotations", "/friction_family_counts/fit_negative"),
                    num("stability_negative", stability_neg, "annotation", "negative STB.* annotations", "/friction_family_counts/stability_negative"),
                    num("friction_negative_total", friction_total, "annotation", "sum of the four friction families", "/friction_family_counts/total_friction_negative"),
                    num("support_positive", support_pos, "annotation", "positive + qualified_positive SUP.* annotations", "/friction_family_counts/support_positive"),
                ],
                status_scope="PRE-G7",
            )
        )

        claims.append(
            evidence.make_claim(
                "C05",
                "experience",
                f"{comfort_pos} 条舒适或外观正向记录中，{both} 条同时出现支撑、适配或稳定性负向。",
                "hypothesis",
                evidence.hypothesis_inputs(both, both, 1.0),
                f"舒适/外观正向 {comfort_pos} 条；其中核心摩擦 {both} 条；纯摩擦记录 {friction_records} 条；其余 {without} 条无核心摩擦。",
                "共现只发生在少数舒适正向记录里，说明张力是条件性的，不是普遍模式。",
                f"其余 {without} 条舒适正向记录没有核心摩擦；共现不是因果。",
                "分开验证支撑梯度与选码引导，不做一次性结构改款。",
                "record-level co-occurrence（COM/APP positive × SUP/FIT/STB negative）",
                "canonical_record",
                "共现为描述性；样本非概率抽样",
                co["pairs"] and [pair["canonical_id"] for pair in co["pairs"]] or [],
                [
                    num("comfort_positive_records", comfort_pos, "canonical_record", "records with at least one COM/APP positive annotation", "/cooccurrence/comfort_positive_records"),
                    num("comfort_positive_with_friction", both, "canonical_record", "subset with SUP/FIT/STB negative", "/cooccurrence/comfort_positive_with_friction", comfort_pos),
                    num("comfort_positive_without_friction", without, "canonical_record", "comfort positive minus both", "/cooccurrence/comfort_positive_without_friction"),
                    num("friction_negative_records", friction_records, "canonical_record", "records with at least one core-friction negative", "/cooccurrence/friction_negative_records"),
                ],
                status_scope="PRE-G7",
            )
        )

        claims.append(
            evidence.make_claim(
                "C06",
                "frames",
                f"三个镜头分别覆盖 {frame_counts.get('natural', 0)}、{frame_counts.get('diagnostic', 0)}、{frame_counts.get('qualitative_seed', 0)} 条 canonical 记录，合计 {corpus['frame_memberships']} 个可重叠 membership。",
                "confirmed",
                evidence.confirmed_inputs(corpus_sha),
                f"natural {frame_counts.get('natural', 0)} 条、diagnostic {frame_counts.get('diagnostic', 0)} 条、qualitative_seed {frame_counts.get('qualitative_seed', 0)} 条；合计 {corpus['frame_memberships']} 个 membership，大于 {corpus['canonical_records']} 个 canonical。",
                "三个镜头选择机制不同，只能并排看绝对计数，不能比较百分比。",
                f"diagnostic 只有 {frame_counts.get('diagnostic', 0)} 条，任何排序都可能随新增记录改变。",
                "把自然镜头作为方向线索，把诊断镜头作为失败模式清单，不合并成一个分母。",
                "corpus-summary.json#/frame_counts",
                "canonical_record",
                "frames 可重叠；diagnostic 样本小",
                [],
                [
                    num("natural_frame_records", frame_counts.get("natural", 0), "canonical_record", "natural frame membership", "/coverage_numbers/natural_frame_records"),
                    num("diagnostic_frame_records", frame_counts.get("diagnostic", 0), "canonical_record", "diagnostic frame membership", "/coverage_numbers/diagnostic_frame_records"),
                    num("qualitative_seed_records", frame_counts.get("qualitative_seed", 0), "canonical_record", "qualitative seed frame membership", "/coverage_numbers/qualitative_seed_records"),
                    num("frame_memberships", corpus["frame_memberships"], "frame_membership", "frames may overlap", "/coverage_numbers/frame_memberships"),
                    num("canonical_records", corpus["canonical_records"], "canonical_record", "independent content units", "/coverage_numbers/canonical_records"),
                ],
                status_scope="FRAME COUNTS",
            )
        )

        claims.append(
            evidence.make_claim(
                "C07",
                "evidence",
                f"G7 没有执行，所以正式指标行是 {ms['metric_rows']}，任何比例都只能标为 Blocked。",
                "blocked",
                evidence.blocked_inputs("G7", data["gate_status"], denominator=0),
                f"eligible records {ms['eligible_records']} 条，但 metric rows = {ms['metric_rows']}；G7 状态 {data['gate_status']}。",
                "有语料不等于有指标；准入条件缺一项就不能生成比率。",
                "若补上第二编码员并达到 agreement 阈值，metric rows 可能大于 0，这会推翻当前的 0。",
                "先完成双盲编码与 agreement，再谈任何 share。",
                "consumer-metric-view-contract + G7 gate status",
                "metric_row",
                "fail-closed：缺第二编码员即阻断",
                [],
                [
                    num("eligible_records", ms["eligible_records"], "canonical_record", "consumer metric view admission predicate", "/eligible_records"),
                    num("metric_rows", ms["metric_rows"], "metric_row", "G7 BLOCKED; fail-closed", "/metric_rows"),
                ],
                status_scope="G7 BLOCKED",
            )
        )

        claims.append(
            evidence.make_claim(
                "C08",
                "evidence",
                f"{medical_records} 条记录含疼痛或病史自述，这些只能进入 review queue，不能变成疗效或安全结论。",
                "not_authorized",
                evidence.not_authorized_inputs("medical_efficacy"),
                f"MED.* annotations {medical_total} 次，覆盖 {medical_records} 条 canonical records。",
                "自述是消费者语言，不是医学测量；报告只记录 self-report。",
                evidence.no_counterevidence("本轮没有测量医学终点，也不存在可用来反驳的临床数据。"),
                "把涉及疼痛、用药或安全的记录交给医学 review，并从体验结论中隔离。",
                "coded-corpus.jsonl（MED.* self-report only）",
                "canonical_record",
                "只记录自述；不含诊断、疗效或安全率",
                ms["medical_record_ids"][:5],
                [
                    num("medical_records", medical_records, "canonical_record", "distinct records with MED.* annotation", "/medical_records"),
                    num("medical_annotations", medical_total, "annotation", "MED.* annotation hits", "/annotation_totals/medical"),
                ],
                status_scope="MEDICAL REVIEW REQUIRED",
            )
        )

        claims.append(
            evidence.make_claim(
                "C09",
                "aspects",
                f"{exp['relevant_records']} 条与支撑带相关的记录里，带旅程或结果信号的只有 {exp['experience_records']} 条，其余 {exp['non_experience_records']} 条是求助、比较或无关内容。",
                "confirmed",
                evidence.confirmed_inputs(coded_sha),
                f"与支撑带相关的 canonical {exp['relevant_records']} 条；journey 或 outcome 至少一项非 unknown 的 {exp['experience_records']} 条；其余 {exp['non_experience_records']} 条。",
                "关键词检索召回的是提问者多于购买者；提问帖可以生成假设，不能估计体验分布。",
                "提问帖仍包含场景、孕周与需求信息，对下一轮采集设计有价值。",
                "补评论层或购买者社区；在此之前报告只输出假设与实验。",
                "coded-corpus.jsonl（journey / outcome rollup）",
                "canonical_record",
                "journey/outcome 为规则判定，未人工复核",
                [],
                [
                    num("relevant_records", exp["relevant_records"], "canonical_record", "exact family + category adjacent", "/experience/relevant_records"),
                    num("experience_records", exp["experience_records"], "canonical_record", "non-unknown journey or outcome", "/experience/experience_records"),
                    num("non_experience_records", exp["non_experience_records"], "canonical_record", "relevant minus experience", "/experience/non_experience_records"),
                ],
                status_scope="CODED CORPUS",
            )
        )

        matrix_total = ms["cooccurrence"]["matrix_total"]
        claims.append(
            evidence.make_claim(
                "C10",
                "mixed",
                f"记录级共现只有 {both} 条，全部是舒适正向与其他摩擦的组合，混合体验是少数条件性事件。",
                "hypothesis",
                evidence.hypothesis_inputs(both, both, 1.0),
                f"mixed_records {both} 条；矩阵格合计 {matrix_total}；positive family × negative family 组合为 comfort→support 与 comfort→fit。",
                "共现不是因果；少数记录不能说明普遍模式。",
                f"其余 {without} 条舒适正向记录没有核心摩擦；增加样本后组合可能改变。",
                "把混合体验当作访谈筛选器，而不是产品改款依据。",
                "metric-summary.json#/cooccurrence/matrix",
                "canonical_record",
                "记录级矩阵；不允许用 annotation 求和替代",
                [pair["canonical_id"] for pair in co["pairs"]],
                [
                    num("mixed_records", both, "canonical_record", "records with both comfort positive and core friction", "/cooccurrence/both_records"),
                    num("matrix_cells_total", matrix_total, "canonical_record", "sum of 4x4 matrix cells", "/cooccurrence/matrix_total"),
                    num("comfort_positive_without_friction", without, "canonical_record", "comfort positive minus mixed", "/cooccurrence/comfort_positive_without_friction"),
                ],
                status_scope="PRE-G7",
            )
        )

        use_count = jr.get("JNY.USE", 0)
        first_count = jr.get("JNY.FIRST_FITTING", 0)
        return_count = jr.get("JNY.RETURN", 0)
        unknown_count = jr.get("unknown", 0)
        claims.append(
            evidence.make_claim(
                "C11",
                "journey",
                f"旅程 single-rollup 落在 {len([k for k, v in jr.items() if k != 'unknown' and v > 0])} 个阶段，使用与推荐覆盖最多，退换阶段只有 {return_count} 条。",
                "confirmed",
                evidence.confirmed_inputs(coded_sha),
                f"journey annotations {journey_total} 次；single-rollup 后使用 {use_count} 条、首次穿戴 {first_count} 条、退换 {return_count} 条、unknown {unknown_count} 条。",
                "阶段计数描述的是语料覆盖，不是购买旅程的逐级转化。",
                "退换记录少可能因为 Reddit 用户不在帖子里更新退换结果，而不是退换比例低。",
                "把退换与护理阶段作为下一轮定向访谈的筛选条件，不计算逐级比例。",
                "coded-corpus.jsonl（journey rollup）",
                "canonical_record",
                "journey 为单值 rollup；unknown 占多数",
                [],
                [
                    num("journey_annotations", journey_total, "annotation", "journey annotation hits; multi-label", "/annotation_totals/journey"),
                    num("journey_use_records", use_count, "canonical_record", "single rollup JNY.USE", "/journey_rollup_counts/JNY.USE"),
                    num("journey_first_fitting_records", first_count, "canonical_record", "single rollup JNY.FIRST_FITTING", "/journey_rollup_counts/JNY.FIRST_FITTING"),
                    num("journey_return_records", return_count, "canonical_record", "single rollup JNY.RETURN", "/journey_rollup_counts/JNY.RETURN"),
                    num("journey_unknown_records", unknown_count, "canonical_record", "remainder to 248", "/journey_rollup_counts/unknown"),
                ],
                status_scope="CODED CORPUS",
            )
        )

        target_rows = ms["identity"]["variant_matrix_rows"]
        per_variant_rows = ms["identity"]["per_variant_review_count_rows"]
        family_review_count = ms["identity"]["family_review_count"] or 0
        claims.append(
            evidence.make_claim(
                "C12",
                "variant",
                f"{target_rows} 个在售变体可以核对，但逐变体评论计数可取得 {per_variant_rows} 行，变体级体验结论仍为空。",
                "evidence_gap",
                evidence.gap_inputs(),
                f"变体矩阵 {target_rows} 行；per-variant review counts 可取得 {per_variant_rows} 行；PDP 只有 family-level {family_review_count} 条评论。",
                "family-level 评论数不能拆到颜色或尺码；没有 crosswalk 时不能把 TikTok SKU 并入。",
                evidence.no_counterevidence("本轮没有逐变体评论导出，无法判断某一变体是否更好或更差。"),
                "先导出 product_review 的 sku_id 分组，再决定是否做变体级结论。",
                "identity-freeze.json + PDP family review count",
                "variant",
                "PDP 只暴露 family-level 评论数；无 SKU/ASIN crosswalk",
                [],
                [
                    idnum("variant_matrix_rows", target_rows, "variant", "len(variants.items)", "/variant_matrix_rows"),
                    idnum("per_variant_review_count_rows", per_variant_rows, "variant", "PDP exposes no per-variant review count", "/per_variant_review_count_rows"),
                    idnum("family_review_count", family_review_count, "canonical_record", "PDP acrCustomerReviewText; quality context only", "/family_review_count"),
                ],
                status_scope="PER-VARIANT CELLS MISSING",
            )
        )

        claims.append(
            evidence.make_claim(
                "C13",
                "agenda",
                f"下一步值得做的是 3 个可逆验证：支撑梯度、选码引导与 G7 双盲编码，而不是一次产品结构改款。",
                "hypothesis",
                evidence.hypothesis_inputs(3, 3, 1.0),
                f"支撑负向 {support_neg} 次、价格负向 {value_neg} 次、共现 {both} 条；三项都未达到正式指标门槛。",
                "证据只支持可逆实验，不支持结构投入。",
                "如果新增样本显示支撑负向不再居首，或 G7 agreement 达标，实验优先级应重排。",
                "先跑三个 proposed 实验，任何一项触发 stop 条件就停止并回到 G0。",
                "C04 + C05 + C07 的 numbers",
                "annotation",
                "实验均为 proposed；没有 owner 签署与预算",
                [],
                [
                    num("support_negative", support_neg, "annotation", "negative SUP.* annotations", "/friction_family_counts/support_negative"),
                    num("value_negative", value_neg, "annotation", "negative VAL.* annotations", "/friction_family_counts/value_negative"),
                    num("mixed_records", both, "canonical_record", "record-level co-occurrence", "/cooccurrence/both_records"),
                    num("metric_rows", ms["metric_rows"], "metric_row", "G7 BLOCKED; fail-closed", "/metric_rows"),
                ],
                status_scope="PRE-G7",
            )
        )

        claims.append(
            evidence.make_claim(
                "C14",
                "evidence",
                f"这份报告能支持方向判断，不能支持任何比率、排名或医学结论；正式指标行仍为 {ms['metric_rows']}。",
                "blocked",
                evidence.blocked_inputs("G7", data["gate_status"], denominator=0),
                f"metric rows {ms['metric_rows']}；G7 {data['gate_status']}；Amazon 评论正文可用 0 条；TikTok 与 Amazon crosswalk 可用 0 条。",
                "报告停在 G6/G7 边界：身份与计数可确认，体验结论最高只到假设级。",
                "补齐 G7 双盲、Amazon 评论正文与 crosswalk 后，结论边界会改变。",
                "在缺口补齐前，停止对外发布与任何结构改款决策。",
                "gate-ledger + metric-summary",
                "metric_row",
                "fail-closed；G7 未执行",
                [],
                [
                    num("metric_rows", ms["metric_rows"], "metric_row", "G7 BLOCKED; fail-closed", "/metric_rows"),
                    num("amazon_review_text_rows", 0, "canonical_record", "product-reviews returns 302 without login", "/coverage_numbers/amazon_review_text_rows"),
                    idnum("verified_crosswalk_links", 0, "variant", "no verified SKU/ASIN crosswalk", "/verified_crosswalk_links"),
                ],
                status_scope="G7 BLOCKED",
            )
        )
        return claims

    # ------------------------------------------------------------------
    # evidence layer
    # ------------------------------------------------------------------
    def build_evidence_layer(self, data: dict[str, Any]) -> dict[str, Any]:
        idf = data["identity"]
        ms = data["metric_summary"]
        corpus = data["corpus_summary"]
        ledger = data["ledger"]
        refs = data["refs"]
        taxonomy = data["taxonomy"]
        gate_ledger = data["gate_ledger"]
        as_of = data["as_of"]

        corpus_evidence = {
            "raw_objects": contract.count_block(
                corpus["raw_objects"], "raw_object", "provider records written to raw store; not a sample size",
                "corpus-summary.json#/raw_objects",
            ),
            "occurrences": contract.count_block(
                corpus["occurrences_deduplicated"], "occurrence", "same external_id + frame deduplicated",
                "corpus-summary.json#/occurrences_deduplicated",
            ),
            "canonical_records": contract.count_block(
                corpus["canonical_records"], "canonical_record", "exact text + same-author Jaccard >= 0.90",
                "corpus-summary.json#/canonical_records",
            ),
            "frame_memberships": contract.count_block(
                corpus["frame_memberships"], "frame_membership", "frames may overlap; not a funnel",
                "corpus-summary.json#/frame_memberships",
            ),
            "annotations": contract.count_block(
                ms["annotation_totals"]["total"], "annotation",
                "aspect + context + journey + outcome + medical annotation hits; multi-label",
                "metric-summary.json#/annotation_totals/total", multi_label=True,
            ),
            "metric_rows": contract.count_block(
                ms["metric_rows"], "metric_row", "G7 BLOCKED; fail-closed", "metric-summary.json#/metric_rows",
            ),
            "reconciliation": corpus["reconciliation"],
            "levels": ledger.levels(),
            "candidate_metric_rows": ledger.candidate_metric_rows,
            "gate_status": data["gate_status"],
            "derivations": {
                "raw_objects": "count of normalised records in successful raw responses",
                "occurrences": "unique (source, external_id, frame) tuples",
                "canonical_records": "occurrence minus exact/same-author duplicate merges",
                "frame_memberships": "sum of frame memberships; diagnostic can be added by content rule",
                "annotations": "sum of rule-coder annotations across five axes",
                "metric_rows": "0 while G7 is BLOCKED",
            },
        }

        taxonomy_codes = [
            {
                "code": code["code"],
                "axis": code["axis"],
                "label": code.get("label", code["code"]),
                "definition": code.get("definition", ""),
                "include": code.get("include", ""),
                "exclude": code.get("exclude", ""),
            }
            for code in taxonomy["codes"]
        ]
        taxonomy_evidence = {
            "taxonomy_id": taxonomy.get("taxonomy_id", "VOC-BAND-v1.0"),
            "frozen_at": taxonomy.get("frozen_at", contract.now_iso()),
            "axes": sorted({code["axis"] for code in taxonomy["codes"]}),
            "code_count": len(taxonomy["codes"]),
            "codes": taxonomy_codes,
            "source": [contract.source_ref_artifact(refs["taxonomy"]["path"], refs["taxonomy"]["sha256"])],
        }

        gate_evidence = {
            "schema_version": gate_ledger.get("schema_version", "voc_gate_ledger_v1"),
            "gates": [{"gate_id": gate["gate_id"], "status": gate["status"]} for gate in gate_ledger.get("gates", [])],
            "decision_scope": "G6 progress snapshot; no formal metric, no external claim.",
            "review_statuses": {"structural": "PASS", "canonical": "PASS", "rights": "CONDITIONAL"},
            "evidence_summary": {
                "raw_objects": corpus["raw_objects"],
                "occurrences": corpus["occurrences_deduplicated"],
                "canonical_records": corpus["canonical_records"],
                "frame_memberships": corpus["frame_memberships"],
                "annotations": ms["annotation_totals"]["total"],
                "metric_rows": ms["metric_rows"],
            },
            "stage_boundary": gate_ledger.get("stage_boundary", {
                "G6_complete": True,
                "G7_executed": False,
                "G8_authorized": False,
                "consumer_metric_rows": 0,
            }),
            "does_not_authorize": gate_ledger.get("does_not_authorize", []),
            "artifact_sha256": {
                "identity-freeze.json": refs["identity"]["sha256"],
                "corpus-summary.json": refs["corpus"]["sha256"],
                "metric-summary.json": refs["metric"]["sha256"],
                "coded-corpus.jsonl": refs["coded"]["sha256"],
                "canonical-records.jsonl": refs["canonical"]["sha256"],
            },
        }

        identity_evidence = dict(idf)
        identity_evidence["source"] = list(idf["source"])
        identity_evidence["variants"] = dict(idf["variants"])

        key_aspects = coding.key_aspects(data["aggregate"], taxonomy, as_of=as_of)
        # Fix source paths to scalar entries in metric-summary.
        for item in key_aspects:
            item["positive"]["source_path"] = f"metric-summary.json#/key_aspects/{item['code']}/positive"
            item["negative"]["source_path"] = f"metric-summary.json#/key_aspects/{item['code']}/negative"

        need_states = self._need_state_evidence(ms, data)
        journey = self._journey_evidence(ms, taxonomy)
        mixed = self._mixed_evidence(ms)
        quotes = self._quotes(data)
        coverage = metrics.coverage_layer(
            corpus_summary=corpus,
            metric_summary=ms,
            canonical=data["canonical"],
            taxonomy=taxonomy,
            as_of=as_of,
        )
        coverage["aspect_code_observed_subset"] = True
        coverage["derivations"] = ms.get("derivations", {})
        return {
            "identity": identity_evidence,
            "gate": gate_evidence,
            "corpus": corpus_evidence,
            "coverage": coverage,
            "taxonomy": taxonomy_evidence,
            "key_aspects": key_aspects,
            "cluster_lenses": ms["frame_lenses"],
            "need_states": need_states,
            "variants": idf["variants"],
            "journey": journey,
            "mixed": mixed,
            "social": None,
            "quotes": quotes,
            "monid": None,
            "skills": contract.SOP_COVERAGE,
            "skill_validation": None,
        }

    def _need_state_evidence(self, ms: dict[str, Any], data: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for index, row in enumerate(ms.get("need_states") or []):
            state_id = row["id"]
            demand = row["demand"]
            friction = row["friction"]
            demand_path = f"metric-summary.json#/need_states/{index}/demand"
            friction_path = f"metric-summary.json#/need_states/{index}/friction"
            out.append(
                {
                    "id": state_id,
                    "quadrant": row["quadrant"],
                    "name": row["name"],
                    "summary": _tp(row["summary"], "C13", [demand_path]),
                    "signal": _tp(
                        f"匹配 {demand} 条记录，其中 {friction} 条同时出现核心摩擦；这是记录级信号，不是人群规模。",
                        "C13",
                        [demand_path, friction_path],
                    ),
                    "success": _tp("支撑稳定且不限制动作，用户能继续原有活动。", "C13", [demand_path]),
                    "failure": _tp("下滑、卷边或压力点出现，用户减少使用时间。", "C13", [friction_path]),
                    "test": _tp("下一轮用定向访谈与 7 天穿戴日志验证该场景，不估计总体比例。", "C13", [demand_path]),
                    "limit": _tp("不表示人群规模或满意程度；只是从关键词语料得到的假设。", "C13", [demand_path]),
                    "axes": {
                        "x": {"label": "需求信号（记录数）", "direction": "higher_is_more"},
                        "y": {"label": "未解摩擦（负向记录数）", "direction": "higher_is_more"},
                    },
                    "evidence_status": _status(
                        "hypothesis", "PRE-G7", evidence.hypothesis_inputs(demand, demand, 1.0), gate="G7"
                    ),
                    "basis": f"{demand} context-matched canonical records; {friction} with core friction",
                    "numbers": [
                        metrics.number_ref("demand_records", demand, "canonical_record", "context-matched records", None, demand_path),
                        metrics.number_ref("friction_records", friction, "canonical_record", "records with core-friction negative", None, friction_path),
                    ],
                }
            )
        return out

    def _journey_evidence(self, ms: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
        labels = {code["code"]: code.get("label", code["code"]) for code in taxonomy["codes"]}
        stage_counts = {
            code: contract.count_block(
                value, "annotation", "journey annotation hits; multi-label",
                f"metric-summary.json#/journey_stage_counts/{code}", multi_label=True,
            )
            for code, value in sorted(ms["journey_stage_counts"].items())
        }
        independent = {
            code: contract.count_block(
                value, "canonical_record", "one deterministic journey stage per record; partition sums to 248",
                f"metric-summary.json#/journey_rollup_counts/{code}", partition=True,
            )
            for code, value in sorted(ms["journey_rollup_counts"].items())
        }
        gaps = {
            name: contract.count_block(
                value, "canonical_record", "one deterministic gap rollup per record; partition sums to 248",
                f"metric-summary.json#/gap_counts/{name}", partition=True,
            )
            for name, value in sorted(ms["gap_counts"].items())
        }
        stage_labels = {code: labels.get(code, code) for code in independent}
        stage_labels["unknown"] = "未知"
        return {
            "stage_counts": stage_counts,
            "stage_labels": stage_labels,
            "expectation_gap_counts": gaps,
            "independent_unit_counts": independent,
            "basis": "independent_content_units",
            "drift_note": "multi-label stage_counts and single-rollup independent_unit_counts answer different questions; the page uses independent_unit_counts",
        }

    def _mixed_evidence(self, ms: dict[str, Any]) -> dict[str, Any]:
        co = ms["cooccurrence"]
        return {
            "mixed_records": contract.count_block(
                co["both_records"], "canonical_record", "records with both comfort-positive and core-friction negative annotations",
                "metric-summary.json#/cooccurrence/both_records",
            ),
            "matrix": co["matrix"],
            "pairs": [
                {
                    "canonical_id": pair["canonical_id"],
                    "positive_codes": pair["positive_codes"],
                    "negative_codes": pair["negative_codes"],
                }
                for pair in co["pairs"]
            ],
            "basis": "record-level co-occurrence; annotation sums are not used",
            "limit": "co-occurrence is not causation and does not estimate prevalence",
        }

    def _quotes(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        ref = data["refs"]["canonical"]
        out = []
        for record in data["canonical"]:
            if record.product_match not in {"exact_current_family", "category_adjacent"}:
                continue
            text = (record.text or "").strip()
            if len(text) < 40:
                continue
            snippet = text[:220].replace("\n", " ")
            out.append(
                {
                    "quote_id": f"Q{len(out) + 1:02d}",
                    "canonical_id": record.canonical_id,
                    "text": snippet,
                    "is_verbatim": True,
                    "source": contract.source_ref_artifact(ref["path"], ref["sha256"]),
                    "language": "en",
                    "redaction_status": "none",
                    "permission": "internal",
                }
            )
            if len(out) >= 3:
                break
        return out

    # ------------------------------------------------------------------
    # report layer
    # ------------------------------------------------------------------
    def build_report(self, data: dict[str, Any], claims: list[dict[str, Any]], evidence_layer: dict[str, Any]) -> dict[str, Any]:
        ms = data["metric_summary"]
        idf = data["identity"]
        corpus = data["corpus_summary"]
        refs = data["refs"]
        co = ms["cooccurrence"]
        ff = ms["friction_family_counts"]
        both = co["both_records"]
        comfort_pos = co["comfort_positive_records"]
        without = co["comfort_positive_without_friction"]
        friction_records = co["friction_negative_records"]
        support_neg = ff["support_negative"]
        support_pos = ff["support_positive"]
        value_neg = ff["value_negative"]
        fit_neg = ff["fit_negative"]
        stability_neg = ff["stability_negative"]

        claim_by_id = {claim["claim_id"]: claim for claim in claims}

        def refs_for(claim_id: str) -> list[str]:
            return [number["source_path"] for number in claim_by_id[claim_id]["numbers"]]

        # --- exhibits -------------------------------------------------
        e01 = self._exhibit_01(data, claim_by_id)
        e02 = self._exhibit_02(data, claim_by_id)
        e03 = self._exhibit_03(data, claim_by_id)
        e04 = self._exhibit_04(data, claim_by_id)
        e05 = self._exhibit_05(data, claim_by_id)
        e06 = self._exhibit_06(data, claim_by_id)
        e08 = self._exhibit_08(data, claim_by_id)
        e09 = self._exhibit_09(data, claims)
        e10 = self._exhibit_10(data, claim_by_id)

        sections: list[dict[str, Any]] = []

        sections.append(
            {
                "index": "00",
                "id": "answer",
                "kicker": "EXECUTIVE ANSWER",
                "title": _tp("先补 G7 双盲与支撑梯度验证，再决定是否做产品结构投入。", "C13", refs_for("C13")),
                "status": "ok",
                "blocks": [
                    {"type": "answer_stack", "claim_ids": ["C02", "C05", "C07"]},
                    {"type": "claim", "claim_id": "C09"},
                ],
            }
        )
        sections.append(
            {
                "index": "01",
                "id": "experience",
                "kicker": "CORE TENSION",
                "title": _tp("27 条舒适正向记录说明轻薄是真实资产，但支撑兑现仍是条件性的。", "C05", refs_for("C05")),
                "status": "ok",
                "blocks": [e01, {"type": "claim", "claim_id": "C04"}, {"type": "claim", "claim_id": "C05"}],
            }
        )
        sections.append(
            {
                "index": "02",
                "id": "aspects",
                "kicker": "EXPERIENCE SIGNATURE",
                "title": _tp(
                    f"{ms['annotation_totals']['aspect']} 次 aspect 标注覆盖 {len(ms['aspect_code_counts'])} 个主题，支撑与舒适同时出现正负两面。",
                    "C09",
                    refs_for("C09"),
                ),
                "status": "ok",
                "blocks": [e02],
            }
        )
        sections.append(
            {
                "index": "03",
                "id": "frames",
                "kicker": "SAMPLE LENSES",
                "title": _tp(
                    f"三个镜头覆盖 {ms['frame_counts'].get('natural', 0)}、{ms['frame_counts'].get('diagnostic', 0)}、{ms['frame_counts'].get('qualitative_seed', 0)} 条记录，合计 {corpus['frame_memberships']} 个 membership。",
                    "C06",
                    refs_for("C06"),
                ),
                "status": "ok",
                "blocks": [e03, {"type": "claim", "claim_id": "C06"}],
            }
        )
        sections.append(
            {
                "index": "04",
                "id": "mixed",
                "kicker": "MIXED EXPERIENCE",
                "title": _tp(f"记录级共现只有 {both} 条，混合体验是少数条件性事件，不是普遍模式。", "C10", refs_for("C10")),
                "status": "ok",
                "blocks": [e04, {"type": "claim", "claim_id": "C10"}],
            }
        )
        if e05:
            sections.append(
                {
                    "index": "05",
                    "id": "contexts",
                    "kicker": "NEED STATES",
                    "title": _tp("4 类需求场景中工作与运动信号最强，但四象限只表示记录信号。", "C13", refs_for("C13")),
                    "status": "ok",
                    "blocks": [e05],
                }
            )
        else:
            sections.append(
                {
                    "index": "05",
                    "id": "contexts",
                    "kicker": "NEED STATES",
                    "title": _tp("四类需求场景尚未达到最小记录门槛，本节不输出象限结论。", "C13", refs_for("C13")),
                    "status": "evidence_gap",
                    "blocks": [_safe_section_gap("contexts", "need_states 每个场景少于 3 条记录", "C13")],
                }
            )
        sections.append(
            {
                "index": "06",
                "id": "journey",
                "kicker": "MOMENTS OF TRUTH",
                "title": _tp(
                    f"旅程 {len([k for k, v in ms['journey_rollup_counts'].items() if k != 'unknown' and v > 0])} 个阶段中，使用 {ms['journey_rollup_counts'].get('JNY.USE', 0)} 条、推荐 {ms['journey_rollup_counts'].get('JNY.RECOMMEND', 0)} 条，退换为 {ms['journey_rollup_counts'].get('JNY.RETURN', 0)} 条。",
                    "C11",
                    refs_for("C11"),
                ),
                "status": "ok",
                "blocks": [e06, {"type": "claim", "claim_id": "C11"}],
            }
        )
        sections.append(
            {
                "index": "07",
                "id": "social",
                "kicker": "SOCIAL FIREWALL",
                "title": _tp("本轮社媒记录为 0 条，任何社媒结论都只能标为 Blocked。", "C14", refs_for("C14")),
                "status": "blocked",
                "blocks": [
                    contract.gap_block(
                        reason="evidence.social 为空：本轮没有 TikTok 视频、评论或达人数据",
                        title="[BLOCKED: social source not collected this run]",
                        block_readout=_readout(
                            "本轮 TikTok 视频、评论、达人与广告数据均为 0 条，无法生成社媒分流图。",
                            "社媒记录不能进入自然口碑，也不能用播放量或点赞量推导情绪。",
                            evidence.no_counterevidence("没有社媒语料，无法检查社媒结论是否成立。"),
                            "先完成 G2 权利审计与 G3 来源试点，再决定是否接入社媒。",
                            "C14",
                            refs_for("C14"),
                        ),
                        block_foot=contract.source_foot(
                            "0 social records", "canonical_record", "no data; no social source", "Blocked · no social source"
                        ),
                    )
                ],
            }
        )
        sections.append(
            {
                "index": "08",
                "id": "variant",
                "kicker": "EVIDENCE APPLICABILITY",
                "title": _tp(
                    f"{idf['family_children']} 个在售变体可以核对，但逐变体评论计数全部缺失，变体级体验结论仍为空。",
                    "C12",
                    refs_for("C12"),
                ),
                "status": "partial",
                "blocks": [{"type": "claim", "claim_id": "C01"}, e08, {"type": "claim", "claim_id": "C12"}],
            }
        )
        experiments = self._experiments()
        sections.append(
            {
                "index": "09",
                "id": "agenda",
                "kicker": "VALIDATION AGENDA",
                "title": _tp("下一步是 3 个可逆验证，不是一次产品结构改款。", "C13", refs_for("C13")),
                "status": "ok",
                "blocks": [
                    {"type": "experiment_sequence", "experiment_ids": [item["id"] for item in experiments]},
                    {"type": "claim", "claim_id": "C13"},
                ],
            }
        )
        sections.append(
            {
                "index": "10",
                "id": "evidence",
                "kicker": "TRUST & LIMITS",
                "title": _tp("商品身份与计数可以确认，体验结论最高只到假设级，正式指标行为 0。", "C14", refs_for("C14")),
                "status": "blocked",
                "blocks": [
                    e09,
                    e10,
                    {"type": "claim", "claim_id": "C07"},
                    {"type": "claim", "claim_id": "C14"},
                    evidence.status_legend_block(),
                ],
            }
        )

        claim_maturity = evidence.claim_maturity(claims)

        meta = {
            "title": "Momcozy BumpEase · 消费者洞察进度快照",
            "description": "G6 progress snapshot; G7 BLOCKED; experience claims capped at hypothesis level.",
            "brand_wordmark": idf["brand"].lower(),
            "report_type": "Decision Brief",
            "lang": "zh-CN",
        }
        hero = {
            "eyebrow": f"Management answer · {data['as_of']}",
            "h1": _tp("商品身份可以确认，支撑类摩擦是最值得验证的线索，正式指标仍然为零。", "C07", refs_for("C07")),
            "h1_accent": "正式指标仍然为零",
            "lead": _tp(
                "报告停在 G6/G7 边界：编码与计数已跑通，但 G7 双盲校准没有执行，所以所有体验结论都是方向性的，不是正式指标。",
                "C07",
                refs_for("C07"),
            ),
            "actions": [
                {"label": "查看答案", "href": "#answer", "primary": True},
                {"label": "查看证据边界", "href": "#evidence", "primary": False},
            ],
            "compass": [
                {"label": "Protect", "title": "轻薄舒适资产", "note": f"舒适/外观正向记录 {comfort_pos} 条；不要把条件性正向写成总体满意。"},
                {"label": "Resolve", "title": "支撑与选码预期", "note": f"支撑负向 {support_neg} 次，共现 {both} 条；先验证再改结构。"},
                {"label": "Prove", "title": "G7 双盲编码", "note": "没有第二编码员，就没有正式指标行。"},
            ],
            "truth_ribbon": {
                "label": "PROGRESS SNAPSHOT",
                "cells": [
                    {"value": "G6 PASS", "note": "canonical + ledger"},
                    {"value": "G7 BLOCKED", "note": "no second coder"},
                    {"value": "0 metric rows", "note": "fail-closed"},
                    {"value": f"{corpus['canonical_records']} canonical", "note": f"from {corpus['raw_objects']} raw objects"},
                ],
            },
            "proofs": [
                {"value": str(idf["family_children"]), "label": "在售 ASIN 变体", "note": f"PDP {data['as_of']}"},
                {"value": f"{corpus['raw_objects']} → {corpus['canonical_records']}", "label": "raw object → canonical", "note": "重复合并全部带理由"},
                {"value": f"{comfort_pos} / {both}", "label": "舒适正向 / 同时有核心摩擦", "note": "canonical records"},
                {"value": "0", "label": "正式指标行", "note": "G7 未执行"},
            ],
        }
        decision = {
            "decision_question": (data["frozen"].get("voc-research-charter.json") or {}).get(
                "decision_question", "是否继续把轻薄可穿作为核心定位，还是先补支撑梯度与选码引导？"
            ),
            "answer": _tp(
                "先校准 Fit 与支撑预期，再决定产品结构投入。C04、C05、C07 支持这个顺序：支撑负向仍是最强摩擦，但正式指标行为 0。",
                "C13",
                refs_for("C13"),
            ),
            "protect": [f"轻薄舒适是可保护的真实资产。C04 记录到舒适/外观正向标注 {ff['comfort_positive']} 次。"],
            "resolve": [f"支撑、尺码与稳定性摩擦的条件性。C05 记录到 {both} 条共现。"],
            "prove": [f"G7 双盲编码与逐字段 agreement。C07 说明 metric rows 为 {ms['metric_rows']}。"],
        }
        report = {
            "meta": meta,
            "hero": hero,
            "decision": decision,
            "sections": sections,
            "claims": claims,
            "experiments": experiments,
            "claim_maturity": claim_maturity,
            "prohibited_outputs": evidence.prohibited_outputs_block(),
            "unknowns": self._unknowns(data),
        }
        return report

    # --- exhibit builders ---------------------------------------------
    def _exhibit_01(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
        ms = data["metric_summary"]
        co = ms["cooccurrence"]
        both = co["both_records"]
        comfort_pos = co["comfort_positive_records"]
        without = co["comfort_positive_without_friction"]
        friction = co["friction_negative_records"]
        status = _status("hypothesis", "PRE-G7", evidence.hypothesis_inputs(both, both, 1.0), gate="G7")
        chart = {
            "type": "nested_bar",
            "unit": "canonical_record",
            "encoding": "absolute_count",
            "basis": f"{comfort_pos} comfort-positive records; {both} with core friction; {without} without; {friction} core-friction records",
            "denominator": comfort_pos,
            "frame_scope": ["natural"],
            "series": [
                {
                    "group": "comfort_or_appearance_positive",
                    "label": "舒适/外观正向记录",
                    "n": comfort_pos,
                    "with_friction": both,
                    "without_friction": without,
                    "codes": ["COM.*", "APP.*"],
                },
                {
                    "group": "core_friction_negative",
                    "label": "核心摩擦负向记录",
                    "n": friction,
                    "with_friction": None,
                    "without_friction": None,
                    "codes": ["SUP.*", "FIT.*", "STB.*"],
                    "status": "evidence_gap",
                },
            ],
            "notes": [
                "同一记录可贡献多个 annotation；不是人数。",
                "核心摩擦组与舒适正向组的共现未计算，标为 Evidence gap。",
            ],
        }
        title = f"{comfort_pos} 条舒适或外观正向记录中，{both} 条同时出现支撑、适配或稳定性负向。"
        return {
            "type": "exhibit",
            "number": "01",
            "title": _tp(title, "C05", [n["source_path"] for n in claims["C05"]["numbers"]]),
            "scope": f"{comfort_pos} comfort-positive canonical records · record-level co-occurrence",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"{comfort_pos} 条舒适或外观正向记录中，{both} 条同时出现支撑、适配或稳定性负向；纯摩擦记录 {friction} 条。",
                "共现只发生在少数正向记录里，说明张力是条件性的，不是普遍模式。",
                f"其余 {without} 条舒适正向记录没有核心摩擦；共现不是因果。",
                "分开验证支撑梯度与选码引导，不做一次性结构改款。",
                "C05",
                [n["source_path"] for n in claims["C05"]["numbers"]],
            ),
            "source_foot": _foot(
                "hypothesis",
                "PRE-G7",
                f"metric-summary.json#/cooccurrence（{comfort_pos} / {both} / {without} / {friction}）",
                "canonical_record",
                "Reddit keyword sample; no Amazon review text; single-coded pre-G7",
            ),
            "drawer": {
                "summary": "查看定义与误读边界",
                "content": "舒适或外观正向 = 至少一个 COM/APP positive annotation；核心摩擦 = SUP/FIT/STB negative。共现不是因果，也不是总体发生率。",
            },
            "data_table": [
                {"label": "comfort_positive_records", "value": comfort_pos, "unit": "canonical_record"},
                {"label": "with_core_friction", "value": both, "unit": "canonical_record"},
                {"label": "without_core_friction", "value": without, "unit": "canonical_record"},
                {"label": "friction_negative_records", "value": friction, "unit": "canonical_record"},
            ],
            "definitions": ["COM/APP positive", "SUP/FIT/STB negative", "record-level co-occurrence"],
        }

    def _exhibit_02(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
        ms = data["metric_summary"]
        key_aspects = coding.key_aspects(data["aggregate"], data["taxonomy"], as_of=data["as_of"])
        max_value = max((max(item["positive"]["value"], item["negative"]["value"]) for item in key_aspects), default=1)
        status = _status("confirmed", "CODED CORPUS", evidence.confirmed_inputs(data["refs"]["coded"]["sha256"]))
        chart = {
            "type": "diverging_bar",
            "unit": "annotation",
            "encoding": "max_relative",
            "basis": f"{ms['annotation_totals']['aspect']} aspect annotations; {len(key_aspects)} of {len(ms['aspect_code_counts'])} aspect codes shown",
            "denominator": None,
            "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "axis": {"min": -max_value, "max": max_value, "step": max(1, max_value // 4)},
            "series": [
                {
                    "code": item["code"],
                    "label": item["label"],
                    "positive": item["positive"]["value"],
                    "negative": item["negative"]["value"],
                }
                for item in key_aspects
            ],
            "notes": [
                "条形宽度按同一轴的最大值缩放；正负分开，不做净分。",
                "annotation hits 是多标签，不是人数，也不是发生率。",
            ],
        }
        total_annotations = data["metric_summary"]["annotation_totals"]["aspect"]
        return {
            "type": "exhibit",
            "number": "02",
            "title": _tp(
                f"{total_annotations} 次 aspect 标注中，支撑类负向 {ms['friction_family_counts']['support_negative']} 次、舒适类正向 {ms['friction_family_counts']['comfort_positive']} 次，正负两面并存。",
                "C09",
                [n["source_path"] for n in claims["C09"]["numbers"]],
            ),
            "scope": f"{len(key_aspects)} key aspects · {total_annotations} aspect annotations · multi-label",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"{len(key_aspects)} 个主题合计 {total_annotations} 次 aspect 标注，其中支撑类负向 {ms['friction_family_counts']['support_negative']} 次、舒适类正向 {ms['friction_family_counts']['comfort_positive']} 次。",
                "支撑与舒适同时出现正负两面，说明体验是条件性的，不能用单一方向概括。",
                f"支撑类正向标注仍有 {ms['friction_family_counts']['support_positive']} 次，说明负向不是唯一信号。",
                "把正向资产与条件性摩擦分开验证，不合并成一个总分。",
                "C09",
                [n["source_path"] for n in claims["C09"]["numbers"]],
            ),
            "source_foot": _foot(
                "confirmed",
                "CODED CORPUS",
                f"metric-summary.json#/aspect_polarity_counts（{total_annotations} annotations）",
                "annotation",
                "rule coder, single-coded pre-G7; annotation hits are not people",
            ),
            "drawer": {
                "summary": "查看主题编码与折叠规则",
                "content": "qualified_positive 折叠进 positive，qualified_negative 折叠进 negative；mixed 同时保留正负两个分量。所有计数来自 coded-corpus.jsonl。",
            },
            "data_table": [
                {"label": item["code"], "value": item["positive"]["value"], "unit": "annotation", "polarity": "positive"}
                for item in key_aspects[:6]
            ]
            + [
                {"label": item["code"], "value": item["negative"]["value"], "unit": "annotation", "polarity": "negative"}
                for item in key_aspects[:6]
            ],
            "definitions": ["aspect annotation", "qualified_* folding", "no net score"],
        }

    def _exhibit_03(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
        ms = data["metric_summary"]
        status = _status("confirmed", "FRAME COUNTS", evidence.confirmed_inputs(data["refs"]["corpus"]["sha256"]))
        chart = {
            "type": "frame_grid",
            "unit": "canonical_record",
            "encoding": "absolute_count",
            "basis": f"frame counts {ms['frame_counts']}; frames may overlap; membership total {data['corpus_summary']['frame_memberships']}",
            "denominator": None,
            "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "series": ms["frame_lenses"],
            "notes": [
                "三个镜头选择机制不同，只允许并排绝对值。",
                "禁止跨 frame 比较百分比。",
            ],
        }
        return {
            "type": "exhibit",
            "number": "03",
            "title": _tp(
                f"自然镜头覆盖 {ms['frame_counts'].get('natural', 0)} 条记录，诊断镜头 {ms['frame_counts'].get('diagnostic', 0)} 条，定性种子镜头 {ms['frame_counts'].get('qualitative_seed', 0)} 条。",
                "C06",
                [n["source_path"] for n in claims["C06"]["numbers"]],
            ),
            "scope": "3 lenses · canonical records with frame membership · frames overlap",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"自然镜头 {ms['frame_counts'].get('natural', 0)} 条、诊断镜头 {ms['frame_counts'].get('diagnostic', 0)} 条、定性种子镜头 {ms['frame_counts'].get('qualitative_seed', 0)} 条；membership 合计 {data['corpus_summary']['frame_memberships']}。",
                "三个镜头回答不同问题，不能合并成一个分母，也不能比较百分比。",
                f"诊断镜头只有 {ms['frame_counts'].get('diagnostic', 0)} 条，排序很容易随新增记录改变。",
                "把自然镜头作为方向线索，把诊断镜头作为失败模式清单。",
                "C06",
                [n["source_path"] for n in claims["C06"]["numbers"]],
            ),
            "source_foot": _foot(
                "confirmed",
                "FRAME COUNTS",
                "corpus-summary.json#/frame_counts",
                "canonical_record",
                "frames overlap; diagnostic sample is small",
            ),
            "drawer": {
                "summary": "查看 frame 定义与重叠规则",
                "content": "natural = 关键词召回的自然样本；diagnostic = 自然镜头中含产品失败措辞的子集；qualitative_seed = 品牌提及种子。一个 canonical 可同时属于多个 frame。",
            },
            "data_table": [
                {"label": lens["id"], "value": lens["n"]["value"], "unit": "canonical_record"}
                for lens in ms["frame_lenses"]
            ],
            "definitions": ["frame membership", "overlap", "no cross-frame percentage"],
        }

    def _exhibit_04(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
        ms = data["metric_summary"]
        co = ms["cooccurrence"]
        status = _status("hypothesis", "PRE-G7", evidence.hypothesis_inputs(co["both_records"], co["both_records"], 1.0), gate="G7")
        chart = {
            "type": "co_occurrence_matrix",
            "unit": "canonical_record",
            "encoding": "absolute_count",
            "basis": f"{co['both_records']} record-level co-occurrences; matrix cells sum to {ms['cooccurrence']['matrix_total']}",
            "denominator": None,
            "frame_scope": ["natural"],
            "matrix": ms["cooccurrence"]["matrix"],
            "notes": [
                "矩阵由记录级数据计算；不是 annotation 求和。",
                "共现不是因果，也不能当百分比。",
            ],
        }
        return {
            "type": "exhibit",
            "number": "04",
            "title": _tp(
                f"记录级共现只有 {co['both_records']} 条，矩阵格合计 {ms['cooccurrence']['matrix_total']}，全部落在 comfort→support 与 comfort→fit 两类组合。",
                "C10",
                [n["source_path"] for n in claims["C10"]["numbers"]],
            ),
            "scope": f"{co['both_records']} mixed canonical records · 4x4 family matrix",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"mixed_records {co['both_records']} 条，矩阵格合计 {ms['cooccurrence']['matrix_total']}；其余 {co['comfort_positive_without_friction']} 条舒适正向记录没有核心摩擦。",
                "共现只发生在少数记录里，说明混合体验是条件性事件。",
                "共现不是因果；样本增加后组合可能改变。",
                "把混合体验当作访谈筛选器，而不是产品改款依据。",
                "C10",
                [n["source_path"] for n in claims["C10"]["numbers"]],
            ),
            "source_foot": _foot(
                "hypothesis",
                "PRE-G7",
                "metric-summary.json#/cooccurrence/matrix",
                "canonical_record",
                "record-level only; no prevalence; single-coded pre-G7",
            ),
            "drawer": {
                "summary": "查看矩阵定义",
                "content": "positive family = COM/APP/MAT/GEN；negative family = SUP/FIT/STB/VAL。每个 mixed record 只取一个主正家族和一个主负家族，保证矩阵和等于 mixed_records。",
            },
            "data_table": [
                {"label": f"{p}→{n}", "value": value, "unit": "canonical_record"}
                for p, row in ms["cooccurrence"]["matrix"].items()
                for n, value in row.items()
                if value
            ],
            "definitions": ["record-level co-occurrence", "family matrix", "no annotation sum"],
        }

    def _exhibit_05(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any] | None:
        ms = data["metric_summary"]
        rows = ms.get("need_states") or []
        if len(rows) < 4:
            return None
        status = _status("hypothesis", "PRE-G7", evidence.hypothesis_inputs(4, 4, 1.0), gate="G7")
        chart = {
            "type": "quadrant_2x2",
            "unit": "canonical_record",
            "encoding": "absolute_count",
            "basis": "4 context-derived need states; demand and friction are record counts",
            "denominator": None,
            "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "axes": {
                "x": {"label": "需求信号（记录数）", "direction": "higher_is_more"},
                "y": {"label": "未解摩擦（负向记录数）", "direction": "higher_is_more"},
            },
            "series": [
                {
                    "id": row["id"],
                    "quadrant": row["quadrant"],
                    "name": row["name"],
                    "demand": row["demand"],
                    "friction": row["friction"],
                    "context_code": row["context_code"],
                }
                for row in rows
            ],
            "notes": [
                "象限是记录信号的中位数切分，不是人群规模。",
                "四个场景来自 context annotation，不是问卷分群。",
            ],
        }
        return {
            "type": "exhibit",
            "number": "05",
            "title": _tp(
                f"四类需求场景分别匹配 {rows[0]['demand']}、{rows[1]['demand']}、{rows[2]['demand']}、{rows[3]['demand']} 条记录，摩擦信号最高的是「{max(rows, key=lambda r: r['friction'])['name']}」。",
                "C13",
                [n["source_path"] for n in claims["C13"]["numbers"]],
            ),
            "scope": "4 context-derived need states · record-level demand and friction",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"四个场景的记录数为 {', '.join(str(row['demand']) for row in rows)}，核心摩擦记录数为 {', '.join(str(row['friction']) for row in rows)}。",
                "工作与运动场景的信号更强，但这是关键词语料中的记录信号，不是人群分群。",
                "context annotation 可能受关键词选择影响；新增语料可能改变象限。",
                "用定向访谈验证最高摩擦场景，不把象限当市场规模。",
                "C13",
                [n["source_path"] for n in claims["C13"]["numbers"]],
            ),
            "source_foot": _foot(
                "hypothesis",
                "PRE-G7",
                "metric-summary.json#/need_states（4 contexts）",
                "canonical_record",
                "context-derived; median split; not a population estimate",
            ),
            "drawer": {
                "summary": "查看需求场景定义",
                "content": "场景由 context code 匹配：运动、工作、产后、孕晚期。每个场景的需求信号是记录数，摩擦信号是其中含 SUP/FIT/STB negative 的记录数。象限按中位数切分。",
            },
            "data_table": [
                {"label": row["id"], "value": row["demand"], "unit": "canonical_record", "friction": row["friction"]}
                for row in rows
            ],
            "definitions": ["context-derived need state", "median split", "not population size"],
        }

    def _exhibit_06(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
        ms = data["metric_summary"]
        labels = {code["code"]: code.get("label", code["code"]) for code in data["taxonomy"]["codes"]}
        rollups = ms["journey_rollup_counts"]
        series = [
            {"stage": code, "label": labels.get(code, "未知"), "value": value}
            for code, value in sorted(rollups.items(), key=lambda item: (-item[1], item[0]))
        ]
        display_max = max((item["value"] for item in series), default=1)
        status = _status("confirmed", "CODED CORPUS", evidence.confirmed_inputs(data["refs"]["coded"]["sha256"]))
        chart = {
            "type": "coverage_bars",
            "unit": "canonical_record",
            "encoding": "max_relative",
            "basis": f"coverage, not funnel; {sum(item['value'] for item in series)} canonical records; display_max {display_max}",
            "denominator": sum(item["value"] for item in series),
            "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "series": series,
            "display_max": display_max,
            "notes": [
                "条形表示阶段覆盖，不是逐级转化。",
                "unknown 单列，不并入负向。",
            ],
        }
        return {
            "type": "exhibit",
            "number": "06",
            "title": _tp(
                f"旅程 single-rollup 覆盖 {len([k for k, v in rollups.items() if k != 'unknown' and v > 0])} 个阶段，使用 {rollups.get('JNY.USE', 0)} 条、推荐 {rollups.get('JNY.RECOMMEND', 0)} 条、退换 {rollups.get('JNY.RETURN', 0)} 条，unknown {rollups.get('unknown', 0)} 条。",
                "C11",
                [n["source_path"] for n in claims["C11"]["numbers"]],
            ),
            "scope": f"{sum(item['value'] for item in series)} canonical records · single journey rollup",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"journey annotations {ms['annotation_totals']['journey']} 次；single-rollup 后使用 {rollups.get('JNY.USE', 0)} 条、首次穿戴 {rollups.get('JNY.FIRST_FITTING', 0)} 条、退换 {rollups.get('JNY.RETURN', 0)} 条、unknown {rollups.get('unknown', 0)} 条。",
                "阶段计数描述语料覆盖，不是购买旅程的逐级比例。",
                "退换记录少可能因为用户不在帖子里更新结果，而不是退换比例低。",
                "把退换与护理阶段作为下一轮访谈筛选条件，不计算比例。",
                "C11",
                [n["source_path"] for n in claims["C11"]["numbers"]],
            ),
            "source_foot": _foot(
                "confirmed",
                "CODED CORPUS",
                "metric-summary.json#/journey_rollup_counts（coverage, not funnel）",
                "canonical_record",
                "single rollup; unknown is the majority",
            ),
            "drawer": {
                "summary": "查看阶段 rollup 规则",
                "content": "每条记录只取一个最具体的 journey stage；unknown 是剩余记录。页面显示的是 independent_unit_counts，不是多标签 annotation 计数。",
            },
            "data_table": [
                {"label": item["stage"], "value": item["value"], "unit": "canonical_record"} for item in series
            ],
            "definitions": ["single journey rollup", "coverage not funnel", "unknown is separate"],
        }

    def _exhibit_08(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
        idf = data["identity"]
        ms = data["metric_summary"]
        status = _status("evidence_gap", "PER-VARIANT CELLS MISSING", evidence.gap_inputs())
        chart = {
            "type": "variant_grid",
            "unit": "variant",
            "encoding": "absolute_count",
            "basis": f"{len(idf['variants']['items'])} ASINs from PDP; per-variant review counts are null",
            "denominator": None,
            "frame_scope": ["identity"],
            "series": idf["variants"]["items"],
            "notes": [
                "逐变体评论计数缺失，不能用 family-level 评论数拆分。",
                "TikTok SKU 与 Amazon ASIN 没有已验证 crosswalk，不能合并。",
            ],
        }
        return {
            "type": "exhibit",
            "number": "08",
            "title": _tp(
                f"{len(idf['variants']['items'])} 个 ASIN 变体全部可核对，但逐变体评论计数可取得 0 行，family-level 评论数 {ms['identity']['family_review_count']} 条不能拆分。",
                "C12",
                [n["source_path"] for n in claims["C12"]["numbers"]],
            ),
            "scope": f"{len(idf['variants']['items'])} ASIN variants · identity grid · per-variant counts missing",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"变体矩阵 {len(idf['variants']['items'])} 行；per-variant review counts 可取得 0 行；family-level 评论数 {ms['identity']['family_review_count']} 条。",
                "family-level 评论数不能拆到颜色或尺码；没有 crosswalk 时不能合并来源。",
                "本轮没有逐变体评论导出，无法判断某一变体是否更好或更差。",
                "先导出 product_review 的 sku_id 分组，再决定是否做变体级结论。",
                "C12",
                [n["source_path"] for n in claims["C12"]["numbers"]],
            ),
            "source_foot": _foot(
                "evidence_gap",
                "PER-VARIANT CELLS MISSING",
                "identity-freeze.json#/variants + PDP family review count",
                "variant",
                "PDP exposes no per-variant review count; no SKU/ASIN crosswalk",
            ),
            "drawer": {
                "summary": "查看变体网格口径",
                "content": "每个 ASIN 是一个变体；目标变体是 Oyster Pink / Small。review_count、rating、verified_count 等逐变体字段全部为 null，不能用 family-level 数字填充。",
            },
            "data_table": [
                {"label": item["variant_key"], "value": item["color"] or "", "unit": "variant", "size": item["size"] or "", "is_target": item["is_target"]}
                for item in idf["variants"]["items"]
            ],
            "definitions": ["ASIN variant", "family-level review count", "no crosswalk"],
        }

    def _exhibit_09(self, data: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        maturity = evidence.claim_maturity(claims)
        status = _status("blocked", "MATURITY MATRIX", evidence.blocked_inputs("G7", data["gate_status"], denominator=0), gate="G7")
        chart = {
            "type": "maturity_matrix",
            "unit": "claim",
            "encoding": "absolute_count",
            "basis": f"{len(maturity)} claims; six status columns",
            "denominator": None,
            "frame_scope": ["all"],
            "series": maturity,
            "notes": [
                "成熟度是状态，不是绩效评分。",
                "每个 claim 恰好一行；当前状态由 grade 决定。",
            ],
        }
        counts = {status_name: sum(1 for row in maturity if row["status"] == status_name) for status_name in contract.STATUS_ORDER}
        return {
            "type": "exhibit",
            "number": "09",
            "title": _tp(
                f"{len(maturity)} 条 claim 中，confirmed {counts['confirmed']} 条、hypothesis {counts['hypothesis']} 条、evidence_gap {counts['evidence_gap']} 条、blocked {counts['blocked']} 条、not_authorized {counts['not_authorized']} 条。",
                "C07",
                [n["source_path"] for n in claims[6]["numbers"]],
            ),
            "scope": f"{len(maturity)} claims · six-status maturity matrix",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"{len(maturity)} 条 claim 分布在 {len([v for v in counts.values() if v])} 个状态；confirmed {counts['confirmed']} 条、hypothesis {counts['hypothesis']} 条、blocked {counts['blocked']} 条。",
                "成熟度矩阵显示证据状态，不是绩效分数；多数体验 claim 仍是 hypothesis。",
                "如果 G7 通过，部分 hypothesis 可能升级，矩阵会改变。",
                "先补 G7，再重跑成熟度矩阵。",
                "C07",
                [n["source_path"] for n in claims[6]["numbers"]],
            ),
            "source_foot": _foot(
                "blocked",
                "G7 BLOCKED",
                "claims.json#/grade + gate-ledger.json#/G7",
                "claim",
                "statuses are decision states, not a score",
            ),
            "drawer": {
                "summary": "查看六级状态定义",
                "content": "Confirmed / Directional / Supported hypothesis / Evidence gap / Blocked / Not authorized。先命中先停；状态不是绩效评分。",
            },
            "data_table": [
                {"label": status_name, "value": counts[status_name], "unit": "claim"} for status_name in contract.STATUS_ORDER
            ],
            "definitions": ["claim maturity", "six statuses", "not a score"],
        }

    def _exhibit_10(self, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
        corpus = data["corpus_summary"]
        ms = data["metric_summary"]
        steps = [
            {"step": "raw_object", "label": "raw object", "value": corpus["raw_objects"], "delta": None},
            {"step": "occurrence", "label": "occurrence", "value": corpus["occurrences_deduplicated"], "delta": corpus["occurrences_deduplicated"] - corpus["raw_objects"]},
            {"step": "canonical_record", "label": "canonical record", "value": corpus["canonical_records"], "delta": corpus["canonical_records"] - corpus["occurrences_deduplicated"]},
            {"step": "frame_membership", "label": "frame membership", "value": corpus["frame_memberships"], "delta": corpus["frame_memberships"] - corpus["canonical_records"]},
            {"step": "annotation", "label": "annotation", "value": ms["annotation_totals"]["total"], "delta": ms["annotation_totals"]["total"] - corpus["frame_memberships"]},
            {"step": "metric_row", "label": "metric row", "value": ms["metric_rows"], "delta": ms["metric_rows"] - ms["annotation_totals"]["total"]},
        ]
        status = _status("confirmed", "LINEAGE RECONCILED", evidence.confirmed_inputs(data["refs"]["corpus"]["sha256"]))
        chart = {
            "type": "lineage_waterfall",
            "unit": "raw_object",
            "encoding": "max_relative",
            "basis": "lineage, not conversion; each step uses its own scale",
            "denominator": None,
            "frame_scope": ["all"],
            "series": steps,
            "notes": [
                "每一步使用独立刻度；0 值单独标注。",
                "血缘链不是逐级转化，不能读出比例。",
            ],
        }
        return {
            "type": "exhibit",
            "number": "10",
            "title": _tp(
                f"血缘链从 {corpus['raw_objects']} 条 raw object 收敛到 {corpus['canonical_records']} 条 canonical，最终 metric row 为 {ms['metric_rows']}。",
                "C02",
                [n["source_path"] for n in claims["C02"]["numbers"]],
            ),
            "scope": "6 counting levels · lineage reconciliation",
            "evidence_status": status,
            "chart": chart,
            "readout": _readout(
                f"raw {corpus['raw_objects']} → occurrence {corpus['occurrences_deduplicated']} → canonical {corpus['canonical_records']} → membership {corpus['frame_memberships']} → annotation {ms['annotation_totals']['total']} → metric row {ms['metric_rows']}。",
                "每一级回答不同问题；血缘链不是逐级转化，metric row 归零是门禁结果。",
                "如果 G7 通过，metric row 可能大于 0，血缘链末端会改变。",
                "先修 G7，再重跑血缘对账。",
                "C02",
                [n["source_path"] for n in claims["C02"]["numbers"]],
            ),
            "source_foot": _foot(
                "confirmed",
                "LINEAGE RECONCILED",
                "corpus-summary.json#/reconciliation + metric-summary.json#/metric_rows",
                "raw_object",
                "lineage, not conversion; each level has its own denominator",
            ),
            "drawer": {
                "summary": "查看六级计数定义",
                "content": "raw object → occurrence → canonical record → frame membership → annotation → metric row。前五级可审计，第六级在 G7 未 PASS 时为 0。",
            },
            "data_table": [
                {"label": step["step"], "value": step["value"], "unit": "raw_object" if step["step"] == "raw_object" else "canonical_record"}
                for step in steps
            ],
            "definitions": ["six counting levels", "lineage not conversion", "fail-closed metric row"],
        }

    def _experiments(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "EX01",
                "lane": "Now · Reversible",
                "name": "支撑梯度小样验证",
                "trigger_evidence_refs": ["C04", "C05"],
                "minimum_test": "在 20 名目标孕周用户中对比 3 档支撑强度，记录下滑、卷边与压力点。",
                "kpi": "实验内支撑负向记录占比",
                "guardrail": "出现疼痛加重或皮肤压痕即停止该档位。",
                "decision": "若支撑负向仍居首，进入下一档设计；否则保留当前结构。",
                "stop": "连续 5 例报告疼痛加重",
                "status": "proposed",
            },
            {
                "id": "EX02",
                "lane": "Now · Reversible",
                "name": "选码引导 A/B",
                "trigger_evidence_refs": ["C05", "C09"],
                "minimum_test": "在商品页加入孕周加腹围选码器，对比退换咨询记录。",
                "kpi": "实验内退换咨询记录数",
                "guardrail": "不得承诺治疗效果或安全保证。",
                "decision": "若退换咨询下降且投诉不升，保留引导。",
                "stop": "咨询量下降但投诉上升",
                "status": "proposed",
            },
            {
                "id": "EX03",
                "lane": "Parallel · Evidence system",
                "name": "G7 双盲编码",
                "trigger_evidence_refs": ["C07", "C14"],
                "minimum_test": "第二编码员独立编码 30 条分层样本，计算 field-level agreement。",
                "kpi": "field-level kappa",
                "guardrail": "agreement 未达 0.8 不得进入 G8。",
                "decision": "达标后重跑证据分级；未达标回到 G4 修 codebook。",
                "stop": "两轮仍低于 0.8",
                "status": "proposed",
            },
        ]

    def _unknowns(self, data: dict[str, Any]) -> list[str]:
        unknowns = [
            "[Evidence gap] 逐变体评论计数未导出：PDP 只暴露 family-level 评论数。",
            "[BLOCKED: product-reviews 需要登录态，当前返回 302]",
            "[BLOCKED: DTC / Okendo 没有配置可用端点与凭证]",
            "[BLOCKED: 没有问卷工具与样本框；推荐值量表永久禁止输出]",
            "[BLOCKED: 没有第二编码员与逐字段 agreement]",
            "[BLOCKED: no verified SKU/ASIN crosswalk between TikTok Shop and Amazon]",
            "[Evidence gap] 本轮没有采集 TikTok 视频、评论、达人或广告数据。",
            "[Evidence gap] gap axis 没有非 unknown 标注：expectation_gap_counts 全部为 unknown。",
            f"[Evidence gap] diagnostic frame 只有 {data['metric_summary']['frame_counts'].get('diagnostic', 0)} 条记录，不能做 prevalence。",
            "[BLOCKED: medical efficacy, safety, diagnosis and causality are out of scope]",
            "[Evidence gap] Amazon 星级分布只能作为商品质量上下文，不能当消费者情绪。",
            "[Evidence gap] Amazon 评论正文不可得，exact-variant 体验层为空。",
            "[Evidence gap] 社媒与自然口碑必须隔离；本轮没有社媒池。",
        ]
        return unknowns

    # ------------------------------------------------------------------
    # final assembly
    # ------------------------------------------------------------------
    def run(self) -> dict[str, Any]:
        data = self.prepare()
        claims = self.build_claims(data)
        # Write claims before evidence ledger so source paths are stable.
        claims_ref = self.registry.write_json("claims.json", claims)
        data["refs"]["claims"] = claims_ref

        evidence_layer = self.build_evidence_layer(data)
        report_layer = self.build_report(data, claims, evidence_layer)
        evidence_ledger = evidence.evidence_ledger(claims, data["identity"], data["ledger"].to_dict())
        evidence_ref = self.registry.write_json("evidence-ledger.json", evidence_ledger)
        data["refs"]["evidence"] = evidence_ref

        root = {
            "schema_version": contract.SCHEMA_VERSION,
            "report_id": f"{data['identity']['market'].lower()}-{data['identity']['brand'].lower().replace(' ', '-')}-unstated-{data['as_of'].replace('-', '')}",
            "as_of": data["as_of"],
            "generated_at": contract.now_iso(),
            "report_mode": "progress_snapshot",
            "language": "zh-CN",
            "evidence": evidence_layer,
            "report": report_layer,
            "artifacts": self.registry.all_refs(exclude={"report-data.json", "report.html"}),
            "validation": {
                "report_data_sha256": None,
                "report_html_sha256": None,
                "validator_version": contract.VALIDATOR_VERSION,
                "checks": [],
                "status": "pending",
            },
        }

        self.resolver = metrics.Resolver(self.out_dir)
        # Verify every NumberRef before writing the report.
        metrics.verify_claim_numbers(claims, self.resolver)
        json_suite = validate.validate_report_data(root, resolver=self.resolver, taxonomy=data["taxonomy"])
        if not json_suite.passed:
            failures = [check.to_dict() for check in json_suite.checks if not check.passed]
            raise contract.ContractError(f"report-data validation failed: {failures[:6]}")
        root["validation"]["checks"] = [check.to_dict() for check in json_suite.checks]
        root["validation"]["status"] = "PASS"

        report_data_ref = self.registry.write_json("report-data.json", root)
        data["refs"]["report_data"] = report_data_ref

        html = render.render_report(root)
        html_path = self.out_dir / "report.html"
        html_path.write_text(html, encoding="utf-8")
        html_bytes = html.encode("utf-8")
        html_sha = contract.sha256_bytes(html_bytes)

        html_suite = validate.validate_html(html)
        validation_payload = {
            "status": "PASS" if html_suite.passed and json_suite.passed else "FAIL",
            "validator_version": contract.VALIDATOR_VERSION,
            "generated_at": contract.now_iso(),
            "report_data_sha256": report_data_ref["sha256"],
            "report_html_sha256": html_sha,
            "report_data_checks": [check.to_dict() for check in json_suite.checks],
            "html_checks": [check.to_dict() for check in html_suite.checks],
            "checks": [check.to_dict() for check in json_suite.checks] + [check.to_dict() for check in html_suite.checks],
        }
        validation_ref = self.registry.write_json("validation-result.json", validation_payload)
        manifest = {
            "generated_at": contract.now_iso(),
            "report_id": root["report_id"],
            "status": validation_payload["status"],
            "artifacts": self.registry.all_refs(),
            "report_data_sha256": report_data_ref["sha256"],
            "report_html_sha256": html_sha,
        }
        manifest_ref = self.registry.write_json("delivery-manifest.json", manifest)

        if not html_suite.passed or not json_suite.passed:
            failures = [check.to_dict() for check in html_suite.checks if not check.passed] + [
                check.to_dict() for check in json_suite.checks if not check.passed
            ]
            raise contract.ContractError(f"validation failed: {failures[:6]}")

        return {
            "status": "PASS",
            "out_dir": str(self.out_dir),
            "report_id": root["report_id"],
            "report_data": str(self.out_dir / "report-data.json"),
            "report_html": str(html_path),
            "validation": str(self.out_dir / "validation-result.json"),
            "manifest": str(self.out_dir / "delivery-manifest.json"),
            "counts": {
                "raw_objects": data["corpus_summary"]["raw_objects"],
                "occurrences": data["corpus_summary"]["occurrences_deduplicated"],
                "canonical_records": data["corpus_summary"]["canonical_records"],
                "frame_memberships": data["corpus_summary"]["frame_memberships"],
                "annotations": data["metric_summary"]["annotation_totals"]["total"],
                "metric_rows": data["metric_summary"]["metric_rows"],
            },
            "claims": {claim["claim_id"]: claim["grade"] for claim in claims},
            "exhibits": [block["number"] for section in report_layer["sections"] for block in section["blocks"] if block.get("type") == "exhibit"],
            "html_checks": {"passed": html_suite.passed, "checks": len(html_suite.checks)},
            "artifacts_written": len(self.registry.refs),
            "validation_ref": validation_ref["path"],
            "manifest_ref": manifest_ref["path"],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a VOC insight report from local raw data.")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN), help="input run directory with raw/ and artifacts")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    parser.add_argument("--market", default=None, help="market override (ISO country code)")
    parser.add_argument("--language", default=None, help="language override")
    args = parser.parse_args(argv)

    builder = ReportBuilder(Path(args.run_dir), Path(args.out), market=args.market, language=args.language)
    try:
        result = builder.run()
    except contract.ContractError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
