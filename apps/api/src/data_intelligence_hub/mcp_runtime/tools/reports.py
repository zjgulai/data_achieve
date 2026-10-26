"""MCP 的报告生成入口。

本模块复用 B4 的合同、渲染器与产物服务。
合同来自调用方。运行本身不足以填满合同。
缺少输入时明确报错，不编造字段。

``create_report`` 必须走 :func:`report_builder.build_contract`。
这样模板注册表、夹具等级上限与 claim 状态上限只校验一次。
本模块不自己 ``model_validate`` 合同。

仓储只 flush。本模块在服务层提交事务。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.repositories.report_artifacts import create_artifact
from data_intelligence_hub.schemas.report_contract import (
    SCHEMA_VERSION,
    Artifact,
    ReportContract,
    contract_sha256,
)
from data_intelligence_hub.services import report_builder, report_templates
from data_intelligence_hub.services.report_artifacts import (
    build_artifact,
    contract_input_ids,
    contract_payload,
    data_sha256,
    render_sha256,
    verify_artifact,
)
from data_intelligence_hub.services.report_renderers import (
    render_report_html,
    render_report_html_unhashed,
    render_sop_html,
    render_sop_html_unhashed,
)

# build_contract 需要的合同组。缺一个就拒绝生成。
REQUIRED_CONTRACT_GROUPS: tuple[str, ...] = (
    "identity",
    "decision",
    "gates",
    "coverage",
    "metrics",
    "claims",
    "evidences",
    "run_ledger",
    "limits",
    "unknowns",
)

# build_contract 还需要生成时间。它与合同组一样必须由调用方给出。
REQUIRED_CONTRACT_FIELDS: tuple[str, ...] = (*REQUIRED_CONTRACT_GROUPS, "generated_at")


def _missing_contract_error(missing: list[str] | None = None) -> ValueError:
    """构造缺输入的明确错误。列出缺的字段名。"""
    fields = "、".join(missing or REQUIRED_CONTRACT_FIELDS)
    return ValueError(
        f"report_contract_incomplete: 缺少 {fields}。"
        "运行数据不能填补这些字段，请传入完整 contract。"
    )


def _registered_template(template_id: str) -> report_templates.ReportTemplate:
    """取 B5 模板注册项。未登记时返回明确错误。"""
    try:
        return report_templates.get_template(template_id)
    except KeyError:
        raise ValueError(f"template_not_registered: {template_id}") from None


def _contract_build_inputs(contract: Mapping[str, object]) -> dict[str, Any]:
    """从调用方合同取出 build_contract 需要的输入。

    本函数只检查缺项。类型与结构交给 build_contract 的 Pydantic 校验。
    """
    missing = [name for name in REQUIRED_CONTRACT_FIELDS if name not in contract]
    if missing:
        raise _missing_contract_error(missing)
    return {
        "claims": contract["claims"],
        "evidences": contract["evidences"],
        "metrics": contract["metrics"],
        "coverage": contract["coverage"],
        "identity": contract["identity"],
        "decision": contract["decision"],
        "generated_at": contract["generated_at"],
        "gates": contract["gates"],
        "run_ledger": contract["run_ledger"],
        "limits": contract["limits"],
        "unknowns": contract["unknowns"],
        "artifact": contract.get("artifact"),
    }


def _render_contract(parsed: ReportContract) -> ReportContract:
    """返回渲染用合同。

    合同哈希先算好。两个页面哈希留空，由渲染器写入占位符。
    这样页脚展示的是真实合同哈希，不是调用方给的值。
    """
    artifact = Artifact(
        report_html_sha256="",
        sop_html_sha256="",
        contract_sha256=contract_sha256(parsed),
    )
    return parsed.model_copy(update={"artifact": artifact})


def _final_contract(parsed: ReportContract, report_digest: str, sop_digest: str) -> ReportContract:
    """写入三个产物哈希。

    合同哈希排除 artifact 组，所以先算哈希再填值不会循环。
    """
    artifact = Artifact(
        report_html_sha256=report_digest,
        sop_html_sha256=sop_digest,
        contract_sha256=contract_sha256(parsed),
    )
    return parsed.model_copy(update={"artifact": artifact})


async def create_report(
    run_id: uuid.UUID,
    template_id: str,
    contract: dict[str, object] | None = None,
    *,
    project_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """为一次运行生成报告合同与产物。

    ``template_id`` 必须已登记在 B5 模板注册表。
    合同必须覆盖本次运行，且通过 ``build_contract`` 的全部校验。
    ``project_id`` 非空时只允许该项目的运行。
    """
    _registered_template(template_id)

    if contract is None:
        raise _missing_contract_error()
    if not isinstance(contract, Mapping):
        raise ValueError("report_contract_invalid: contract 必须是对象")

    declared_template = contract.get("template_id")
    if declared_template is not None and declared_template != template_id:
        raise ValueError("template_id_mismatch")

    declared_schema = contract.get("schema_version")
    if declared_schema is not None and declared_schema != SCHEMA_VERSION:
        raise ValueError(f"report_contract_invalid: schema_version 必须是 {SCHEMA_VERSION}")

    build_inputs = _contract_build_inputs(contract)

    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or (project_id is not None and run.project_id != project_id):
            raise ValueError("run_not_found")

        try:
            parsed = report_builder.build_contract(
                template_id,
                run=run,
                **build_inputs,
            )
        except report_builder.ReportContractBuildError as exc:
            raise ValueError(f"report_contract_invalid: {exc}") from exc

        run_ids, evidence_ids = contract_input_ids(parsed)
        if str(run_id) not in run_ids:
            raise ValueError("report_run_not_in_contract")

        data_hash = data_sha256(run_ids, evidence_ids)
        render_contract = _render_contract(parsed)
        report_unhashed = render_report_html_unhashed(render_contract, data_hash=data_hash)
        sop_unhashed = render_sop_html_unhashed(render_contract, data_hash=data_hash)
        report_digest = render_sha256(report_unhashed)
        sop_digest = render_sha256(sop_unhashed)
        report_html = render_report_html(
            render_contract,
            report_hash=report_digest,
            sop_hash=sop_digest,
            data_hash=data_hash,
        )
        sop_html = render_sop_html(
            render_contract,
            report_hash=report_digest,
            sop_hash=sop_digest,
            data_hash=data_hash,
        )

        final = _final_contract(parsed, report_digest, sop_digest)
        built = build_artifact(
            workspace_id=workspace_id if workspace_id is not None else run.workspace_id,
            project_id=project_id if project_id is not None else run.project_id,
            template_id=template_id,
            contract=final,
            report_html=report_html,
            sop_html=sop_html,
            run_id=run_id,
        )
        row = await create_artifact(
            session,
            workspace_id=built.workspace_id,
            project_id=built.project_id,
            template_id=built.template_id,
            contract_json=built.contract_json,
            contract_sha256=built.contract_sha256,
            data_sha256=built.data_sha256,
            report_html_sha256=built.report_html_sha256,
            sop_html_sha256=built.sop_html_sha256,
            combined_sha256=built.combined_sha256,
            run_id=built.run_id,
            version=built.version,
            report_html=built.report_html,
            sop_html=built.sop_html,
        )
        await session.commit()

    return {
        "run_id": str(run_id),
        "template_id": template_id,
        "artifact_id": str(row.id),
        "contract": contract_payload(final),
        "artifact": {
            "contract_sha256": built.contract_sha256,
            "data_sha256": built.data_sha256,
            "report_html_sha256": built.report_html_sha256,
            "sop_html_sha256": built.sop_html_sha256,
            "combined_sha256": built.combined_sha256,
        },
        "verification": verify_artifact(built, final, report_html, sop_html),
        "report_html": report_html,
        "sop_html": sop_html,
    }


__all__ = ["REQUIRED_CONTRACT_GROUPS", "create_report"]
