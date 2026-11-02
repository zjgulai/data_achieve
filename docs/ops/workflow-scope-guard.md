# Workflow scope guard（2026-11-03）

## 用途

并发 workflow 或子代理写文件前，先声明写集。guard 阻止两个 workflow 写同一路径，也阻止写集外改动。

## 命令

```bash
# 声明写集与读集
python3 scripts/workflow_scope_guard.py claim \
  --id report-rewrite \
  --write tmp/staging/report-rewrite \
  --read docs/retro/

# 每个 workflow 只写自己的 staging 目录
# 合并前审计
python3 scripts/workflow_scope_guard.py audit --claim report-rewrite

# 清理超过 4 小时的 claim
python3 scripts/workflow_scope_guard.py clean
```

## 判据

| 检查 | 失败条件 |
|---|---|
| 写集重叠 | 新 claim 与未过期 claim 的写路径互为前缀 |
| 重复 claim | 同一 id 未过期；用 `--force` 覆盖 |
| 越界写 | `git status` 的改动不在写集内 |
| 读密钥 | 读集含 `.env*`、`.pem`、`.key`，且未加 `--allow-secret-read` |
| 付费调用 | claim 声明 `--paid-calls`，但 `ALLOW_PAID_API` 不是 `1` |
| claim 过期 | 超过 4 小时；先重新 claim 或 `clean` |

## 数据位置

- claim 文件：`tmp/workflow-claims/<id>.json`（gitignored）。
- 测试：`scripts/tests/test-workflow-scope-guard.sh`。
- CI：`Test operational scripts` 步骤运行测试。

## 与报告闸门的关系

报告闸门检查最终文本；scope guard 检查写入过程。两者一起用：先 claim，写 staging，合并，再跑报告闸门。

## 已知限制

- 只检查文件路径，不检查数据库、远端 API 或容器状态。
- claim 是协作约定，不是强制锁。agent 必须主动运行命令。
- 4 小时过期是固定值；长任务需要重新 claim。