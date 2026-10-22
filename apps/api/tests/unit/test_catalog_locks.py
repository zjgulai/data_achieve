"""SP-41 目录锁守卫测试。

本文件固定六件事：

1. 运行时 tool catalog 与 tool-catalog.lock 完全一致。
2. 运行时 platform package catalog 与 platform-packages.lock 完全一致。
3. 两份运行时目录共享同一个 catalog_digest。
4. generated 索引存在，且内容投影等于运行时 platform package catalog。
5. 生成物比对忽略环境派生字段，但真实内容变化必须失败。
6. 采集器账本差集变化必须阻断。

生成物缺失时直接失败。CI 与本地 pytest 入口必须先运行生成命令。
篡改 lock 的测试复制最小 root 到 tmp_path。
守卫仍从源码构建运行时目录，只从 --root 读取 lock 与 generated。
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from data_intelligence_hub.platform_packages.builder import (
    catalog_content_projection,
    compute_catalog_digest,
)
from data_intelligence_hub.platform_packages.models import PlatformPackageCatalog

ROOT = Path(__file__).resolve().parents[4]
GUARD = ROOT / "scripts/check_catalog_locks.py"
TOOL_LOCK = ROOT / "configs/tool-catalog.lock.json"
PACKAGE_LOCK = ROOT / "configs/platform-packages.lock.json"
GENERATED_INDEX = ROOT / "generated/platform-packages.json"

GENERATE_COMMAND = (
    "cd apps/api && uv run python ../../scripts/generate_platform_packages.py"
)
LEDGER_CHECKS = (
    "live.collector_declared_without_impl",
    "live.collector_registered_without_declaration",
)


def _run_guard(*args: str) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(GUARD), "--json", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            "守卫未输出 JSON："
            f"stdout={result.stdout!r} stderr={result.stderr!r} ({exc})"
        )
    return result.returncode, cast(dict[str, Any], payload)


def _find_check(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    for item in report.get("checks", []):
        if item.get("check_id") == check_id:
            return cast(dict[str, Any], item)
    pytest.fail(f"报告缺少检查项 {check_id}：{report}")


def _load_guard_module() -> Any:
    """按路径加载守卫脚本，便于测试白名单与报告逻辑。"""
    spec = importlib.util.spec_from_file_location(
        "check_catalog_locks_under_test", GUARD
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _content_diffs(expected: Any, actual: Any, path: str = "<root>") -> list[str]:
    """递归比较两个 JSON 值，返回字段级差异。"""
    if type(expected) is not type(actual):
        return [
            f"{path}: 类型不同 "
            f"expected={type(expected).__name__} actual={type(actual).__name__}"
        ]
    if isinstance(expected, dict):
        diffs: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}"
            if key not in expected:
                diffs.append(f"{child}: 生成物多出字段")
            elif key not in actual:
                diffs.append(f"{child}: 生成物缺少字段")
            else:
                diffs.extend(_content_diffs(expected[key], actual[key], child))
        return diffs
    if isinstance(expected, list):
        diffs = []
        if len(expected) != len(actual):
            diffs.append(
                f"{path}: 长度不同 expected={len(expected)} actual={len(actual)}"
            )
        for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
            diffs.extend(_content_diffs(left, right, f"{path}[{index}]"))
        return diffs
    if expected != actual:
        return [f"{path}: expected={expected!r} actual={actual!r}"]
    return []


def _require_generated() -> None:
    assert GENERATED_INDEX.is_file(), (
        "generated/platform-packages.json 不存在。"
        f"先运行：{GENERATE_COMMAND}。CI 必须先运行同一命令。"
    )


def _load_generated_catalog() -> PlatformPackageCatalog:
    _require_generated()
    return PlatformPackageCatalog.model_validate_json(
        GENERATED_INDEX.read_text(encoding="utf-8")
    )


def _assert_projection_matches(
    live: PlatformPackageCatalog,
    generated: PlatformPackageCatalog,
) -> None:
    diffs = _content_diffs(
        catalog_content_projection(live),
        catalog_content_projection(generated),
    )
    assert not diffs, "生成物与运行时目录内容不一致：\n" + "\n".join(diffs[:20])


def _mutate_nested(
    data: dict[str, Any],
    path: tuple[str | int, ...],
    mutate: Callable[[Any], Any],
) -> None:
    target: Any = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = mutate(target[path[-1]])


async def _live_catalogs() -> tuple[Any, Any]:
    from data_intelligence_hub.api.routes.collectors import get_collector_catalog
    from data_intelligence_hub.platform_packages.builder import (
        build_platform_package_catalog,
    )
    from data_intelligence_hub.tool_catalog.projection import build_tool_catalog

    source = await get_collector_catalog()
    catalog = build_platform_package_catalog(source)
    return catalog, build_tool_catalog(catalog)


async def test_tool_catalog_matches_tool_lock_exactly() -> None:
    """运行时工具目录必须逐字段等于 tool-catalog.lock。"""
    _, tools = await _live_catalogs()
    lock = json.loads(TOOL_LOCK.read_text(encoding="utf-8"))
    assert lock == {
        "schema_version": tools.schema_version,
        "contract_version": tools.contract_version,
        "catalog_digest": tools.catalog_digest,
        "tool_count": tools.tool_count,
        "canonical_tool_count": tools.canonical_tool_count,
        "executable_count": tools.executable_count,
    }


async def test_platform_package_catalog_matches_package_lock_exactly() -> None:
    """运行时平台包目录必须逐字段等于 platform-packages.lock。"""
    catalog, _ = await _live_catalogs()
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
    assert lock == {
        "schema_version": catalog.schema_version,
        "catalog_digest": catalog.catalog_digest,
        "platform_count": catalog.platform_count,
        "capability_count": catalog.capability_count,
        "unique_endpoint_count": catalog.unique_endpoint_count,
    }


async def test_runtime_tool_and_package_catalogs_share_digest() -> None:
    """工具目录直接复制平台包 digest。两份运行时值必须相等。"""
    catalog, tools = await _live_catalogs()
    assert tools.catalog_digest == catalog.catalog_digest
    assert len(tools.catalog_digest) == 64


def test_generated_index_matches_runtime_catalog() -> None:
    """generated 索引必须存在，且内容投影等于运行时平台包目录。

    生成物不在版本控制里。缺失时给出明确失败，不再 skip。
    CI 与本地 pytest 入口必须先运行生成命令。
    """
    catalog, _ = asyncio.run(_live_catalogs())
    _assert_projection_matches(catalog, _load_generated_catalog())


ENV_CASES = [
    pytest.param({}, id="default"),
    pytest.param({"COLLECTION_NETWORK_MODE": "restricted"}, id="restricted"),
    pytest.param({"APP_ENV": "production"}, id="production"),
]


@pytest.mark.parametrize("env", ENV_CASES)
def test_generated_matches_runtime_in_every_environment(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
) -> None:
    """默认、restricted、production 三种环境都必须通过。

    policy_block_reason 与 verified_count 随环境变化。
    内容投影必须剔除它们，否则这里会误报。
    """
    monkeypatch.delenv("COLLECTION_NETWORK_MODE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    catalog, _ = asyncio.run(_live_catalogs())
    _assert_projection_matches(catalog, _load_generated_catalog())


CONTENT_TAMPER_CASES = [
    pytest.param(
        ("packages", 0, "endpoints", 0, "label"),
        lambda value: value + "-tampered",
        "label",
        id="label",
    ),
    pytest.param(
        ("packages", 0, "endpoints", 0, "endpoint_type"),
        lambda value: value + "_tampered",
        "endpoint_type",
        id="endpoint_type",
    ),
]


@pytest.mark.parametrize(("path", "mutate", "needle"), CONTENT_TAMPER_CASES)
def test_content_projection_detects_real_changes(
    path: tuple[str | int, ...],
    mutate: Callable[[Any], Any],
    needle: str,
) -> None:
    """改动 label 或 endpoint_type 必须产生字段级差异。"""
    catalog, _ = asyncio.run(_live_catalogs())
    generated = catalog.model_dump(mode="json")
    _mutate_nested(generated, path, mutate)
    tampered = PlatformPackageCatalog.model_validate(generated)

    diffs = _content_diffs(
        catalog_content_projection(catalog),
        catalog_content_projection(tampered),
    )
    assert diffs, f"改动 {needle} 未被发现"
    assert any(needle in diff for diff in diffs), diffs
    assert compute_catalog_digest(tampered.packages) != catalog.catalog_digest


def test_content_projection_detects_digest_change() -> None:
    """改动 catalog_digest 必须产生字段级差异。"""
    catalog, _ = asyncio.run(_live_catalogs())
    generated = catalog.model_dump(mode="json")
    generated["catalog_digest"] = _flip_digest(generated["catalog_digest"])
    tampered = PlatformPackageCatalog.model_validate(generated)

    diffs = _content_diffs(
        catalog_content_projection(catalog),
        catalog_content_projection(tampered),
    )
    assert any("catalog_digest" in diff for diff in diffs), diffs


def test_digest_ignores_environment_derived_fields() -> None:
    """verified_count 与 policy_block_reason 不参与 digest。"""
    catalog, _ = asyncio.run(_live_catalogs())
    generated = catalog.model_dump(mode="json")
    for package in generated["packages"]:
        package["verified_count"] = package["verified_count"] + 1
        for endpoint in package["endpoints"]:
            endpoint["policy_block_reason"] = "offline: 测试环境"
    tampered = PlatformPackageCatalog.model_validate(generated)

    assert compute_catalog_digest(tampered.packages) == catalog.catalog_digest
    assert catalog_content_projection(tampered) == catalog_content_projection(catalog)


def test_guard_passes_with_generated_required() -> None:
    """干净工作树必须通过阻断式守卫。"""
    code, report = _run_guard("--require-generated")
    assert code == 0, report.get("problems")
    assert report["status"] == "passed"
    assert report["violations"] == []
    assert report["layers_present"] == {
        "live": "present",
        "tool_lock": "present",
        "package_lock": "present",
        "generated_index": "present",
    }


@pytest.mark.parametrize("env", ENV_CASES)
def test_guard_passes_in_every_environment(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
) -> None:
    """守卫在默认、restricted、production 三种环境都必须通过。"""
    monkeypatch.delenv("COLLECTION_NETWORK_MODE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    code, report = _run_guard("--require-generated")
    assert code == 0, report.get("problems")
    assert report["violations"] == []


def _copy_configs(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir()
    shutil.copy2(TOOL_LOCK, tmp_path / "configs/tool-catalog.lock.json")
    shutil.copy2(PACKAGE_LOCK, tmp_path / "configs/platform-packages.lock.json")
    return tmp_path


def test_guard_requires_generated_index(tmp_path: Path) -> None:
    """--require-generated 时，缺少生成物必须失败。"""
    root = _copy_configs(tmp_path)
    code, report = _run_guard("--root", str(root), "--require-generated")
    assert code == 1
    assert report["status"] == "failed"
    check = _find_check(report, "generated.present")
    assert check["ok"] is False
    assert check["layer"] == "generated_index"


def _flip_digest(value: str) -> str:
    head = "1" if value[0] != "1" else "0"
    return head + value[1:]


def _add_one(value: int) -> int:
    return value + 1


Tamper = tuple[str, str, Callable[[Any], Any], str]

TAMPER_CASES: list[Tamper] = [
    ("tool-catalog.lock.json", "tool_count", _add_one, "tool_lock.tool_count_eq_live"),
    (
        "tool-catalog.lock.json",
        "catalog_digest",
        _flip_digest,
        "tool_lock.digest_eq_live",
    ),
    (
        "platform-packages.lock.json",
        "capability_count",
        _add_one,
        "package_lock.capability_count_eq_live",
    ),
    (
        "platform-packages.lock.json",
        "catalog_digest",
        _flip_digest,
        "package_lock.digest_eq_live",
    ),
]


@pytest.mark.parametrize(("lock_name", "field", "mutate", "check_id"), TAMPER_CASES)
def test_tampered_lock_fails_with_field_detail(
    tmp_path: Path,
    lock_name: str,
    field: str,
    mutate: Callable[[Any], Any],
    check_id: str,
) -> None:
    """篡改 lock 的计数或 digest，守卫退出 1，并指出字段。"""
    root = _copy_configs(tmp_path)
    lock_path = root / "configs" / lock_name
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    original = lock[field]
    lock[field] = mutate(original)
    lock_path.write_text(
        json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    code, report = _run_guard("--root", str(root))
    assert code == 1, report
    assert report["status"] == "failed"
    check = _find_check(report, check_id)
    assert check["ok"] is False
    assert check["field"] == field
    assert check["expected"] == original
    assert check["actual"] == lock[field]
    assert any(problem.startswith(check_id) for problem in report["problems"])


def test_tampered_generated_index_fails_with_field_detail(tmp_path: Path) -> None:
    """篡改生成物的 digest，守卫退出 1，并指出字段。"""
    assert GENERATED_INDEX.is_file(), (
        "generated/platform-packages.json 不存在。"
        f"先运行：{GENERATE_COMMAND}。"
    )
    root = _copy_configs(tmp_path)
    (root / "generated").mkdir()
    shutil.copy2(GENERATED_INDEX, root / "generated/platform-packages.json")
    index_path = root / "generated/platform-packages.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    original = index["catalog_digest"]
    index["catalog_digest"] = _flip_digest(original)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    code, report = _run_guard("--root", str(root), "--require-generated")
    assert code == 1, report
    check = _find_check(report, "generated.digest_eq_live")
    assert check["ok"] is False
    assert check["field"] == "catalog_digest"
    assert check["expected"] == original
    assert check["actual"] == index["catalog_digest"]


@pytest.mark.parametrize(("path", "mutate", "needle"), CONTENT_TAMPER_CASES)
def test_guard_detects_generated_content_tamper(
    tmp_path: Path,
    path: tuple[str | int, ...],
    mutate: Callable[[Any], Any],
    needle: str,
) -> None:
    """改动生成物的 label 或 endpoint_type，守卫必须退出 1。

    顶层 catalog_digest 保持不变。守卫重算内容摘要后必须发现差异。
    """
    _require_generated()
    root = _copy_configs(tmp_path)
    (root / "generated").mkdir()
    index = json.loads(GENERATED_INDEX.read_text(encoding="utf-8"))
    _mutate_nested(index, path, mutate)
    (root / "generated/platform-packages.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    code, report = _run_guard("--root", str(root), "--require-generated")
    assert code == 1, report
    check = _find_check(report, "generated.recomputed_digest_eq_live")
    assert check["ok"] is False
    assert check["field"] == "packages"
    assert check["expected"] != check["actual"]
    assert check["severity"] == "blocker"
    assert any(
        problem.startswith("generated.recomputed_digest_eq_live")
        for problem in report["problems"]
    ), f"{needle} 篡改未进入阻断列表"


def test_ledger_allowlists_match_live_sets_exactly() -> None:
    """两个账本差集必须与白名单逐元素相等。"""
    guard = _load_guard_module()
    ledger = guard._build_ledger()
    assert ledger["declared"] - ledger["registry"] == set(
        guard.KNOWN_DECLARED_WITHOUT_IMPL
    )
    assert ledger["registry"] - ledger["declared"] == set(
        guard.KNOWN_REGISTERED_WITHOUT_DECLARATION
    )


def test_ledger_checks_are_blockers() -> None:
    """账本差集检查的 severity 必须是 blocker，层归 ledger。"""
    code, report = _run_guard("--require-generated")
    assert code == 0, report.get("problems")
    for check_id in LEDGER_CHECKS:
        check = _find_check(report, check_id)
        assert check["ok"] is True
        assert check["severity"] == "blocker"
        assert check["layer"] == "ledger"
        assert check["expected"] == check["actual"]


LEDGER_DRIFT_CASES = [
    pytest.param(
        "KNOWN_DECLARED_WITHOUT_IMPL",
        "live.collector_declared_without_impl",
        id="declared-without-impl",
    ),
    pytest.param(
        "KNOWN_REGISTERED_WITHOUT_DECLARATION",
        "live.collector_registered_without_declaration",
        id="registered-without-declaration",
    ),
]


@pytest.mark.parametrize(("constant", "check_id"), LEDGER_DRIFT_CASES)
def test_changed_ledger_allowlist_blocks(
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    check_id: str,
) -> None:
    """白名单任何变化都必须阻断，退出码 1。"""
    guard = _load_guard_module()
    original = set(getattr(guard, constant))
    monkeypatch.setattr(
        guard,
        constant,
        frozenset(original | {"ghost_collector"}),
    )

    report = guard.build_report(ROOT, require_generated=True)

    assert report["exit_code"] == 1
    assert report["status"] == "failed"
    check = _find_check(report, check_id)
    assert check["ok"] is False
    assert check["severity"] == "blocker"
    assert check["layer"] == "ledger"
    assert check["expected"] == sorted(original | {"ghost_collector"})
    assert check["actual"] == sorted(original)
    assert any(problem.startswith(check_id) for problem in report["problems"])
