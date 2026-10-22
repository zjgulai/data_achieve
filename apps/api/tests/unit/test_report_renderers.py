"""B4-03：两个报告渲染器。

本套测试覆盖以下判据：

1. 两个渲染器都产出完整 HTML。
2. 改一个 metric 数字，两页同步变。
3. 最低证据等级与门禁状态出现在 report.html 首屏。
4. 合同文本里的 ``<script>`` 被转义。
5. 同一输入连调两次输出相同。
6. 渲染器不发起 I/O，也不 import 时钟、数据库或 HTTP 客户端。
7. 两步哈希协议与产物线的 ``strip_hash_placeholders`` 约定一致。
8. coverage 使用 ``{"cells": [...]}`` 对象形状。

渲染器只接收合同与调用方给的哈希。
签名里不得出现 session、http client、llm 或 now。
"""

from __future__ import annotations

import builtins
import copy
import inspect
import socket
import urllib.request
from collections.abc import Mapping
from typing import Any

import pytest

import data_intelligence_hub.services.report_renderers as renderers
from data_intelligence_hub.schemas.report_contract import ReportContract, canonical_json_bytes
from data_intelligence_hub.services.report_artifacts import render_sha256
from data_intelligence_hub.services.report_renderers import (
    REPORT_HASH_PLACEHOLDER,
    SOP_HASH_PLACEHOLDER,
    render_report_html,
    render_report_html_unhashed,
    render_sop_html,
    render_sop_html_unhashed,
)

_CONTRACT: dict[str, Any] = {
    "schema_version": "1.0.0",
    "template_id": "t1_voc",
    "generated_at": "2026-10-21T10:00:00+08:00",
    "identity": {
        "task_id": "00000000-0000-0000-0000-000000000001",
        "brand": "Momcozy",
        "category": "maternal",
        "competitors": ["Medela"],
        "markets": ["US"],
        "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
    },
    "decision": {
        "decision_question": "用户为什么觉得支撑不足？",
        "answer": "轻薄是资产，但支撑兑现依赖 Fit。",
        "protect": ["轻薄"],
        "resolve": ["支撑与 Fit"],
        "prove": ["exact S 证据"],
    },
    "gates": [
        {
            "gate_id": "G0",
            "status": "pass",
            "owner": "00000000-0000-0000-0000-000000000002",
            "decided_at": "2026-10-20T09:00:00+08:00",
            "note": "范围已批准。",
        },
        {
            "gate_id": "G7",
            "status": "pending",
            "owner": None,
            "decided_at": None,
            "note": "等待双盲校准。",
        },
    ],
    "coverage": {
        "cells": [
            {
                "source_tool_id": "amazon_reviews",
                "market": "US",
                "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
                "record_count": 68,
                "frame_member_count": 70,
                "status": "success",
            },
            {
                "source_tool_id": "reddit_search",
                "market": "US",
                "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
                "record_count": 0,
                "frame_member_count": 0,
                "status": "empty",
            },
        ]
    },
    "metrics": [
        {
            "metric_id": "m1",
            "label": "舒适正向记录",
            "numerator": 4321,
            "denominator": 68,
            "count_type": "canonical_record",
            "frame": "自然样本",
            "as_of": "2026-03-01",
            "note": "不是发生率。",
        },
        {
            "metric_id": "m2",
            "label": "反证覆盖",
            "numerator": 12,
            "denominator": 12,
            "count_type": "annotation",
            "frame": "编码语料",
            "as_of": "2026-03-01",
        },
    ],
    "claims": [
        {
            "claim_id": "c1",
            "text": "轻薄舒适是真实资产 <script>alert(1)</script>",
            "claim_status": "directional",
            "evidence_grade": "L3_live_single",
            "scope": {
                "market": "US",
                "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
                "sample_n": 68,
            },
            "counterevidence_text": "未发现反证。",
            "owner": "00000000-0000-0000-0000-000000000003",
            "evidence_ids": ["e1", "e2"],
        }
    ],
    "evidences": [
        {
            "evidence_id": "e1",
            "claim_id": "c1",
            "role": "support",
            "source_tool_id": "amazon_reviews",
            "url": "https://example.com/review/1",
            "excerpt": "很轻薄。",
            "captured_at": "2026-02-01T10:00:00+08:00",
            "market": "US",
            "locale": "en-US",
            "evidence_grade": "L3_live_single",
        },
        {
            "evidence_id": "e2",
            "claim_id": "c1",
            "role": "counter",
            "source_tool_id": "reddit_search",
            "url": "javascript:alert(1)",
            "excerpt": "<img src=x onerror=alert(1)>",
            "captured_at": "2026-02-02T10:00:00+08:00",
            "market": "US",
            "locale": "en-US",
            "evidence_grade": "L3_live_single",
        },
    ],
    "run_ledger": [
        {
            "run_id": "00000000-0000-0000-0000-000000000004",
            "tool_id": "amazon_reviews",
            "endpoint_type": "reviews",
            "actor_id": None,
            "unit": "call",
            "quantity": 1,
            "unit_price": "0.100000",
            "total_cost_usd": "0.100000",
            "evidence_grade": "L3_live_single",
            "started_at": "2026-02-01T09:00:00+08:00",
            "finished_at": "2026-02-01T09:01:00+08:00",
            "outcome": "success",
        }
    ],
    "limits": ["不能推断发生率。"],
    "unknowns": ["缺 exact S 证据。"],
    # 合同 schema 的 artifact 只有三个哈希。data_sha256 不是合同字段。
    "artifact": {
        "contract_sha256": "contract-hash",
        "report_html_sha256": "artifact-report-hash",
        "sop_html_sha256": "artifact-sop-hash",
    },
}


