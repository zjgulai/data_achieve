#!/usr/bin/env python3
"""Section 02 — EXPERIENCE SIGNATURE / 体验签名."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "02")
    if sec is None:
        return missing("02", "report.sections 中没有 02 体验签名。")
    exhibit = first_exhibit(sec, "02")
    if not exhibit:
        return missing("02", "02 体验签名缺少 EXHIBIT 02（12 主题极性）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("02", sec, body))
