#!/usr/bin/env python3
"""What this report omits.

Every section is an independent pluggable function. When its required data is
missing the renderer omits the whole section instead of rendering a shell with
placeholder numbers. The omission and its reason are listed here, in view.
"""
from __future__ import annotations

from templates import components as c


def render_omissions(omissions: list[dict], total_sections: int) -> str:
    if not omissions:
        body = (
            f'<p class="omission-empty">本轮没有整节省略：{total_sections} 个 section 都有 required 数据。'
            "数据缺口仍可能出现在 section 内，见各处 [Evidence gap] 与 [BLOCKED] 标记。</p>"
        )
    else:
        items = "".join(
            f'<li><b>{c.esc(o.get("index"))} · {c.esc(o.get("kicker"))} · {c.esc(o.get("zh"))}</b>'
            f'<span>{c.esc(o.get("reason"))}</span></li>'
            for o in omissions
        )
        body = (
            f'<p class="omission-empty">本轮 {total_sections - len(omissions)} / {total_sections} 个 section 有 required 数据。'
            "以下 section 因 required 数据缺失而整节省略。缺口不是零，也不能用相邻数据推断。</p>"
            f'<ol class="omission-list">{items}</ol>'
        )
    return (
        '<section class="omissions-block" id="omissions"><div class="shell">'
        '<div class="section-index">APPENDIX / OMISSIONS · 本报告省略了什么</div>'
        "<h2>本报告省略了什么</h2>"
        f"{body}"
        "</div></section>"
    )
