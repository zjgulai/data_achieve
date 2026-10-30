#!/usr/bin/env python3
"""Helpers shared by the pluggable section modules."""
from __future__ import annotations

from dataclasses import dataclass

import ir_contract as C
from templates import components as c
from templates.claim import render_claim
from templates.exhibit import render_exhibit


@dataclass
class SectionResult:
    html: str | None
    reason: str | None = None


def get_section(data: dict, index: str) -> dict | None:
    for s in data.get("report", {}).get("sections", []):
        if s.get("index") == index:
            return s
    return None


def first_exhibit(section: dict, number: str) -> dict | None:
    for b in section.get("blocks", []):
        if b.get("type") == "exhibit" and str(b.get("number")) == number:
            return b
    return None


def blocks_of_type(section: dict, btype: str) -> list[dict]:
    return [b for b in section.get("blocks", []) if b.get("type") == btype]


def claims_map(data: dict) -> dict:
    return {x.get("claim_id"): x for x in data.get("report", {}).get("claims", [])}


def render_claim_blocks(section: dict, data: dict) -> str:
    cmap = claims_map(data)
    out = []
    for b in blocks_of_type(section, "claim"):
        out.append(render_claim(b, cmap))
    return "".join(out)


def render_gap_blocks(section: dict) -> str:
    out = []
    for b in blocks_of_type(section, "gap"):
        out.append(
            '<div class="gap-block">'
            f'<div class="gap-title">{c.esc(b.get("title") or "[Evidence gap]")}</div>'
            f'<p class="gap-reason">{c.esc(b.get("reason"))}</p>'
            f'{c.readout(b.get("readout", {}), "gap")}'
            f'{c.source_foot(b.get("source_foot", {}))}'
            "</div>"
        )
    return "".join(out)


def section_html(index: str, section: dict, body: str) -> str:
    spec = C.SECTION_BY_INDEX[index]
    return c.section_shell(spec, section.get("title"), section.get("deck"), body, section.get("status", "ok"))


def missing(index: str, reason: str) -> SectionResult:
    return SectionResult(None, reason)
