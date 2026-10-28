"""``build_query`` 的事务归属。

改动前 ``build_query`` 在末尾 ``await session.commit()``，异常时 ``rollback()``。
这有两个后果：

1. 一次「只读查询」会结束掉调用方的事务。调用方后续的写入会落在一个
   意外的新事务里，前面读到的行不再处于同一快照。
2. 导出复用它时，整个导出过程一直持有 ``export_job`` 的行锁。

所以事务边界移到调用方：``build_query`` 不 commit、不 rollback，
需要独立事务的用 ``run_query_page``，它包一层只读会话。

这些断言用假的 session 直接观察调用，不需要数据库。
"""

from __future__ import annotations

import ast
import inspect
import textwrap
import uuid
from typing import Any

import pytest

from data_intelligence_hub.services import abi_query


class _RecordingSession:
    """记录 commit/rollback 调用次数的假 session。

    只实现 ``build_query`` 会走到的方法。任何未实现的方法被调用都会抛
    ``AttributeError``——这本身也是一种断言：说明 ``build_query``
    多碰了它不该碰的东西。
    """

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def execute(self, *_args: Any, **_kwargs: Any):
        raise AssertionError("build_query 在参数校验阶段就应失败，不应执行 SQL")

    def in_transaction(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_build_query_rejects_out_of_range_limit_without_touching_transaction() -> None:
    session = _RecordingSession()

    with pytest.raises(abi_query.AbiQueryValidationError):
        await abi_query.build_query(
            session,  # type: ignore[arg-type]
            uuid.uuid4(),
            limit=0,
            workspace_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

    assert session.commits == 0
    assert session.rollbacks == 0


def _called_attrs(func: Any) -> set[str]:
    """收集一个函数体内所有 ``x.method(...)`` 形式调用的方法名。"""
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_build_query_body_never_calls_commit_or_rollback() -> None:
    """静态断言：``build_query`` 的函数体里没有 commit/rollback。

    这比用假 session 撞失败路径更可靠——后者只能覆盖被触发的那一条分支，
    而成功路径（需要数据库）恰恰是最容易把 commit 加回去的地方。
    直接读源码，任何一条分支加回事务调用都会红。
    """
    called = _called_attrs(abi_query.build_query)

    assert "commit" not in called, "build_query 不得 commit 调用方的事务"
    assert "rollback" not in called, "build_query 不得 rollback 调用方的事务"


def test_read_only_session_is_the_one_that_commits() -> None:
    """事务的所有权在 ``read_only_session``，不在 ``build_query``。"""
    called = _called_attrs(abi_query.read_only_session)

    assert "commit" in called
    assert "rollback" in called


def test_read_only_session_is_exported() -> None:
    """独立只读会话必须是公开 API，导出层与路由都要用它。"""

    assert callable(abi_query.read_only_session)
    assert callable(abi_query.run_query_page)


@pytest.mark.asyncio
async def test_read_only_session_accepts_injectable_factory() -> None:
    """工厂必须可注入。

    硬编码全局 ``async_session_factory`` 会让测试的 ``dependency_overrides``
    失效——测试打到真实库上，而它以为自己连的是内存库。
    """
    entered: list[str] = []

    class _FakeSession:
        async def execute(self, statement: Any) -> None:
            entered.append(str(statement))

        async def commit(self) -> None:
            entered.append("commit")

        async def rollback(self) -> None:
            entered.append("rollback")

    class _FakeFactory:
        def __call__(self):
            session = _FakeSession()

            class _Ctx:
                async def __aenter__(self_inner):
                    return session

                async def __aexit__(self_inner, *_exc):
                    return False

            return _Ctx()

    async with abi_query.read_only_session(
        session_factory=_FakeFactory()  # type: ignore[arg-type]
    ):
        pass

    joined = " | ".join(entered)
    assert "READ ONLY" in joined, f"必须声明只读事务，实际执行：{joined}"
    assert "statement_timeout" in joined
    # 正常退出要提交，否则只读事务会一直挂着直到连接归还。
    assert entered[-1] == "commit"
