#!/usr/bin/env python3
"""Section 06 — MOMENTS OF TRUTH / 关键时刻."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "06")
    if sec is None:
        return missing("06", "report.sections 中没有 06 关键时刻。")
    exhibit = first_exhibit(sec, "06")
    if not exhibit:
        return missing("06", "06 关键时刻缺少 EXHIBIT 06（旅程覆盖条）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("06", sec, body))
