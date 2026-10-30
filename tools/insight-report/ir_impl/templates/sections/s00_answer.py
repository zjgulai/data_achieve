#!/usr/bin/env python3
"""Section 00 — EXECUTIVE ANSWER."""
from __future__ import annotations

from templates import components as c
from templates.section_helpers import SectionResult, get_section, blocks_of_type, render_claim_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "00")
    if sec is None:
        return missing("00", "report.sections 中没有 00 执行答案。")
    stacks = blocks_of_type(sec, "answer_stack")
    if not stacks:
        return missing("00", "00 执行答案缺少 answer_stack block。")
    decision = data.get("report", {}).get("decision", {})
    if not decision.get("decision_question") or not c.text(decision.get("answer")):
        return missing("00", "report.decision 缺少 decision_question 或 answer，无法输出行动方案。")

    def list_row(label: str, items: list[str]) -> str:
        lis = "".join(f"<li>{c.esc(x)}</li>" for x in items)
        return (
            f'<article class="answer-row"><div class="label">{label}</div>'
            f'<h3>{c.esc(items[0]) if items else "—"}</h3>'
            f'<ul class="answer-list">{lis}</ul></article>'
        )

    rows = [
        f'<article class="answer-row"><div class="label">Decision question</div>'
        f'<h3>{c.esc(decision.get("decision_question"))}</h3>'
        f'<p>来自 G0 decision charter；本报告不新增决策问题。</p></article>',
        f'<article class="answer-row"><div class="label">Answer</div>'
        f'<h3>{c.esc(c.text(decision.get("answer")))}</h3>'
        f'<p>答案引用 claim：{c.esc(" / ".join(stacks[0].get("claim_ids", [])))}。'
        f'每个数字与限制见对应 section 的四问 readout。</p></article>',
        list_row("Protect", decision.get("protect", [])),
        list_row("Resolve", decision.get("resolve", [])),
        list_row("Prove", decision.get("prove", [])),
    ]
    body = (
        '<div class="answer-stack">' + "".join(rows) + "</div>"
        + c.evidence_band(data.get("report", {}).get("claims", []))
        + render_claim_blocks(sec, data)
    )
    return SectionResult(section_html("00", sec, body))