def _contract() -> dict[str, Any]:
    """每次返回独立副本。用例只改需要变化的字段。"""
    return copy.deepcopy(_CONTRACT)


def test_both_renderers_return_complete_html() -> None:
    contract = _contract()
    report = render_report_html(contract)
    sop = render_sop_html(contract)
    for document in (report, sop):
        assert document
        assert "<html" in document
        assert "</html>" in document
        assert "<style>" in document


def test_one_metric_change_updates_both_pages() -> None:
    """验收判据：改一个数字，两页同步变。"""
    original = _contract()
    changed = copy.deepcopy(original)
    changed["metrics"][0]["numerator"] = 8765

    report_before = render_report_html(original)
    sop_before = render_sop_html(original)
    report_after = render_report_html(changed)
    sop_after = render_sop_html(changed)

    assert "4321" in report_before
    assert "4321" in sop_before
    assert "8765" in report_after
    assert "8765" in sop_after
    assert "4321" not in report_after
    assert "4321" not in sop_after


def test_lowest_grade_and_gate_status_are_in_first_screen() -> None:
    report = render_report_html(_contract())
    first_screen = report.split("</section>", 1)[0]
    assert "最低证据等级" in first_screen
    assert "L3_live_single" in first_screen
    assert "门禁状态" in first_screen
    assert "pending" in first_screen


def test_lowest_grade_uses_all_run_grades() -> None:
    """报告引用多次 run。任一 run 的等级都参与最低值比较。"""
    contract = _contract()
    contract["claims"][0]["evidence_grade"] = "L4_authorized_live"
    for evidence in contract["evidences"]:
        evidence["evidence_grade"] = "L4_authorized_live"
    contract["run_ledger"][0]["evidence_grade"] = "L2_fixture_local"
    first_screen = render_report_html(contract).split("</section>", 1)[0]
    assert "L2_fixture_local" in first_screen


def test_coverage_object_shape_renders_cells() -> None:
    """合同 coverage 是 {"cells": [...]} 对象。"""
    contract = _contract()
    assert isinstance(contract["coverage"], dict)
    sop = render_sop_html(contract)
    assert "2 个覆盖单元" in sop
    assert "amazon_reviews" in sop
    assert "reddit_search" in sop
    assert ">68<" in sop
    assert ">70<" in sop
    assert "有结果" in sop
    assert "空结果" in sop


def test_coverage_reads_cells_key() -> None:
    """渲染器只读 coverage.cells。少一个单元，覆盖表就少一行。"""
    contract = _contract()
    contract["coverage"] = {"cells": contract["coverage"]["cells"][:1]}
    sop = render_sop_html(contract)
    assert "1 个覆盖单元" in sop
    assert "amazon_reviews" in sop
    assert "reddit_search" not in sop


