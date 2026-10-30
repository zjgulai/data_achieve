#!/usr/bin/env python3
"""Section 09 — VALIDATION AGENDA / 验证议程."""
from __future__ import annotations

from templates import components as c
from templates.section_helpers import SectionResult, get_section, blocks_of_type, render_claim_blocks, render_gap_blocks, section_html, missing


def _experiment_card(exp: dict) -> str:
    return (
        f'<article class="experiment-card" data-experiment-id="{c.esc(exp.get("id"))}">'
        f'<div class="experiment-lane">{c.esc(exp.get("lane"))}</div>'
        f'<h3>{c.esc(exp.get("name"))}</h3>'
        f'<dl class="experiment-facts">'
        f'<div><dt>触发证据</dt><dd>{c.esc(", ".join(exp.get("trigger_evidence_refs", [])))}</dd></div>'
        f'<div><dt>最小测试</dt><dd>{c.esc(exp.get("minimum_test"))}</dd></div>'
        f'<div><dt>KPI</dt><dd>{c.esc(exp.get("kpi"))}</dd></div>'
        f'<div><dt>Guardrail</dt><dd>{c.esc(exp.get("guardrail"))}</dd></div>'
        f'<div><dt>决策规则</dt><dd>{c.esc(exp.get("decision"))}</dd></div>'
        f'<div><dt>停止条件</dt><dd>{c.esc(exp.get("stop"))}</dd></div>'
        f'<div><dt>状态</dt><dd>{c.esc(exp.get("status"))}（未审批不写成 approved）</dd></div>'
        f"</dl></article>"
    )


def render(data: dict) -> SectionResult:
    sec = get_section(data, "09")
    if sec is None:
        return missing("09", "report.sections 中没有 09 验证议程。")
    seqs = blocks_of_type(sec, "experiment_sequence")
    experiments = data.get("report", {}).get("experiments", [])
    if not seqs or not experiments:
        return missing("09", "report.experiments 为空：没有 owner 批准的可逆实验，本节只保留缺口。")
    by_id = {e.get("id"): e for e in experiments}
    cards = []
    for seq in seqs:
        for eid in seq.get("experiment_ids", []):
            exp = by_id.get(eid)
            if exp is None:
                continue
            cards.append(_experiment_card(exp))
    if not cards:
        return missing("09", "experiment_sequence 引用的实验不存在。")
    body = (
        '<div class="experiment-sequence">'
        '<p class="section-deck">所有实验都是 proposed；没有 G9 审批，不得写成 approved，也不得进入资源排序。</p>'
        + "".join(cards)
        + "</div>"
        + render_claim_blocks(sec, data)
        + render_gap_blocks(sec)
    )
    return SectionResult(section_html("09", sec, body))
