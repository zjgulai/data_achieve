"""目录对账守卫。

守一件事：采集器的三层账本必须互相自洽。

三层账本：
  - collector 声明与注册实现有已知差集
  - endpoint 映射与生成的 platform-packages 必须一致
  - 策略分组必须无遗漏地覆盖注册表

前两项用显式列表固定；差集变化时测试失败。
第三项必须严格相等，不允许例外。
生成物缺失时直接失败。CI 必须先运行生成命令。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# 文件在 apps/api/tests/unit/，向上 4 级是仓库根。
ROOT = Path(__file__).resolve().parents[4]
GUARD = ROOT / "scripts/check_catalog_locks.py"

# 已知且被接受的差集。任何变化都要显式更新本表并说明原因。
# 2026-10-21 清空：apify_tiktok_shop_search_v2 无 Actor 配置、调用返回 400，
# 已作为幽灵端点删除映射，现 Apify 映射与 Actor 配置一一对应。
KNOWN_APIFY_MAPPED_WITHOUT_ACTOR: set[str] = set()


def _guard_module() -> Any:
    """按路径加载守卫脚本，复用唯一一份账本白名单。"""
    spec = importlib.util.spec_from_file_location(
        "check_catalog_locks_for_reconciliation", GUARD
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reconcile() -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/reconcile_catalog.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_policy_groups_cover_registry_exactly() -> None:
    """策略四组必须无重叠、无遗漏地覆盖注册表。"""
    payload = _reconcile()
    summary = payload["summary"]
    assert summary["policy_unclassified"] == []
    assert summary["policy_unknown_types"] == []
    assert summary["policy_classified_total"] == summary["collector_registered"]


def test_policy_group_counts() -> None:
    """四组计数固定。变化说明有采集器被改分类，需要显式确认。"""
    summary = _reconcile()["summary"]
    # 2026-10-21：exa_agent 走 provider_api，28 → 29。
    assert summary["policy"] == {
        "offline": 1,
        "guarded_http": 4,
        "provider_api": 29,
        "unsupported": 53,
    }


def test_apify_mapping_matches_actor_defaults() -> None:
    """每个映射到 apify_actor 的端点都应有 Actor 配置。"""
    summary = _reconcile()["summary"]
    assert set(summary["apify_mapped_without_actor"]) == KNOWN_APIFY_MAPPED_WITHOUT_ACTOR
    assert summary["apify_defaults_without_mapping"] == []


def test_collector_declarations_match_registry() -> None:
    """两个账本差集必须与白名单逐元素相等。"""
    summary = _reconcile()["summary"]
    guard = _guard_module()
    assert summary["collector_definitions"] == 100
    # 2026-10-21：新增 exa_agent 采集器，注册数 86 → 87。
    assert summary["collector_registered"] == 87
    assert set(summary["collector_declared_without_impl"]) == set(
        guard.KNOWN_DECLARED_WITHOUT_IMPL
    )
    assert set(summary["collector_registered_without_declaration"]) == set(
        guard.KNOWN_REGISTERED_WITHOUT_DECLARATION
    )


def test_generated_catalog_exists_and_is_consistent() -> None:
    """生成的 platform-packages 必须存在，且与运行时口径一致。

    生成物不在版本控制里。缺少生成物时直接失败，不 skip。
    CI 必须先运行：
      cd apps/api && uv run python ../../scripts/generate_platform_packages.py
    """
    summary = _reconcile()["summary"]
    generated = summary["generated"]
    assert generated is not None, (
        "generated/platform-packages.json 不存在。"
        "先在 apps/api 下运行 uv run python ../../scripts/generate_platform_packages.py"
    )
    assert generated["platform_count"] == 70
    assert isinstance(generated["catalog_digest"], str)
    assert len(generated["catalog_digest"]) == 64
    # 284 是唯一端点单位。不要拿 312（视图条目）与它比较。
    assert generated["unique_endpoint_count"] == summary["endpoint_mappings"]
    assert generated["capability_count"] == generated["source_entry_count"]


def test_endpoint_mapping_count_is_stable() -> None:
    """端点映射总数。新增或删除端点必须显式更新此断言。

    2026-10-21：删除 8 个幽灵端点映射，290 → 282。
    幽灵端点与目录元数据现已对齐，差集为 0。
    2026-10-21（Exa 3.0 刷新）：新增 exa_search_lite，282 → 283。
    2026-10-21（P1 后续）：新增 exa_agent_research，283 → 284。
    """
    summary = _reconcile()["summary"]
    assert summary["endpoint_mappings"] == 284


def test_reconcile_rejects_removed_update_lock_option() -> None:
    """假 --update-lock 已移除。传入时必须作为未知参数失败。"""
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/reconcile_catalog.py"),
            "--json",
            "--update-lock",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert "--update-lock" in result.stderr
    # 参数解析失败，不应产生 JSON 报告。
    assert result.stdout.strip() == ""


def test_reconcile_help_does_not_advertise_update_lock() -> None:
    """帮助文本不得再宣传 --update-lock。"""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/reconcile_catalog.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0
    assert "--update-lock" not in result.stdout
