#!/usr/bin/env python3
"""Section 10 — TRUST & LIMITS / 信任与边界."""
from __future__ import annotations

from templates import components as c
from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, blocks_of_type, render_claim_blocks, render_gap_blocks, section_html, missing
from templates.status_legend import render_status_legend


def _gate_rail(gates: list[dict]) -> str:
    chips = "".join(
        f'<span class="gate-chip {c.esc(g.get("status"))}">{c.esc(g.get("gate_id"))} {c.esc(g.get("status"))}</span>'
        for g in gates
    )
    return f'<div class="gate-rail" aria-label="门禁状态">{chips}</div>'


def _unknowns(items: list[str]) -> str:
    lis = "".join(f"<li>{c.esc(x)}</li>" for x in items)
    return (
        '<div class="unknowns-block"><h3>未知与阻断</h3>'
        '<p>以下缺口在正文对应位置也有 [Evidence gap] 或 [BLOCKED] 标记；这里集中列出，避免遗漏。</p>'
        f'<ul class="unknown-list">{lis}</ul></div>'
    )


def render(data: dict) -> SectionResult:
    sec = get_section(data, "10")
    if sec is None:
        return missing("10", "report.sections 中没有 10 信任与边界。")
    e09 = first_exhibit(sec, "09")
    e10 = first_exhibit(sec, "10")
    legends = blocks_of_type(sec, "status_legend")
    if not e09 and not e10 and not legends:
        return missing("10", "10 信任与边界缺少 claim 成熟度、血缘瀑布与六级状态图例。")
    body = ""
    if e09:
        body += render_exhibit(e09)
    if e10:
        body += render_exhibit(e10)
    if legends:
        body += "".join(render_status_legend(b) for b in legends)
    gates = data.get("evidence", {}).get("gate", {}).get("gates", [])
    if gates:
        body += _gate_rail(gates)
    body += render_claim_blocks(sec, data)
    body += render_gap_blocks(sec)
    unknowns = data.get("report", {}).get("unknowns", [])
    if unknowns:
        body += _unknowns(unknowns)
    return SectionResult(section_html("10", sec, body))
