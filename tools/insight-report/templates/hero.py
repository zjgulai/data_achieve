#!/usr/bin/env python3
"""Hero renderer.

Hard rule: the four hero proofs must be ratios or gaps. A raw total such as
"18" raises AssertionError before any HTML is produced.
"""
from __future__ import annotations

from templates import components as c
import ir_contract as C


def assert_hero_proofs(proofs: list[dict]) -> None:
    assert len(proofs) == 4, f"hero must contain exactly 4 proofs, got {len(proofs)}"
    for i, proof in enumerate(proofs):
        ok, reason = C.is_ratio_or_gap(str(proof.get("value", "")))
        assert ok, f"hero proof {i + 1} rejected: {reason}"


def render_hero(report: dict) -> str:
    hero = report["hero"]
    proofs = hero.get("proofs", [])
    assert_hero_proofs(proofs)

    h1 = c.text(hero.get("h1"))
    h1_html = c.split_accent(h1, hero.get("h1_accent", ""))
    actions = "".join(
        f'<a class="{"primary" if a.get("primary") else ""}" href="{c.esc(a.get("href", "#main"))}">{c.esc(a.get("label"))}</a>'
        for a in hero.get("actions", [])
    )
    compass = "".join(
        f'<div class="compass-item"><b>{c.esc(x.get("label"))}</b><strong>{c.esc(x.get("title"))}</strong>'
        f'<p>{c.esc(x.get("note"))}</p></div>'
        for x in hero.get("compass", [])
    )
    ribbon = hero.get("truth_ribbon", {})
    cells = "".join(
        f'<div><b>{c.esc(x.get("value"))}</b><span>{c.esc(x.get("note"))}</span></div>'
        for x in ribbon.get("cells", [])
    )
    proofs_html = "".join(
        f'<article class="decision-proof"><div class="value num">{c.esc(p.get("value"))}</div>'
        f'<div class="label">{c.esc(p.get("label"))}</div><div class="note">{c.esc(p.get("note"))}</div></article>'
        for p in proofs
    )
    return (
        '<section class="hero" id="top"><div class="shell">'
        '<div class="report-hero"><div>'
        f'<div class="eyebrow">{c.esc(hero.get("eyebrow"))}</div>'
        f"<h1>{h1_html}</h1>"
        f'<p class="hero-lead">{c.esc(c.text(hero.get("lead")))}</p>'
        f'<div class="hero-actions">{actions}</div></div>'
        f'<aside class="decision-compass" aria-label="管理决策路径">{compass}</aside></div>'
        f'<div class="truth-ribbon" aria-label="报告证据状态"><div class="truth-label">{c.esc(ribbon.get("label"))}</div>{cells}</div>'
        f'<div class="decision-evidence" aria-label="首屏关键证据">{proofs_html}</div>'
        "</div></section>"
    )
