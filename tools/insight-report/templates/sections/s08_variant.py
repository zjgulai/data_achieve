#!/usr/bin/env python3
"""Section 08 — EVIDENCE APPLICABILITY / 证据适用性."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "08")
    if sec is None:
        return missing("08", "report.sections 中没有 08 证据适用性。")
    exhibit = first_exhibit(sec, "08")
    if not exhibit:
        return missing("08", "08 证据适用性缺少 EXHIBIT 08（变体网格）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("08", sec, body))
