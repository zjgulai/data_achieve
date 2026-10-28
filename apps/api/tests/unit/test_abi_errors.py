"""ABI 错误基类的统一性。

F1 之前仓库里有两套同名 ``AbiServiceError``：``abi_service`` 用
``__init__(detail, status_code)``，``abi_query`` 用 ``__init__(message)`` +
类属性。路由层捕获前者，查询层抛后者，接线时必然漏分支。

这些断言把「只有一个类对象」变成会红的测试，而不是靠读代码确认。
"""

from __future__ import annotations

import pytest

from data_intelligence_hub.services import (
    abi_errors,
    abi_export,
    abi_query,
    abi_service,
    abi_upload,
)


def test_all_service_modules_share_one_base_class() -> None:
    assert abi_errors.AbiServiceError is abi_service.AbiServiceError
    assert abi_errors.AbiServiceError is abi_query.AbiServiceError
    assert issubclass(abi_upload.AbiUploadError, abi_errors.AbiServiceError)
    assert issubclass(abi_export.AbiExportError, abi_errors.AbiServiceError)
    assert issubclass(abi_query.AbiQueryValidationError, abi_errors.AbiServiceError)


def test_default_code_and_status_come_from_class_attributes() -> None:
    error = abi_errors.AbiDatasetNotFound()

    assert error.code == "abi_dataset_not_found"
    assert error.status_code == 404
    # detail 与 message 是同一份内容：路由层读前者，日志读后者，
    # 两者不一致时排查要对着两份代码看。
    assert error.detail == error.message
    assert str(error) == "abi_dataset_not_found"


def test_positional_detail_is_preserved() -> None:
    """A 套的既有调用风格（positional detail + status）必须继续有效。"""

    error = abi_errors.AbiServiceError("数据集已被占用", 409)

    assert error.detail == "数据集已被占用"
    assert error.message == "数据集已被占用"
    assert error.status_code == 409
    assert error.code == "abi_error"


def test_status_and_code_can_be_overridden_per_instance() -> None:
    error = abi_errors.AbiQueryValidationError("列不存在", 422, code="abi_column_missing")

    assert error.status_code == 422
    assert error.code == "abi_column_missing"
    # 实例覆盖不能污染类属性，否则后续同类错误会带着上一个请求的状态码。
    assert abi_errors.AbiQueryValidationError.status_code == 400
    assert abi_errors.AbiQueryValidationError.code == "abi_query_invalid"


@pytest.mark.parametrize(
    ("error_class", "expected_status", "expected_code"),
    [
        (abi_errors.AbiAccessDenied, 403, "abi_access_denied"),
        (abi_errors.AbiDatasetNotFound, 404, "abi_dataset_not_found"),
        (abi_errors.AbiQueryValidationError, 400, "abi_query_invalid"),
        (abi_errors.AbiPiiUnknownDenied, 403, "abi_pii_unknown_denied"),
        (abi_errors.AbiPiiPolicyNotConfigured, 403, "abi_pii_policy_not_configured"),
        (abi_errors.AbiFilterOnPiiDenied, 400, "abi_filter_on_pii_denied"),
        (abi_errors.AbiOrderOnPiiDenied, 400, "abi_order_on_pii_denied"),
    ],
)
def test_pii_related_errors_carry_expected_status(
    error_class: type[abi_errors.AbiServiceError],
    expected_status: int,
    expected_code: str,
) -> None:
    error = error_class()

    assert error.status_code == expected_status
    assert error.code == expected_code


def test_cursor_error_keeps_query_validation_semantics() -> None:
    """游标错误是查询校验错误的子类，路由层不必单独处理。"""

    error = abi_query.AbiQueryCursorError("cursor signature mismatch")

    assert isinstance(error, abi_errors.AbiQueryValidationError)
    assert error.status_code == 400
    assert error.code == "abi_query_cursor_invalid"
