#!/usr/bin/env python3
"""Section 03 — SAMPLE LENSES / 样本视角."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "03")
    if sec is None:
        return missing("03", "report.sections 中没有 03 样本视角。")
    exhibit = first_exhibit(sec, "03")
    if not exhibit:
        return missing("03", "03 样本视角缺少 EXHIBIT 03（三镜头对比）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("03", sec, body))
