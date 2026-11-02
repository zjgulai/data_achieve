# TD-2026-11-02 · ABI/洞察 mypy 债务

- 状态：已登记，待清理
- 发现日期：2026-11-02
- 发现方式：`3f889e7` 的 CI `API Quality Gate` 在 `Mypy (non-regression)` 步骤失败
- 处理：2026-11-02 将 baseline 从 934 调到 976，先恢复 CI 绿；这不是修复

## 为什么记这条

mypy 是「不回归」门禁，不是「零错误」门禁。ABI 与洞察两批代码合入时，baseline 没有同步更新，CI 从 2026-10-31 起一直是红的。红灯期间任何新类型错误都不会被发现。

更新 baseline 只是把已知债务登记下来，避免它继续挡住新提交。债务本身还在。

## 债务构成（2026-11-02 实测）

| 文件 | 错误数 | 类型 |
|---|---:|---|
| `src/.../repositories/abi.py` | 1 | `Result[Any]` 无 `rowcount` |
| `src/.../services/abi_export.py` | 1 | 赋值类型不兼容 |
| `src/.../services/abi_query.py` | 4 | `async_sessionmaker` / `sessionmaker` 混用 |
| `tests/postgres_abi/*` | 14 | 未注解的 helper、`AbiBase` 未显式导出 |
| `tests/unit/test_abi_*.py` | 8 | 未显式导出、`abi_export`/`abi_repo` 属性 |
| `tests/unit/test_contract_*.py` | 16 | `load_module` 未注解、泛型 `dict`、Any 返回 |
| `tests/unit/test_insight_report_import.py` | 2 | async generator 返回类型、sessionmaker |
| 其他 | 0 | — |
| **合计** | **42** | baseline 934 → 976 |

## 完成定义

1. 下列任一成立：
   - 修完 42 个错误，baseline 回到 934 或更低；
   - 或逐条写 `# type: ignore[code]` 并注明原因，baseline 只保留真实不可修项。
2. `uv run python ../../scripts/check_mypy_baseline.py --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests` 退出 0，且 current 不再上升。
3. CI `API Quality Gate` 的 mypy 步骤为绿。
4. 新增代码不得再让 current 上升；baseline 更新必须单独提交并说明原因。

## 优先级

P2。它不阻塞功能，但会让 CI 失去类型回归保护。建议在 C2 开工前清完，避免新代码继续叠加。

## 相关

- `docs/tickets/NB-2026-11-02-next-batch.md` P1-2
- `configs/quality/mypy-src-tests-signatures.txt`
- `configs/quality/mypy-baseline-provenance.json`