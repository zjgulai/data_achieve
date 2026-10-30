#!/usr/bin/env python3
"""Six-level evidence status legend (section 10)."""
from __future__ import annotations

import ir_contract as C
from templates import components as c


def render_status_legend(block: dict) -> str:
    rows = []
    for item in block.get("statuses", []):
        status = item.get("status")
        label = item.get("label") or C.STATUS_LABEL.get(status, status)
        badge = f'<span class="evidence-badge {C.STATUS_CLASS.get(status, "gap")}">{c.esc(label)}</span>'
        rows.append(
            "<tr>"
            f'<td>{badge}</td>'
            f'<td>{c.esc(item.get("rule"))}</td>'
            f'<td>{c.esc(item.get("may_use"))}</td>'
            f'<td>{c.esc(item.get("may_not_use"))}</td>'
            "</tr>"
        )
    return (
        '<div class="status-legend-wrap">'
        f'<h3>{c.esc(block.get("title") or "六级证据状态：先命中先停")}</h3>'
        '<table class="status-legend"><thead><tr><th>状态</th><th>判定条件</th><th>可以用于</th><th>不能用于</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )
