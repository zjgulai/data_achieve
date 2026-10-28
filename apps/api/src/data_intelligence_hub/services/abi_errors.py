"""ABI 服务的统一错误基类。

在此之前仓库里有两套同名的 ``AbiServiceError``：

- ``abi_service``（已接线）：``__init__(detail, status_code=400)``，实例属性。
- ``abi_query`` / ``abi_upload`` / ``abi_export``（未接线）：``__init__(message)``，
  ``code`` 与 ``status_code`` 是类属性。

路由层只捕获一种类型，两套并存意味着接线时必须写适配层，而适配层是最容易
漏掉分支的地方。这里把两者合成一个基类，同时满足两种调用风格：

    AbiServiceError("数据集不存在", 404)          # A 套风格
    AbiDatasetNotFound()                          # B 套风格（类属性给默认值）

``detail`` 与 ``message`` 是同一份内容的两个名字：路由层读 ``detail``，
服务层日志读 ``message``。让它们指向同一个字符串，避免出现「路由报 A、
日志说 B」这类需要对着两份代码才能解释的现象。
"""

from __future__ import annotations


class AbiServiceError(Exception):
    """带 HTTP 语义的 ABI 业务错误，由路由层转换成 HTTPException。"""

    # 子类用类属性给默认值；构造器参数优先。
    code: str = "abi_error"
    status_code: int = 400

    def __init__(
        self,
        detail: str | None = None,
        status_code: int | None = None,
        *,
        code: str | None = None,
    ) -> None:
        text = detail or self.code
        self.detail = text
        self.message = text
        # 实例级覆盖：只有显式传入才写实例字典，否则子类的类属性生效。
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        super().__init__(text)


# ---------------------------------------------------------------- 查询侧
#
# 这些类型原本定义在 abi_query.py。移到这里是为了让 abi_service 的路由层
# 能按类型区分 PII 相关拒绝，而不必 import 尚未接线的查询模块。


class AbiAccessDenied(AbiServiceError):
    """没有 grant，或 grant 的角色不够。"""

    code = "abi_access_denied"
    status_code = 403


class AbiDatasetNotFound(AbiServiceError):
    """数据集不存在，或不在当前 workspace。"""

    code = "abi_dataset_not_found"
    status_code = 404


class AbiQueryValidationError(AbiServiceError):
    """查询参数非法（列不存在、操作符不支持等）。"""

    code = "abi_query_invalid"
    status_code = 400


class AbiPiiUnknownDenied(AbiServiceError):
    """列的 PII 等级是 unknown，按策略拒绝访问。

    unknown 不等于「没有 PII」，它等于「还没判定」。默认拒绝是唯一安全的
    解释：放行它等于让未判定字段以明文流出。
    """

    code = "abi_pii_unknown_denied"
    status_code = 403


class AbiPiiPolicyNotConfigured(AbiServiceError):
    """数据集还没有 PII 策略，但访问路径要求先有策略。"""

    code = "abi_pii_policy_not_configured"
    status_code = 403


class AbiFilterOnPiiDenied(AbiServiceError):
    """对非 none 等级的列做了过滤。

    过滤本身会泄露信息：可以通过二分探测出明文值。所以只允许对
    pii_class=none 的列过滤。
    """

    code = "abi_filter_on_pii_denied"
    status_code = 400


class AbiOrderOnPiiDenied(AbiServiceError):
    """对非 none 等级的列做了排序。排序同样可用于推断明文顺序。"""

    code = "abi_order_on_pii_denied"
    status_code = 400
