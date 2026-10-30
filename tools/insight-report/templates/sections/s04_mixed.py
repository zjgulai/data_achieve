#!/usr/bin/env python3
"""Section 04 — MIXED EXPERIENCE / 混合体验."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "04")
    if sec is None:
        return missing("04", "report.sections 中没有 04 混合体验。")
    exhibit = first_exhibit(sec, "04")
    if not exhibit:
        return missing("04", "04 混合体验缺少 EXHIBIT 04（共现矩阵）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("04", sec, body))
