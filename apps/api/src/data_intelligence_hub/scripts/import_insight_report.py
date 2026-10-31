"""洞察分析报告包的校验与导入。

报告包的正文是 182 KB 的单文件 HTML，因此正文走数据库的独立正文表，
不写进 alembic 迁移，也不依赖容器的本地文件卷。

用法::

    python -m data_intelligence_hub.scripts.import_insight_report \\
      --bundle tools/insight-reports/tiktok-viral-topic/2026-10-31 \\
      --workspace-slug <workspace-slug> \\
      --dry-run

去掉 ``--dry-run`` 后写库。导入器不是 HTTP 端点，不经过 API 鉴权；它用
数据库连接和工作区 slug，属于一次性运维动作。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.insight_report import (
    InsightReport,
    InsightReportContent,
)
from data_intelligence_hub.repositories.insight_reports import (
    get_content_by_report_id,
    get_report_by_scope,
)
from data_intelligence_hub.repositories.users import get_user_by_email
from data_intelligence_hub.repositories.workspaces import get_workspace_by_slug
from data_intelligence_hub.schemas.insight_report import (
    InsightReportManifest,
)
from data_intelligence_hub.services.insight_report_catalog import (
    is_registered_analysis_type,
)

# 报告里只有两段内联脚本：目录高亮与移动端表格卡片化。白名单写在代码里，
# manifest 不能自己授权脚本。
ALLOWED_SCRIPT_SHA256: frozenset[str] = frozenset(
    {
        "d63f12e445a8317edc925644d31dca93c3f4107b06dc74d5fed67ce62281b56f",
        "43158db65a7984b9ac2044505ef49ae1565e1ffb13b0271acd987d093950b4c6",
    }
)

FORBIDDEN_TAGS = frozenset({"iframe", "object", "embed", "form", "base"})
URL_ATTRIBUTES = frozenset(
    {
        "action",
        "background",
        "cite",
        "data",
        "formaction",
        "href",
        "poster",
        "src",
        "srcset",
        "xlink:href",
    }
)
CSS_EXTERNAL_PATTERN = re.compile(
    r"url\(\s*['\"]?\s*(?:https?:)?//|url\(\s*['\"]?\s*http",
    re.IGNORECASE,
)
EXTERNAL_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
DOCTYPE_PATTERN = re.compile(r"^\s*<!doctype\s+html\s*>", re.IGNORECASE)


class InsightImportError(Exception):
    """导入校验或写库失败。CLI 以非零退出码结束。"""


class ReportHtmlSafetyError(InsightImportError):
    """HTML 未通过安全校验。"""


class _ReportHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.script_hashes: list[str] = []
        self.errors: list[str] = []
        self._script_chunks: list[str] | None = None
        self._style_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in FORBIDDEN_TAGS:
            self.errors.append(f"禁止的标签 <{tag}>")
        if tag == "meta":
            for name, value in attrs:
                if name.lower() == "http-equiv" and (value or "").lower() == "refresh":
                    self.errors.append("禁止 <meta http-equiv=\"refresh\">")
        if tag == "script":
            if any(name.lower() == "src" for name, _ in attrs):
                self.errors.append("禁止外链脚本 <script src=...>")
            self._script_chunks = []
        if tag == "style":
            self._style_chunks = []
        for name, value in attrs:
            attribute = name.lower()
            if attribute.startswith("on"):
                self.errors.append(f"禁止事件属性 {attribute}")
            if attribute in URL_ATTRIBUTES:
                self._check_url(attribute, value or "")
            if attribute == "style":
                self._check_css(value or "")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._script_chunks is not None:
            self._script_chunks.append(data)
        if self._style_chunks is not None:
            self._style_chunks.append(data)
            self._check_css(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script" and self._script_chunks is not None:
            script = "".join(self._script_chunks)
            self._script_chunks = None
            sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()
            self.script_hashes.append(sha256)
            if sha256 not in ALLOWED_SCRIPT_SHA256:
                self.errors.append(f"内联脚本不在白名单: {sha256}")
        if tag == "style" and self._style_chunks is not None:
            self._style_chunks = None

    def _check_url(self, attribute: str, value: str) -> None:
        url = value.strip()
        lowered = url.lower()
        if not url:
            return
        if lowered.startswith("#"):
            return
        if lowered.startswith("data:image/"):
            return
        if lowered.startswith("data:"):
            self.errors.append(f"{attribute} 的 data: 类型不受支持: {url[:40]}")
            return
        if lowered.startswith("javascript:") or lowered.startswith("vbscript:"):
            self.errors.append(f"{attribute} 使用了 javascript/vbscript URL")
            return
        if lowered.startswith("http://") or lowered.startswith("https://"):
            self.errors.append(f"{attribute} 使用了外部 URL: {url[:60]}")
            return
        if lowered.startswith("//"):
            self.errors.append(f"{attribute} 使用了协议相对 URL: {url[:60]}")
            return
        if attribute == "srcset" and any(
            part.strip().lower().startswith(("http://", "https://", "//"))
            for part in url.split(",")
        ):
            self.errors.append("srcset 包含外部 URL")

    def _check_css(self, css: str) -> None:
        if "@import" in css.lower():
            self.errors.append("CSS 禁止 @import")
        if CSS_EXTERNAL_PATTERN.search(css):
            self.errors.append("CSS 禁止外部 url()")


@dataclass(frozen=True)
class ValidatedReportBundle:
    bundle_dir: Path
    manifest: InsightReportManifest
    html: str
    source_bytes: int
    source_sha256: str
    content_bytes: int
    content_sha256: str


def load_manifest(bundle_dir: Path) -> InsightReportManifest:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        raise InsightImportError(f"缺少 manifest.json: {manifest_path}")
    try:
        return InsightReportManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except ValidationError as exc:
        raise InsightImportError(f"manifest 校验失败: {exc}") from exc


def _resolve_content_path(bundle_dir: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise InsightImportError(f"正文路径必须是包内相对路径: {relative_path}")
    root = bundle_dir.resolve()
    content_path = (root / relative_path).resolve()
    if not content_path.is_relative_to(root):
        raise InsightImportError(f"正文路径越界: {relative_path}")
    if not content_path.is_file():
        raise InsightImportError(f"正文文件不存在: {content_path}")
    return content_path


def _normalize_html(html: str, manifest: InsightReportManifest) -> str:
    normalized = html
    for rule in manifest.content.normalize:
        if set(rule) != {"find", "replace"}:
            raise InsightImportError(
                "normalize 规则只能包含 find 与 replace 两个字面量字段"
            )
        find = rule["find"]
        replace = rule["replace"]
        if not find:
            raise InsightImportError("normalize 的 find 不能为空")
        normalized = normalized.replace(find, replace)
    if "/tmp/" in normalized:
        raise InsightImportError("归一化后仍残留 /tmp/ 路径")
    return normalized


def _check_html_safety(html: str) -> None:
    parser = _ReportHtmlParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # HTMLParser 的异常类型不稳定，统一按校验失败处理
        raise ReportHtmlSafetyError(f"HTML 解析失败: {exc}") from exc
    if parser.errors:
        raise ReportHtmlSafetyError("; ".join(parser.errors))
    if EXTERNAL_URL_PATTERN.search(html):
        raise ReportHtmlSafetyError("正文包含 http:// 或 https:// 外部引用")


def validate_bundle(bundle_dir: Path) -> ValidatedReportBundle:
    bundle_dir = bundle_dir.resolve()
    manifest = load_manifest(bundle_dir)
    if not is_registered_analysis_type(manifest.analysis_type):
        raise InsightImportError(
            f"未注册的分析类型: {manifest.analysis_type}"
        )
    if manifest.content.format != "html":
        raise InsightImportError("v1 只支持 html 正文")

    content_path = _resolve_content_path(bundle_dir, manifest.content.path)
    source = content_path.read_bytes()
    source_bytes = len(source)
    source_sha256 = hashlib.sha256(source).hexdigest()
    if source_bytes != manifest.content.source_bytes:
        raise InsightImportError(
            f"源文件字节数不一致: 期望 {manifest.content.source_bytes}，实际 {source_bytes}"
        )
    if source_sha256 != manifest.content.source_sha256:
        raise InsightImportError(
            f"源文件 SHA-256 不一致: 期望 {manifest.content.source_sha256}，"
            f"实际 {source_sha256}"
        )
    try:
        html = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InsightImportError("正文不是有效的 UTF-8") from exc

    for token in ("<!DOCTYPE html>", "<html", "<head", "<body"):
        if token.lower() not in html.lower():
            raise InsightImportError(f"正文缺少 {token}")
    if not DOCTYPE_PATTERN.match(html):
        raise InsightImportError("正文必须以 <!DOCTYPE html> 开头")

    normalized = _normalize_html(html, manifest)
    content_bytes = len(normalized.encode("utf-8"))
    content_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if content_bytes != manifest.content.content_bytes:
        raise InsightImportError(
            f"归一化后字节数不一致: 期望 {manifest.content.content_bytes}，"
            f"实际 {content_bytes}"
        )
    if content_sha256 != manifest.content.content_sha256:
        raise InsightImportError(
            f"归一化后 SHA-256 不一致: 期望 {manifest.content.content_sha256}，"
            f"实际 {content_sha256}"
        )

    _check_html_safety(normalized)
    return ValidatedReportBundle(
        bundle_dir=bundle_dir,
        manifest=manifest,
        html=normalized,
        source_bytes=source_bytes,
        source_sha256=source_sha256,
        content_bytes=content_bytes,
        content_sha256=content_sha256,
    )


@dataclass(frozen=True)
class ImportOutcome:
    status: str
    report_id: uuid.UUID
    analysis_type: str
    version: str
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "report_id": str(self.report_id),
            "analysis_type": self.analysis_type,
            "version": self.version,
            "content_sha256": self.content_sha256,
        }


async def import_bundle(
    session: AsyncSession,
    bundle: ValidatedReportBundle,
    *,
    workspace_slug: str,
    actor_email: str | None = None,
    replace: bool = False,
) -> ImportOutcome:
    workspace = await get_workspace_by_slug(session, workspace_slug)
    if workspace is None:
        raise InsightImportError(f"工作区不存在: {workspace_slug}")

    actor_id: uuid.UUID | None = None
    if actor_email:
        actor = await get_user_by_email(session, actor_email)
        if actor is None:
            raise InsightImportError(f"操作人不存在: {actor_email}")
        actor_id = actor.id

    manifest = bundle.manifest
    existing = await get_report_by_scope(
        session,
        workspace.id,
        manifest.analysis_type,
        manifest.version,
    )
    imported_at = datetime.now(UTC)

    if existing is not None:
        existing_content = await get_content_by_report_id(session, existing.id)
        same_content = (
            existing_content is not None
            and existing_content.content_sha256 == bundle.content_sha256
        )
        if same_content and not replace:
            return ImportOutcome(
                status="already_imported",
                report_id=existing.id,
                analysis_type=manifest.analysis_type,
                version=manifest.version,
                content_sha256=bundle.content_sha256,
            )
        if not same_content and not replace:
            raise InsightImportError(
                "同一版本已存在且正文哈希不同；正文变更必须换 version"
            )
        if not same_content and existing_content is not None:
            raise InsightImportError(
                "--replace 只允许更新元数据；正文变更必须换 version"
            )

        existing.title = manifest.title
        existing.summary = manifest.summary
        existing.data_scope = manifest.data_scope.model_dump(
            mode="json", by_alias=True
        )
        existing.source_status = manifest.source_status
        existing.source_note = manifest.source_note
        existing.generated_at = manifest.generated_at
        if actor_id is not None:
            existing.created_by = actor_id
        if existing_content is None:
            session.add(_new_content(existing.id, bundle))
        await session.flush()
        return ImportOutcome(
            status="replaced",
            report_id=existing.id,
            analysis_type=manifest.analysis_type,
            version=manifest.version,
            content_sha256=bundle.content_sha256,
        )

    report = InsightReport(
        workspace_id=workspace.id,
        project_id=None,
        analysis_type=manifest.analysis_type,
        title=manifest.title,
        summary=manifest.summary,
        status="ready",
        version=manifest.version,
        data_scope=manifest.data_scope.model_dump(mode="json", by_alias=True),
        source_status=manifest.source_status,
        source_note=manifest.source_note,
        generated_at=manifest.generated_at,
        imported_at=imported_at,
        created_by=actor_id,
    )
    session.add(report)
    await session.flush()
    session.add(_new_content(report.id, bundle))
    await session.flush()
    return ImportOutcome(
        status="imported",
        report_id=report.id,
        analysis_type=manifest.analysis_type,
        version=manifest.version,
        content_sha256=bundle.content_sha256,
    )


def _new_content(report_id: uuid.UUID, bundle: ValidatedReportBundle) -> InsightReportContent:
    return InsightReportContent(
        report_id=report_id,
        content_format="html",
        content_html=bundle.html,
        content_sha256=bundle.content_sha256,
        content_bytes=bundle.content_bytes,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="导入一份已生成的洞察分析报告到数据库。"
    )
    parser.add_argument(
        "--bundle",
        required=True,
        type=Path,
        help="报告包目录（含 manifest.json 与 report.html）。",
    )
    parser.add_argument(
        "--workspace-slug",
        required=True,
        help="目标工作区 slug。",
    )
    parser.add_argument(
        "--actor-email",
        default=None,
        help="导入操作人邮箱，可选；只写入 created_by。",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="版本不变时更新元数据（正文哈希必须不变）。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只校验并打印摘要，不写库。",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    bundle = validate_bundle(args.bundle)
    summary = {
        "status": "dry_run" if args.dry_run else "pending",
        "workspace_slug": args.workspace_slug,
        "analysis_type": bundle.manifest.analysis_type,
        "version": bundle.manifest.version,
        "title": bundle.manifest.title,
        "source_bytes": bundle.source_bytes,
        "source_sha256": bundle.source_sha256,
        "content_bytes": bundle.content_bytes,
        "content_sha256": bundle.content_sha256,
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    async with async_session_factory() as session:
        outcome = await import_bundle(
            session,
            bundle,
            workspace_slug=args.workspace_slug,
            actor_email=args.actor_email,
            replace=args.replace,
        )
        await session.commit()

    summary.update(outcome.to_dict())
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except InsightImportError as exc:
        print(f"导入失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
