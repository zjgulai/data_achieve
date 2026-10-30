#!/usr/bin/env python3
"""Section 01 — CORE TENSION / 核心张力."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "01")
    if sec is None:
        return missing("01", "report.sections 中没有 01 核心张力。")
    exhibit = first_exhibit(sec, "01")
    if not exhibit:
        return missing("01", "01 核心张力缺少 EXHIBIT 01（记录级共现）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("01", sec, body))
