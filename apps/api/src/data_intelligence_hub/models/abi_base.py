"""ABI 数据中心的独立 declarative base。

为什么不能复用 ``Base``：
``Base.metadata`` 被 80 多个测试用 ``create_all`` 建到 sqlite 内存库。
ABI 的表都带 ``schema="meta/raw/abi"``，sqlite 没有这些 schema，
注册进 ``Base.metadata`` 会让那批测试全部报 unknown database。

先例：``services/run_queue.py`` 同样用独立 ``MetaData``，不注册到 ``Base``。

命名约定与 ``Base`` 保持一致，保证迁移里的约束名与自动生成的 DDL 对得上。
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from data_intelligence_hub.models.base import NAMING_CONVENTION


class AbiBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
