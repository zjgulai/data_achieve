"""ABI 外部数据中心模块。

目录约定：

- 模型继承 ``models.abi_base.AbiBase``，绝不继承 ``Base``：
  ABI 表都在 ``meta`` / ``raw`` / ``abi`` schema 下，注册进 ``Base.metadata``
  会让 80 多个使用 sqlite ``create_all`` 的测试全部失败。
- 本阶段只有常驻 worker 骨架（``abi.ingest``）。摄取、导出与 API 路由
  按 ``docs/plans/abi-external-datacenter.md`` 的切片逐步补齐。
"""
