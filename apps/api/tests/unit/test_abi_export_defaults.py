"""Pin the ABI export approval default.

The bug: ``policy is not None and policy.require_dual_approval`` treated a
missing policy row as "no approval needed". The table default is true, and no
code created policy rows, so unmasked exports skipped approval in production.

The fix is a pure resolver. These tests fail if it goes back to fail-open.
"""

from __future__ import annotations

from types import SimpleNamespace

from data_intelligence_hub.services.abi_service import resolve_require_dual_approval


def test_missing_policy_requires_approval() -> None:
    assert resolve_require_dual_approval(None) is True


def test_policy_true_requires_approval() -> None:
    policy = SimpleNamespace(require_dual_approval=True)
    assert resolve_require_dual_approval(policy) is True


def test_policy_false_skips_approval() -> None:
    policy = SimpleNamespace(require_dual_approval=False)
    assert resolve_require_dual_approval(policy) is False


def test_policy_without_attribute_defaults_to_approval() -> None:
    assert resolve_require_dual_approval(object()) is True
