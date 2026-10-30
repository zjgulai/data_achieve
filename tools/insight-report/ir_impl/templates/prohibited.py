#!/usr/bin/env python3
"""Prohibited outputs — the last substantive block before the footer."""
from __future__ import annotations

from templates import components as c


def render_prohibited(report: dict) -> str:
    items = []
    for p in report.get("prohibited_outputs", []):
        items.append(
            f'<li><span class="po-id">{c.esc(p.get("id"))}</span>'
            f'<div><b>{c.esc(p.get("label"))}</b><span>{c.esc(p.get("reason"))}</span>'
            f'<span class="po-sections">适用：{c.esc(", ".join(p.get("applies_to_sections", [])))}</span></div>'
            f'<span class="po-gate">{c.esc(p.get("gate"))} · {c.esc(p.get("severity"))}</span></li>'
        )
    return (
        '<section class="prohibited-block" id="prohibited"><div class="shell">'
        '<div class="section-index">APPENDIX / PROHIBITED OUTPUTS · 禁止输出清单</div>'
        "<h2>本报告明确禁止输出的结论，以及为什么不能说</h2>"
        '<p class="section-deck">以下条目是硬约束。任何 section 违反其中一条，构建必须失败。</p>'
        f'<ol class="prohibited-list">{"".join(items)}</ol>'
        "</div></section>"
    )
