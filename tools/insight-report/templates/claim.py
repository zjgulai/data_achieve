#!/usr/bin/env python3
"""Claim block renderer."""
from __future__ import annotations

from templates.components import claim_card


def render_claim(block: dict, claims_by_id: dict) -> str:
    cid = block.get("claim_id")
    claim = claims_by_id.get(cid)
    if claim is None:
        raise ValueError(f"claim block references unknown claim_id {cid!r}")
    return claim_card(claim)