def test_two_step_protocol_report() -> None:
    contract = _contract()
    unhashed = render_report_html_unhashed(contract)
    assert f'data-render-hash="{REPORT_HASH_PLACEHOLDER}"' in unhashed
    assert f'data-render-hash="{SOP_HASH_PLACEHOLDER}"' in unhashed

    hashed = render_report_html(contract, report_hash="abc")
    assert 'data-render-hash="abc"' in hashed
    assert REPORT_HASH_PLACEHOLDER not in hashed
    assert SOP_HASH_PLACEHOLDER not in hashed
    assert "未计算" in hashed


def test_two_step_protocol_sop() -> None:
    contract = _contract()
    unhashed = render_sop_html_unhashed(contract)
    assert f'data-render-hash="{SOP_HASH_PLACEHOLDER}"' in unhashed
    assert f'data-render-hash="{REPORT_HASH_PLACEHOLDER}"' in unhashed

    hashed = render_sop_html(contract, sop_hash="xyz")
    assert 'data-render-hash="xyz"' in hashed
    assert REPORT_HASH_PLACEHOLDER not in hashed
    assert SOP_HASH_PLACEHOLDER not in hashed
    assert "未计算" in hashed


def test_two_step_hash_matches_artifacts_render_sha256() -> None:
    """占位符形态与回填形态必须算出同一个渲染哈希。"""
    contract = _contract()
    data_hash = "data-digest"
    report_unhashed = render_report_html_unhashed(contract, data_hash=data_hash)
    sop_unhashed = render_sop_html_unhashed(contract, data_hash=data_hash)
    report_digest = render_sha256(report_unhashed)
    sop_digest = render_sha256(sop_unhashed)

    report = render_report_html(
        contract,
        report_hash=report_digest,
        sop_hash=sop_digest,
        data_hash=data_hash,
    )
    sop = render_sop_html(
        contract,
        report_hash=report_digest,
        sop_hash=sop_digest,
        data_hash=data_hash,
    )

    assert render_sha256(report) == report_digest
    assert render_sha256(sop) == sop_digest


def test_missing_hash_shows_uncomputed_without_cross_page_fallback() -> None:
    """V6：缺一页哈希时显示「未计算」，不得借用另一页的值。"""
    contract = _contract()
    report = render_report_html(contract, report_hash="report-only")
    assert 'data-render-hash="report-only"' in report
    assert "未计算" in report
    assert "artifact-sop-hash" not in report

    sop = render_sop_html(contract, sop_hash="sop-only")
    assert 'data-render-hash="sop-only"' in sop
    assert "未计算" in sop
    assert "artifact-report-hash" not in sop


def test_both_hashes_missing_show_uncomputed() -> None:
    report = render_report_html(_contract())
    assert 'data-render-hash="未计算"' in report
    assert report.count('data-render-hash="未计算"') >= 2
    assert REPORT_HASH_PLACEHOLDER not in report
    assert SOP_HASH_PLACEHOLDER not in report
    assert "artifact-report-hash" not in report
    assert "artifact-sop-hash" not in report


def test_data_hash_comes_from_parameter_not_artifact() -> None:
    """V11：渲染器不读 artifact.data_sha256。"""
    contract = _contract()
    contract["artifact"]["data_sha256"] = "leaky-data-hash"
    report = render_report_html(contract, data_hash="input-data-hash")
    assert "input-data-hash" in report
    assert "leaky-data-hash" not in report


def test_unhashed_renderer_writes_data_hash_before_hashing() -> None:
    """数据哈希必须在第一步写入。否则第二步回填会改变被哈希的字节。"""
    unhashed = render_report_html_unhashed(_contract(), data_hash="input-data-hash")
    assert "input-data-hash" in unhashed
    assert REPORT_HASH_PLACEHOLDER in unhashed


def test_contract_text_is_escaped() -> None:
    report = render_report_html(_contract())
    assert "<script>alert(1)</script>" not in report
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in report
    assert "<img src=x onerror=alert(1)>" not in report
    assert "&lt;img src=x onerror=alert(1)&gt;" in report
    assert 'href="javascript:' not in report


def test_renderers_are_deterministic() -> None:
    contract = _contract()
    assert render_report_html(contract) == render_report_html(contract)
    assert render_sop_html(contract) == render_sop_html(contract)
    assert render_report_html_unhashed(contract) == render_report_html_unhashed(contract)
    assert render_sop_html_unhashed(contract) == render_sop_html_unhashed(contract)


