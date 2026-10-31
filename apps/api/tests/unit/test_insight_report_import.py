"""报告包校验与导入器测试。

覆盖验收清单 §7.1 中可在单测层验证的项目：哈希、归一化、脚本白名单、
事件属性、外链、路径越界、幂等与版本冲突。
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.scripts.import_insight_report import (
    InsightImportError,
    ReportHtmlSafetyError,
    import_bundle,
    validate_bundle,
)

BUNDLE_DIR = (
    Path(__file__).resolve().parents[4]
    / "tools"
    / "insight-reports"
    / "tiktok-viral-topic"
    / "2026-10-31"
)


@pytest.fixture()
def bundle_copy(tmp_path: Path) -> Path:
    target = tmp_path / "bundle"
    shutil.copytree(BUNDLE_DIR, target)
    return target


def _rewrite_bundle(
    bundle_dir: Path,
    mutate_html: Callable[[str], str],
) -> None:
    """修改正文并同步 manifest 的字节数与哈希，隔离安全校验用例。"""
    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    html = (bundle_dir / manifest["content"]["path"]).read_text(encoding="utf-8")
    mutated = mutate_html(html)
    (bundle_dir / manifest["content"]["path"]).write_text(mutated, encoding="utf-8")

    source = mutated.encode("utf-8")
    manifest["content"]["source_bytes"] = len(source)
    manifest["content"]["source_sha256"] = hashlib.sha256(source).hexdigest()
    normalized = mutated
    for rule in manifest["content"]["normalize"]:
        normalized = normalized.replace(rule["find"], rule["replace"])
    content = normalized.encode("utf-8")
    manifest["content"]["content_bytes"] = len(content)
    manifest["content"]["content_sha256"] = hashlib.sha256(content).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_real_bundle_validates_with_expected_hashes() -> None:
    bundle = validate_bundle(BUNDLE_DIR)

    assert bundle.source_bytes == 182450
    assert bundle.source_sha256 == (
        "415445711c9fc293d330c34cbb6a273af768348adbefe18739a4318ad31ed8d1"
    )
    assert bundle.content_bytes == 181984
    assert bundle.content_sha256 == (
        "f7f7c4f0b5483e789740345cff7c115100283b5ec1847cd181ef55e7f00b50dc"
    )
    assert "/tmp/" not in bundle.html


def test_tampered_source_is_rejected(bundle_copy: Path) -> None:
    report = bundle_copy / "report.html"
    report.write_text(report.read_text(encoding="utf-8") + "<!-- modified -->", encoding="utf-8")

    with pytest.raises(InsightImportError, match="字节数不一致|SHA-256 不一致"):
        validate_bundle(bundle_copy)


def test_unknown_inline_script_is_rejected(bundle_copy: Path) -> None:
    _rewrite_bundle(
        bundle_copy,
        lambda html: html.replace(
            "</body>", "<script>alert(1)</script></body>"
        ),
    )

    with pytest.raises(ReportHtmlSafetyError, match="不在白名单"):
        validate_bundle(bundle_copy)


def test_event_handler_attribute_is_rejected(bundle_copy: Path) -> None:
    _rewrite_bundle(bundle_copy, lambda html: html.replace("<body>", '<body onload="x">'))

    with pytest.raises(ReportHtmlSafetyError, match="事件属性"):
        validate_bundle(bundle_copy)


def test_external_url_is_rejected(bundle_copy: Path) -> None:
    _rewrite_bundle(
        bundle_copy,
        lambda html: html.replace(
            "</body>", '<a href="https://example.com">x</a></body>'
        ),
    )

    with pytest.raises(ReportHtmlSafetyError, match="外部 URL"):
        validate_bundle(bundle_copy)


def test_tmp_path_left_after_normalization_is_rejected(bundle_copy: Path) -> None:
    _rewrite_bundle(
        bundle_copy,
        lambda html: html.replace("</body>", "<p>/tmp/evil</p></body>"),
    )

    with pytest.raises(InsightImportError, match="残留 /tmp/"):
        validate_bundle(bundle_copy)


def test_path_traversal_is_rejected(bundle_copy: Path) -> None:
    manifest_path = bundle_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content"]["path"] = "../report.html"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(InsightImportError, match="相对路径"):
        validate_bundle(bundle_copy)


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email="import-owner@example.com",
            password_hash="x",
            name="Import Owner",
            status="active",
        )
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Import WS",
            slug="import-ws",
            owner_id=user.id,
        )
        session.add_all([user, workspace])
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


async def test_import_is_idempotent_and_replace_only_updates_metadata(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    bundle = validate_bundle(BUNDLE_DIR)

    async with session_factory() as session:
        first = await import_bundle(
            session, bundle, workspace_slug="import-ws", actor_email="import-owner@example.com"
        )
        await session.commit()
        assert first.status == "imported"

        second = await import_bundle(session, bundle, workspace_slug="import-ws")
        await session.commit()
        assert second.status == "already_imported"
        assert second.report_id == first.report_id

        renamed = dataclasses.replace(
            bundle,
            manifest=bundle.manifest.model_copy(update={"title": "新的标题"}),
        )
        without_replace = await import_bundle(
            session, renamed, workspace_slug="import-ws"
        )
        await session.commit()
        assert without_replace.status == "already_imported"

        replaced = await import_bundle(
            session, renamed, workspace_slug="import-ws", replace=True
        )
        await session.commit()
        assert replaced.status == "replaced"
        assert replaced.report_id == first.report_id

    async with session_factory() as session:
        from data_intelligence_hub.models.insight_report import InsightReport

        stored = await session.get(InsightReport, first.report_id)
        assert stored is not None
        assert stored.title == "新的标题"
        assert stored.summary == bundle.manifest.summary
        assert stored.created_by is not None


async def test_import_rejects_same_version_with_different_content(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    bundle = validate_bundle(BUNDLE_DIR)
    async with session_factory() as session:
        await import_bundle(session, bundle, workspace_slug="import-ws")
        await session.commit()

        changed = dataclasses.replace(bundle, content_sha256="0" * 64)
        with pytest.raises(InsightImportError, match="正文变更必须换 version"):
            await import_bundle(session, changed, workspace_slug="import-ws")
        with pytest.raises(InsightImportError, match="正文变更必须换 version"):
            await import_bundle(
                session, changed, workspace_slug="import-ws", replace=True
            )


async def test_import_rejects_unknown_workspace(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    bundle = validate_bundle(BUNDLE_DIR)
    async with session_factory() as session:
        with pytest.raises(InsightImportError, match="工作区不存在"):
            await import_bundle(session, bundle, workspace_slug="missing-ws")
