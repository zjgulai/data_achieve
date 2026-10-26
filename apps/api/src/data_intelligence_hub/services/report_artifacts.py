"""报告产物的五个哈希、组装与复核。

五个哈希的定义：

- ``contract_sha256``：规范化合同的 sha256。排除 ``generated_at``
  与 ``artifact`` 组。
- ``data_sha256``：本次报告输入 run id 与 evidence id 的 sha256。
  先排序再去重，保证集合相同则哈希相同。
- ``report_html_sha256``：决策者视图 ``report.html`` 的渲染哈希。
- ``sop_html_sha256``：执行者视图 ``sop.html`` 的渲染哈希。
- ``combined_sha256``：``sha256(report_html_sha256 + sop_html_sha256)``。

规范化入口只有一处：``schemas.report_contract.canonical_json_bytes``
与 ``schemas.report_contract.contract_sha256``。本模块直接 import 它们。
本模块不另写 ``json.dumps`` 规范化。上一版在这里自己拼 JSON，
时间输出 ``+00:00``，契约模块输出 ``Z``，同一份合同算出两个哈希。
本模块已删除 ``_json_default`` 与本地 ``contract_sha256``。

页脚自引用的不动点约定（与渲染器线共同遵守）：

1. 模板在哈希位置写 ``__REPORT_HASH__`` 或 ``__SOP_HASH__``。
2. 渲染器先输出带占位符的 HTML。
3. 对带占位符的 HTML 调用 :func:`render_sha256`。
4. 把占位符替换成第 3 步的哈希值，得到最终 HTML。
5. 复核时对最终 HTML 调用 :func:`strip_hash_placeholders`。
   它把 ``data-render-hash="<64 位十六进制>"`` 还原为 ``__RENDER_HASH__``。
   然后 :func:`render_sha256` 重新计算。

:func:`render_sha256` 内部也调用 :func:`strip_hash_placeholders`。
所以带占位符的 HTML 与最终 HTML 得到同一个哈希。三种写法
``__REPORT_HASH__``、``__SOP_HASH__``、``__RENDER_HASH__``
先归一到 ``__RENDER_HASH__``。页脚自引用不再形成循环。

本模块是纯函数层。它不读库、不联网、不调模型、不读文件系统。
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.schemas.report_contract import (
    ReportContract,
    canonical_json_bytes,
    contract_sha256,
)

# 合同可以来自 Pydantic 模型，也可以来自已落库的 JSON 对象。
ContractInput = ReportContract | Mapping[str, Any]

_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_HASH_ATTRIBUTE = re.compile(r'(data-render-hash=")([^"]*)(")')
_RENDER_HASH_PLACEHOLDER = "__RENDER_HASH__"
_RENDER_HASH_PLACEHOLDERS = frozenset(
    {"__REPORT_HASH__", "__SOP_HASH__", _RENDER_HASH_PLACEHOLDER}
)
DEFAULT_VERSION = "1.0.0"


def _normalize_digest(value: object) -> str:
    """把哈希值收敛到 64 位小写十六进制。"""
    digest = str(value).strip()
    if digest.startswith("sha256:"):
        digest = digest[len("sha256:") :]
    digest = digest.lower()
    if _HEX_DIGEST.fullmatch(digest) is None:
        raise ValueError("哈希必须是 64 位十六进制")
    return digest


def strip_hash_placeholders(html: str) -> str:
    """把最终 HTML 里的渲染哈希还原成占位符。

    只处理 ``data-render-hash="..."`` 属性。值必须是 64 位十六进制，
    或者是三种占位写法之一。其他值原样保留。

    返回的字符串用 ``__RENDER_HASH__`` 作唯一占位符。
    这样两个页面的 HTML 都能走同一条复核路径。
    """
    def _restore(match: re.Match[str]) -> str:
        value = match.group(2)
        if value in _RENDER_HASH_PLACEHOLDERS:
            return f"{match.group(1)}{_RENDER_HASH_PLACEHOLDER}{match.group(3)}"
        if _HEX_DIGEST.fullmatch(value.lower()) is not None:
            return f"{match.group(1)}{_RENDER_HASH_PLACEHOLDER}{match.group(3)}"
        return match.group(0)

    return _HASH_ATTRIBUTE.sub(_restore, html)


def render_sha256(html: str | bytes) -> str:
    """计算一页 HTML 的渲染哈希。

    先归一占位符，再对 UTF-8 字节求 sha256。
    字符串与 UTF-8 字节得到同一哈希。
    归一规则见模块 docstring。
    """
    text = html.decode("utf-8") if isinstance(html, bytes) else html
    canonical = strip_hash_placeholders(text)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def combined_sha256(report_html_sha256: str, sop_html_sha256: str) -> str:
    """计算两页渲染哈希的拼接哈希。

    输入必须是 64 位十六进制。先统一成小写再去拼接。
    """
    report_digest = _normalize_digest(report_html_sha256)
    sop_digest = _normalize_digest(sop_html_sha256)
    return hashlib.sha256((report_digest + sop_digest).encode("ascii")).hexdigest()


def _contract_mapping(contract: ContractInput) -> dict[str, Any]:
    """把合同转成普通映射。本函数不修改调用方对象。"""
    if isinstance(contract, BaseModel):
        return contract.model_dump(mode="json")
    if isinstance(contract, Mapping):
        return dict(contract)
    raise TypeError("合同必须是 Mapping 或 Pydantic 模型")


def contract_payload(contract: ContractInput) -> dict[str, Any]:
    """返回规范化后的完整合同 JSON 对象。

    内容来自唯一规范化入口 :func:`canonical_json_bytes`。
    输入先包一层 ``{"contract": ...}``。排除规则只看顶层键，
    所以 ``generated_at`` 与 ``artifact`` 会保留在存下来的合同里。
    时间写 ``Z``，Decimal 写字符串，键排序。
    重新计算 :func:`contract_sha256` 时，排除规则仍作用于合同的顶层键。
    同一份合同再次规范化得到同样的字节。
    """
    wrapped: dict[str, Any] = {"contract": contract}
    envelope = json.loads(canonical_json_bytes(wrapped).decode("utf-8"))
    if not isinstance(envelope, dict):
        raise TypeError("合同规范化结果必须是 JSON 对象")
    payload = envelope.get("contract")
    if not isinstance(payload, dict):
        raise TypeError("合同规范化结果必须是 JSON 对象")
    return {str(key): value for key, value in payload.items()}


def _normalize_ids(values: Iterable[uuid.UUID | str]) -> list[str]:
    """转字符串、去重、排序。排序保证同一集合得到同一哈希。"""
    return sorted({str(value) for value in values})


def data_sha256(
    run_ids: Iterable[uuid.UUID | str],
    evidence_ids: Iterable[uuid.UUID | str],
) -> str:
    """计算输入数据 id 集合的 sha256。

    先排序再去重。同一集合换顺序得到同一哈希。
    换一个 id 会得到不同哈希。规范化走同一入口。
    """
    payload = {
        "evidence_ids": _normalize_ids(evidence_ids),
        "run_ids": _normalize_ids(run_ids),
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def contract_input_ids(contract: ContractInput) -> tuple[list[str], list[str]]:
    """从合同读出 run id 与 evidence id。

    ``run_ledger[].run_id`` 是 run 来源。
    ``evidences[].evidence_id`` 是证据来源。
    """
    payload = _contract_mapping(contract)
    run_ids: list[str] = []
    for entry in payload.get("run_ledger") or []:
        if isinstance(entry, Mapping) and entry.get("run_id") is not None:
            run_ids.append(str(entry["run_id"]))
    evidence_ids: list[str] = []
    for entry in payload.get("evidences") or []:
        if isinstance(entry, Mapping) and entry.get("evidence_id") is not None:
            evidence_ids.append(str(entry["evidence_id"]))
    return _normalize_ids(run_ids), _normalize_ids(evidence_ids)


def _as_text(html: str | bytes) -> str:
    """把 HTML 统一成字符串。"""
    return html.decode("utf-8") if isinstance(html, bytes) else html


def _resolve_input_ids(
    contract: ContractInput,
    *,
    run_id: uuid.UUID | str | None,
    run_ids: Iterable[uuid.UUID | str] | None = None,
    evidence_ids: Iterable[uuid.UUID | str] | None = None,
) -> tuple[Iterable[uuid.UUID | str], Iterable[uuid.UUID | str]]:
    """解析本次报告的输入 id 集合。build 与 verify 共用本入口。

    显式传入的集合优先。未传时从合同读取；合同的 ``run_ledger``
    为空时回退到 ``run_id``（verify 用记录行的 ``artifact.run_id``）。
    合同账本非空时不做回退，行为与只认合同的老路径一致。

    两条被否决的替代方案：

    1. 把输入 id 集合持久化成新列。需要数据库迁移，
       SCHEMA_HEAD 冻结在 202610220059，本批不动表结构。
    2. 拒绝空 ``run_ledger``。schema 允许 ``evidences`` 与
       ``run_ledger`` 为空；一刀切拒绝会把可渲染的合同变成失败。
    """
    contract_run_ids, contract_evidence_ids = contract_input_ids(contract)
    if run_ids is None:
        run_ids = contract_run_ids or ([run_id] if run_id is not None else [])
    if evidence_ids is None:
        evidence_ids = contract_evidence_ids
    return run_ids, evidence_ids


def build_artifact(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    template_id: str,
    contract: ContractInput,
    report_html: str | bytes,
    sop_html: str | bytes,
    run_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    run_ids: Iterable[uuid.UUID | str] | None = None,
    evidence_ids: Iterable[uuid.UUID | str] | None = None,
    version: str = DEFAULT_VERSION,
) -> ReportArtifact:
    """组装一行报告产物。本函数不写库、不写文件。

    两个页面分别求渲染哈希。组合哈希由两个页面哈希拼接后再求 sha256。
    输入 id 集合走 :func:`_resolve_input_ids`：显式集合优先，
    否则从合同读取，合同没有 run_ledger 时用 ``run_id`` 补。

    ``report_html`` 与 ``sop_html`` 传入最终 HTML。
    最终 HTML 的哈希位置已填好哈希值。
    """
    resolved_run_ids, resolved_evidence_ids = _resolve_input_ids(
        contract,
        run_id=run_id,
        run_ids=run_ids,
        evidence_ids=evidence_ids,
    )
    report_digest = render_sha256(report_html)
    sop_digest = render_sha256(sop_html)
    return ReportArtifact(
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        report_id=report_id,
        template_id=template_id,
        version=version,
        contract_json=contract_payload(contract),
        contract_sha256=contract_sha256(contract),
        data_sha256=data_sha256(resolved_run_ids, resolved_evidence_ids),
        report_html_sha256=report_digest,
        sop_html_sha256=sop_digest,
        combined_sha256=combined_sha256(report_digest, sop_digest),
        report_html=_as_text(report_html),
        sop_html=_as_text(sop_html),
    )


def verify_artifact(
    artifact: ReportArtifact,
    contract: ContractInput,
    report_html: str | bytes,
    sop_html: str | bytes,
    *,
    run_ids: Iterable[uuid.UUID | str] | None = None,
    evidence_ids: Iterable[uuid.UUID | str] | None = None,
) -> list[str]:
    """重算五个哈希并比对。

    返回不一致项的中文说明。全部一致时返回空列表。
    数据哈希的 id 集合与 build 走同一入口
    :func:`_resolve_input_ids`：显式集合优先，否则从合同读取，
    合同没有 run_ledger 时回退到记录行的 ``artifact.run_id``。
    旧的四参数位置调用完全兼容。

    组合哈希只用记录里的两个页面哈希复算。
    所以只改一页 HTML 时，只有该页的渲染哈希报错。
    """
    mismatches: list[str] = []
    if artifact.contract_sha256 != contract_sha256(contract):
        mismatches.append("contract_sha256 不一致：合同内容与记录不符")
    resolved_run_ids, resolved_evidence_ids = _resolve_input_ids(
        contract,
        run_id=artifact.run_id,
        run_ids=run_ids,
        evidence_ids=evidence_ids,
    )
    if artifact.data_sha256 != data_sha256(resolved_run_ids, resolved_evidence_ids):
        mismatches.append("data_sha256 不一致：输入 run 或证据集合与记录不符")
    # 先把最终 HTML 的哈希值还原成占位符，再重算。
    canonical_report = strip_hash_placeholders(_as_text(report_html))
    canonical_sop = strip_hash_placeholders(_as_text(sop_html))
    if artifact.report_html_sha256 != render_sha256(canonical_report):
        mismatches.append("report_html_sha256 不一致：报告页 HTML 与记录不符")
    if artifact.sop_html_sha256 != render_sha256(canonical_sop):
        mismatches.append("sop_html_sha256 不一致：执行页 HTML 与记录不符")
    try:
        recorded_combined = combined_sha256(
            artifact.report_html_sha256,
            artifact.sop_html_sha256,
        )
    except ValueError:
        mismatches.append("combined_sha256 不一致：两页哈希不是 64 位十六进制")
    else:
        if artifact.combined_sha256 != recorded_combined:
            mismatches.append("combined_sha256 不一致：两页哈希的组合与记录不符")
    return mismatches


__all__ = [
    "DEFAULT_VERSION",
    "build_artifact",
    "combined_sha256",
    "contract_input_ids",
    "contract_payload",
    "contract_sha256",
    "data_sha256",
    "render_sha256",
    "strip_hash_placeholders",
    "verify_artifact",
]
