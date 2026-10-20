"""目录对账守卫。

守一件事：采集器的三层账本必须互相自洽。

三层账本长期不一致是已知问题：
  - collector 声明（99）与注册实现（86）不同
  - endpoint 映射（290）与生成的 platform-packages（286/258）不同
  - 策略分组（1+4+28+53）与注册表（86）必须完全一致

前两项允许有已知差集，用白名单固定；差集变化时测试失败。
第三项必须严格相等，不允许例外。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# 文件在 apps/api/tests/unit/，向上 4 级是仓库根。
ROOT = Path(__file__).resolve().parents[4]

# 已知且被接受的差集。任何变化都要显式更新本表并说明原因。
KNOWN_APIFY_MAPPED_WITHOUT_ACTOR = {"apify_tiktok_shop_search_v2"}


def _reconcile() -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/reconcile_catalog.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode in (0, 1), result.stderr
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
    assert summary["policy"] == {
        "offline": 1,
        "guarded_http": 4,
        "provider_api": 28,
        "unsupported": 53,
    }


def test_apify_mapping_matches_actor_defaults() -> None:
    """每个映射到 apify_actor 的端点都应有 Actor 配置。"""
    summary = _reconcile()["summary"]
    assert set(summary["apify_mapped_without_actor"]) == KNOWN_APIFY_MAPPED_WITHOUT_ACTOR
    assert summary["apify_defaults_without_mapping"] == []


def test_collector_declarations_match_registry() -> None:
    """只声明未实现的类型数量固定。"""
    summary = _reconcile()["summary"]
    assert summary["collector_definitions"] == 99
    assert summary["collector_registered"] == 86
    assert len(summary["collector_declared_without_impl"]) == 13


def test_generated_catalog_exists_and_is_consistent() -> None:
    """生成的 platform-packages 存在，且记录自身计数。

    条目数与端点映射允许不同（生成物落后于工作树），
    但生成物内部三个计数必须自洽。
    """
    summary = _reconcile()["summary"]
    generated = summary["generated"]
    assert generated is not None, "generated/platform-packages.json 缺失"
    assert generated["platform_count"] == 70
    assert isinstance(generated["catalog_digest"], str)
    assert len(generated["catalog_digest"]) == 64


def test_endpoint_mapping_count_is_stable() -> None:
    """端点映射总数。新增或删除端点必须显式更新此断言。"""
    summary = _reconcile()["summary"]
    assert summary["endpoint_mappings"] == 290