def test_renderers_do_not_start_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid(*args: object, **kwargs: object) -> None:
        raise AssertionError("渲染器不得发起 I/O")

    monkeypatch.setattr(socket.socket, "connect", forbid)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)
    monkeypatch.setattr(urllib.request, "urlopen", forbid)
    monkeypatch.setattr(builtins, "open", forbid)

    contract = _contract()
    assert "<html" in render_report_html(contract)
    assert "<html" in render_sop_html(contract)


def test_signatures_have_no_io_or_clock_parameters() -> None:
    forbidden = ("session", "http", "llm", "now", "clock")
    functions = (
        render_report_html,
        render_report_html_unhashed,
        render_sop_html,
        render_sop_html_unhashed,
    )
    for function in functions:
        parameters = inspect.signature(function).parameters
        assert "contract" in parameters
        for name in parameters:
            assert not any(token in name for token in forbidden), name


def test_hash_parameters_are_keyword_only() -> None:
    for function in (render_report_html, render_sop_html):
        parameters = inspect.signature(function).parameters
        for name in ("report_hash", "sop_hash", "data_hash"):
            assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_renderer_does_not_import_clock_db_or_http() -> None:
    """渲染器不得 import datetime、sqlalchemy、httpx，也不得自带序列化规则。"""
    namespace = vars(renderers)
    for name in ("datetime", "date", "sqlalchemy", "httpx"):
        assert name not in namespace
    source = inspect.getsource(renderers)
    for forbidden in (
        "import datetime",
        "from datetime import",
        "import sqlalchemy",
        "from sqlalchemy import",
        "import httpx",
        "from httpx import",
        "json.dumps",
    ):
        assert forbidden not in source
    assert renderers.canonical_json_bytes is canonical_json_bytes


def test_sop_contains_gates_coverage_ledger_limits_and_unknowns() -> None:
    sop = render_sop_html(_contract())
    assert sop.index("G0") < sop.index("G7")
    assert "amazon_reviews" in sop
    assert "reddit_search" in sop
    assert "0.100000" in sop
    assert "成本合计" in sop
    assert "不能推断发生率。" in sop
    assert "缺 exact S 证据。" in sop


def test_footer_contains_three_hashes() -> None:
    contract = _contract()
    report = render_report_html(
        contract,
        report_hash="report-page-hash",
        sop_hash="sop-page-hash",
        data_hash="input-data-hash",
    )
    sop = render_sop_html(
        contract,
        report_hash="report-page-hash",
        sop_hash="sop-page-hash",
        data_hash="input-data-hash",
    )
    for document in (report, sop):
        assert "合同哈希" in document
        assert "数据哈希" in document
        assert "渲染哈希" in document
        assert "contract-hash" in document
        assert "input-data-hash" in document
        assert 'data-render-hash="report-page-hash"' in document
        assert 'data-render-hash="sop-page-hash"' in document


def test_real_report_contract_model_is_accepted() -> None:
    """真实 Pydantic 合同走 model_dump(mode="json") 路径。"""
    contract = ReportContract.model_validate(_contract())
    report_digest = render_sha256(
        render_report_html_unhashed(contract, data_hash="data-digest")
    )
    sop_digest = render_sha256(
        render_sop_html_unhashed(contract, data_hash="data-digest")
    )
    report = render_report_html(
        contract,
        report_hash=report_digest,
        sop_hash=sop_digest,
        data_hash="data-digest",
    )
    assert render_sha256(report) == report_digest
    assert "2 个覆盖单元" in render_sop_html(contract)


def test_contract_model_with_model_dump_is_accepted() -> None:
    class _ContractModel:
        def __init__(self, data: Mapping[str, Any]) -> None:
            self._data = data

        def model_dump(self) -> Mapping[str, Any]:
            return self._data

    report = render_report_html(_ContractModel(_contract()))
    assert "<html" in report
    assert "4321" in report


def test_empty_contract_still_renders() -> None:
    report = render_report_html({})
    sop = render_sop_html({})
    assert "<html" in report
    assert "<html" in sop
    assert "未评级" in report
    assert "合同未提供 claims" in report
    assert "合同未提供 gates" in sop
    assert "未计算" in report
