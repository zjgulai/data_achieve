"""工具输入参数的类型契约与校验。

现有采集目录只记录参数名，没有类型信息。
本模块提供补类型与校验的统一位置。

设计约束：

- 没有登记规格的参数保持 ``untyped``，不得凭名称推断类型。
- 每个已登记规格必须给出类型、必填性和来源依据。
- 校验失败时返回结构化原因，不抛裸异常给调用方。

本模块不修改采集目录，也不触发任何执行。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

PARAMETER_CONTRACT_VERSION = "tool-params.v1"

ValueType = Literal["string", "integer", "number", "boolean", "enum", "string_list"]
SpecSource = Literal[
    "upstream_schema",
    "collector_validation",
    "documented",
    "operator_decision",
]


class ParameterSpec(BaseModel):
    """单个参数的类型规格。

    ``source`` 说明规格来自哪里。
    没有明确来源的规格不得登记。
    """

    model_config = ConfigDict(frozen=True)

    name: str
    value_type: ValueType
    required: bool
    source: SpecSource
    description: str | None = None
    default: object | None = None
    allowed_values: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    max_length: int | None = None
    pattern: str | None = None


class ToolParameterContract(BaseModel):
    """一个工具的参数契约。

    未登记的参数按 untyped 处理，只做存在性检查。
    """

    model_config = ConfigDict(frozen=True)

    tool_id: str
    contract_version: str = PARAMETER_CONTRACT_VERSION
    specs: tuple[ParameterSpec, ...] = ()

    def spec_for(self, name: str) -> ParameterSpec | None:
        for spec in self.specs:
            if spec.name == name:
                return spec
        return None

    @property
    def typed_names(self) -> frozenset[str]:
        return frozenset(spec.name for spec in self.specs)


class ParameterViolation(BaseModel):
    """单条校验失败。"""

    model_config = ConfigDict(frozen=True)

    name: str
    code: str
    message: str


class ParameterValidation(BaseModel):
    """校验结果。

    ``ok`` 为真时 ``violations`` 必为空。
    未登记类型的参数不产生类型类违规。
    """

    model_config = ConfigDict(frozen=True)

    ok: bool
    violations: tuple[ParameterViolation, ...] = ()
    untyped_names: tuple[str, ...] = ()


_INT_TYPES = {"integer"}
_NUMBER_TYPES = {"integer", "number"}


def _check_type(spec: ParameterSpec, value: object) -> ParameterViolation | None:
    """只校验已登记类型的参数。

    布尔与整数在 Python 里是父子关系，必须显式排除，
    否则 ``True`` 会被当成合法的整数。
    """
    kind = spec.value_type
    if kind == "string":
        if not isinstance(value, str):
            return _violation(spec.name, "wrong_type", "期望字符串")
        if spec.max_length is not None and len(value) > spec.max_length:
            return _violation(spec.name, "too_long", f"长度超过 {spec.max_length}")
        if spec.pattern is not None and not re.fullmatch(spec.pattern, value):
            return _violation(spec.name, "pattern_mismatch", "格式不符合要求")
    elif kind in _NUMBER_TYPES:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return _violation(spec.name, "wrong_type", "期望数值")
        if kind in _INT_TYPES and isinstance(value, float) and not value.is_integer():
            return _violation(spec.name, "wrong_type", "期望整数")
        if spec.minimum is not None and value < spec.minimum:
            return _violation(spec.name, "below_minimum", f"小于 {spec.minimum}")
        if spec.maximum is not None and value > spec.maximum:
            return _violation(spec.name, "above_maximum", f"大于 {spec.maximum}")
    elif kind == "boolean":
        if not isinstance(value, bool):
            return _violation(spec.name, "wrong_type", "期望布尔值")
    elif kind == "enum":
        if not isinstance(value, str) or value not in spec.allowed_values:
            return _violation(spec.name, "not_allowed", "不在允许取值内")
    elif kind == "string_list":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            return _violation(spec.name, "wrong_type", "期望字符串列表")
    return None


def _violation(name: str, code: str, message: str) -> ParameterViolation:
    return ParameterViolation(name=name, code=code, message=message)


def validate_parameters(
    contract: ToolParameterContract,
    params: dict[str, object],
    *,
    required_names: tuple[str, ...],
    optional_names: tuple[str, ...],
) -> ParameterValidation:
    """校验一次调用参数。

    规则：

    1. 未知参数被拒绝。服务端不接受目录之外的输入。
    2. 缺少必填参数被拒绝。
    3. 已登记规格的参数按规格校验。
    4. 未登记规格的参数只做存在性检查，并在结果里列出。
    """
    violations: list[ParameterViolation] = []
    declared = set(required_names) | set(optional_names)
    untyped: list[str] = []

    for name in sorted(set(params) - declared):
        violations.append(_violation(name, "unknown_parameter", "不在该工具的输入范围内"))

    for name in required_names:
        if name not in params:
            violations.append(_violation(name, "missing_required", "缺少必填参数"))

    for name, value in sorted(params.items()):
        if name not in declared:
            continue
        spec = contract.spec_for(name)
        if spec is None:
            untyped.append(name)
            continue
        violation = _check_type(spec, value)
        if violation is not None:
            violations.append(violation)

    return ParameterValidation(
        ok=not violations,
        violations=tuple(violations),
        untyped_names=tuple(sorted(untyped)),
    )
