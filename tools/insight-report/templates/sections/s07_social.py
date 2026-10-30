#!/usr/bin/env python3
"""Section 07 — SOCIAL FIREWALL / 社媒防火墙."""
from __future__ import annotations

from templates.exhibit import render_exhibit
from templates.section_helpers import SectionResult, get_section, first_exhibit, render_claim_blocks, render_gap_blocks, section_html, missing


def render(data: dict) -> SectionResult:
    sec = get_section(data, "07")
    if sec is None:
        return missing("07", "evidence.social 为空：本轮没有采集社媒池，无法生成社媒防火墙。")
    exhibit = first_exhibit(sec, "07")
    if not exhibit:
        return missing("07", "07 社媒防火墙缺少 EXHIBIT 07（社媒分流）。")
    body = render_exhibit(exhibit) + render_claim_blocks(sec, data) + render_gap_blocks(sec)
    return SectionResult(section_html("07", sec, body))
