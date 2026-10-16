"""日志渲染配置。

本模块只做一件事：关掉异常回溯里的局部变量。

背景（2026-10-16 归因）：本仓库没有显式 ``structlog.configure``，
于是走 structlog 的默认值。structlog 26.1.0 在装了 rich 时，
默认用 ``RichTracebackFormatter(show_locals=True, extra_lines=3)``。

后果是 ``logger.exception(...)`` 会把异常帧的局部变量连同取值一起
渲染出来。实测：一个抛 ``RuntimeError(含密钥的字符串)`` 的调用，
即使各处已用 ``_sanitized_exc_info`` 把异常显示行换成类型名，
局部变量里的原始值仍会出现在输出中——脱敏挡不住 locals。

路由层因此写过注释说"缺产品侧配置"。本模块就是那个配置。

``show_locals=False`` 保留 rich 的排版，只去掉局部变量。
不放宽任何既有断言：脱敏本就该挡住这两处。
"""

from __future__ import annotations

import structlog
import structlog.dev

# 关闭局部变量渲染，保留 rich 排版。
# 若运行环境没装 rich，structlog 会退到 plain_traceback，那本来也不含 locals。
_SAFE_EXCEPTION_FORMATTER = structlog.dev.RichTracebackFormatter(
    show_locals=False,
    # 源码上下文也收敛为 0：默认 3 行会把调用点附近的代码一并打出，
    # 那不属于脱敏目标，但同样不是诊断所需。
    extra_lines=0,
)


def configure_logging() -> None:
    """应用安全的日志渲染配置。

    幂等：重复调用无副作用。可在应用工厂里安全调用。
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer(
                exception_formatter=_SAFE_EXCEPTION_FORMATTER,
            ),
        ],
    )
