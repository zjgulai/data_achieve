#!/usr/bin/env python3
"""Section 05 — NEED STATES / 需求场景."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "05")
    if sec is None:
        return missing("05", "report.sections 中没有 05 需求场景。")
    exhibit = first_exhibit(sec, "05")
    if not exhibit:
        return missing("05", "05 需求场景缺少 EXHIBIT 05（四象限）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("05", sec, body))
