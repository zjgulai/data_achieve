from __future__ import annotations

import pytest

from data_intelligence_hub.tool_catalog.parameters import (
    ParameterSpec,
    ToolParameterContract,
    validate_parameters,
)


def _contract(*specs: ParameterSpec) -> ToolParameterContract:
    return ToolParameterContract(tool_id="demo_tool", specs=specs)


def test_untyped_parameters_pass_without_type_claims() -> None:
    # 没有登记规格的参数只做存在性检查。
    contract = _contract()
    result = validate_parameters(
        contract,
        {"keyword": "coffee", "max_items": 30},
        required_names=("keyword",),
        optional_names=("max_items",),
    )
    assert result.ok is True
    assert result.violations == ()
    # 未登记的参数必须被列出，而不是被当作已校验。
    assert result.untyped_names == ("keyword", "max_items")
    assert contract.typed_names == frozenset()


def test_unknown_parameter_is_rejected() -> None:
    contract = _contract()
    result = validate_parameters(
        contract,
        {"keyword": "coffee", "drop_tables": True},
        required_names=("keyword",),
        optional_names=(),
    )
    assert result.ok is False
    assert [v.code for v in result.violations] == ["unknown_parameter"]
    assert result.violations[0].name == "drop_tables"


def test_missing_required_parameter_is_rejected() -> None:
    contract = _contract()
    result = validate_parameters(
        contract, {}, required_names=("keyword",), optional_names=()
    )
    assert result.ok is False
    assert [v.code for v in result.violations] == ["missing_required"]


def test_typed_spec_enforces_type_and_bounds() -> None:
    contract = _contract(
        ParameterSpec(
            name="max_items",
            value_type="integer",
            required=False,
            source="collector_validation",
            minimum=1,
            maximum=100,
        ),
        ParameterSpec(
            name="sort_type",
            value_type="enum",
            required=False,
            source="upstream_schema",
            allowed_values=("latest", "popular"),
        ),
    )
    ok = validate_parameters(
        contract,
        {"max_items": 30, "sort_type": "latest"},
        required_names=(),
        optional_names=("max_items", "sort_type"),
    )
    assert ok.ok is True
    assert ok.untyped_names == ()

    below = validate_parameters(
        contract, {"max_items": 0}, required_names=(), optional_names=("max_items",)
    )
    assert [v.code for v in below.violations] == ["below_minimum"]

    bad_enum = validate_parameters(
        contract, {"sort_type": "whatever"}, required_names=(), optional_names=("sort_type",)
    )
    assert [v.code for v in bad_enum.violations] == ["not_allowed"]

    wrong_type = validate_parameters(
        contract, {"max_items": "thirty"}, required_names=(), optional_names=("max_items",)
    )
    assert [v.code for v in wrong_type.violations] == ["wrong_type"]


def test_boolean_is_not_accepted_as_integer() -> None:
    # Python 里 bool 是 int 的子类，必须显式排除，
    # 否则 True 会被当成合法的 max_items=1。
    contract = _contract(
        ParameterSpec(
            name="max_items",
            value_type="integer",
            required=False,
            source="collector_validation",
        )
    )
    result = validate_parameters(
        contract, {"max_items": True}, required_names=(), optional_names=("max_items",)
    )
    assert result.ok is False
    assert [v.code for v in result.violations] == ["wrong_type"]


@pytest.mark.parametrize(
    ("value_type", "value", "ok"),
    [
        ("string", "text", True),
        ("string", 12, False),
        ("number", 1.5, True),
        ("number", "1.5", False),
        ("boolean", False, True),
        ("boolean", 0, False),
        ("string_list", ["a", "b"], True),
        ("string_list", ["a", 1], False),
    ],
)
def test_value_type_matrix(value_type: str, value: object, ok: bool) -> None:
    contract = _contract(
        ParameterSpec(
            name="field",
            value_type=value_type,  # type: ignore[arg-type]
            required=True,
            source="operator_decision",
        )
    )
    result = validate_parameters(
        contract, {"field": value}, required_names=("field",), optional_names=()
    )
    assert result.ok is ok
