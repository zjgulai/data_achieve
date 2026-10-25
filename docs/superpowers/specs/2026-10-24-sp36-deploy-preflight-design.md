# SP-36：部署前置检查接入发布流程设计

## 1. 目标

`scripts/deploy-p0.sh` 必须在生产代码发布前自动运行只读生产检查。

本批只接入生产 A 的门禁。生产 B 尚未建立独立检查，因此 B 与 `both` 代码发布必须 fail-closed。

目标行为：

| 调用方式 | 行为 |
|---|---|
| `--host a` | 运行本地检查与生产 A preflight。通过后继续发布。 |
| `--host b` | 立即失败。不得检查 key、拉取、构建、迁移或替换容器。 |
| `--host both` | 立即失败。不得先发布 A。 |
| `--host a --dry-run` | 运行完整只读 preflight。通过后只打印发布动作。 |
| `--grants-file` | 跳过代码发布 preflight。保持现有授权更新流程。 |

## 2. 范围

### 2.1 包含

- 在 `scripts/deploy-p0.sh` 中接入 `scripts/preflight-production.sh`。
- 生产 A preflight 失败时阻断代码发布。
- 生产 B 与 `both` 在 B 门禁完成前阻断代码发布。
- 保持 `--grants-file` 模式不受代码发布门禁影响。
- 保持 `--dry-run` 执行只读 preflight。
- 加固 `scripts/preflight-production.sh` 中可能假通过的检查。
- 增加不连接生产的 shell 回归测试，并接入 CI。
- 更新生产重启文档与发布回滚工作流文档。

### 2.2 不包含

- 不为生产 B 新建 preflight。
- 不修改部署目标、SSH 密钥、容器名称或 compose 文件。
- 不新增绕过 preflight 的参数。
- 不执行生产部署、迁移或容器重启。
- 不改数据库。

## 3. 现有问题

### 3.1 发布脚本没有调用完整 preflight

当前代码发布流程：

```text
参数解析
→ key 定位与本地检查
→ 远端分支检查
→ 拉取代码
→ 构建镜像
→ 数据库迁移
→ 替换容器
→ 重启 edge
→ 健康检查
→ 网关 reload
→ 公网验收
```

`scripts/preflight-production.sh` 已存在，但 `deploy-p0.sh` 没有调用它。

### 3.2 迁移号不能作为发布前固定门禁

若发布前用仓库最新 Alembic head 校验生产 revision，会产生死锁：

```text
仓库新增迁移 057
生产仍是 056
→ preflight 失败
→ 无法执行 alembic upgrade head
```

正确语义是验证正在运行的生产版本自洽：

```text
schema == "current"
schema_revision == schema_head
```

迁移发布后，再由发布后验收验证新 revision 与新 head 一致。

### 3.3 现有 preflight 可假通过

需要修复：

- `(unhealthy)` 包含 `healthy`，现有正则可能误判。
- 容器名称过滤使用子串匹配，可能命中相似名称。
- HEAD 格式检查不够严格。
- edge IP 未按边界匹配，`172.20.0.160` 可能通过。
- vault key 长度未锚定，`440` 可能通过。
- HTTP 与 SSH 缺少明确超时。
- 脚本未使用 `set -e`。

## 4. 方案选择

采用「目标级 fail-closed + schema 自洽检查」。

```text
代码发布模式
  ├─ host=a    → local preflight → A production preflight → 发布
  ├─ host=b    → 立即失败
  └─ host=both → 立即失败

授权更新模式
  └─ grants-file → 现有批准流程，不运行代码发布 preflight
```

不采用：

- B 只告警：会形成无门禁发布入口。
- `both` 自动降级为 A：行为与调用参数不一致。
- 本批同时参数化 B：B 的分支、域名、schema 与网络约束需要单独设计。
- 隐式跳过参数：会削弱门禁。抢修使用独立运维手册。

## 5. 模块设计

### 5.1 目标策略函数

在 `scripts/deploy-p0.sh` 新增：

```bash
require_supported_deploy_target() {
  case "$HOST" in
    a)
      return 0
      ;;
    b|both)
      die "生产 B 的 preflight 尚未接入。请使用 --host a，或先完成 B 门禁。"
      ;;
    *)
      die "host 只能是 a、b 或 both"
      ;;
  esac
}
```

非 grants 模式必须在 `preflight_local` 前调用。

这样 B/both 的稳定错误不会被以下错误抢先覆盖：

- 工作区不干净。
- B SSH key 不存在。
- 远端不可达。

### 5.2 A preflight 编排函数

```bash
preflight_production_a() {
  echo "== Production preflight: A =="
  SCRAPY_PROD_KEY="$A_KEY" \
  SCRAPY_PROD_HOST="$A_SSH" \
  SCRAPY_PUBLIC_URL="$A_URL" \
    bash "$ROOT_DIR/scripts/preflight-production.sh"
  echo "PASS production preflight A"
}
```

不传 `SCRAPY_EXPECTED_SCHEMA`。schema 规则由 preflight 的健康响应自洽判断实现。

`A_KEY` 由 `preflight_local` 内的 `find_key` 得到。因此调用顺序必须是：

```text
require_supported_deploy_target
→ preflight_local
→ preflight_production_a
```

### 5.3 Schema 自洽检查

`preflight-production.sh` 解析 `/api/health` JSON，并要求：

```text
status == "ok"
database == "connected"
schema == "current"
schema_revision == schema_head
```

禁止将仓库 head 与发布前生产 revision 直接比较。

发布后由 `deploy-p0.sh` 的健康验收确认新容器报告的新 head。

### 5.4 API 健康检查

使用精确容器：

```bash
health_status=$(ssh \
  -i "$KEY_FILE" \
  -o BatchMode=yes \
  -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=no \
  "$SSH_TARGET" \
  "docker inspect -f '{{.State.Health.Status}}' data_achieve_scrapy_api")
[[ "$health_status" == "healthy" ]]
```

不得从 `docker ps` 文本中匹配 `healthy`。

### 5.5 HEAD、edge IP 与 vault 长度

- HEAD：`^[0-9a-f]{7,}$`
- edge IP：按 `lighthouse_ai_video_net` 精确取值并比较 `172.20.0.16`
- vault key 长度：精确比较 `44`

### 5.6 超时

公网请求：

```bash
curl --connect-timeout 5 --max-time 15
```

SSH：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no
```

该配置与现有部署脚本一致。

## 6. 控制流

### 6.1 代码发布模式

```text
解析参数
→ require_supported_deploy_target
→ preflight_local（含 key 定位）
→ preflight_production_a
→ check_remote_branches
→ deploy_one
```

门禁发生在：

- 远端生产代码拉取前。
- 镜像构建前。
- `alembic upgrade head` 前。
- 容器替换前。
- edge 重启前。

### 6.2 Grants 模式

grants 分支必须在代码发布门禁前分流。

现有 grants 模式会：

- 更新外访授权。
- 替换 API 容器。
- 重启 edge，使新环境变量生效。

它不会：

- 构建代码镜像。
- 执行数据库迁移。

本批保持该行为，不调用代码发布 preflight。

### 6.3 Dry-run

`--dry-run` 定义为：

> 不改变生产状态，但仍执行只读 preflight，包括本地 `git fetch`、公网 HTTP 与远端 SSH 查询。

Dry-run 执行：

- 目标策略检查。
- 本地检查。
- 生产 A preflight。
- 远端分支检查。

Dry-run 不执行：

- 生产代码拉取。
- 镜像构建。
- 数据库迁移。
- 容器替换。
- edge 重启。
- 发布后的 `verify_public`。

## 7. 错误语义

### 7.1 A preflight 失败

脚本必须：

- 保留每个 preflight 子检查的 PASS/FAIL 输出。
- 非零退出。
- 不打印 `PASS production preflight A`。
- 不进入远端分支检查或部署函数。

### 7.2 B 或 both

稳定错误：

```text
失败：生产 B 的 preflight 尚未接入。请使用 --host a，或先完成 B 门禁。
```

该错误必须先于本地工作区、key 与 SSH 检查。

### 7.3 Grants 模式

保持现有错误语义。

## 8. 可观测性

成功路径输出：

```text
== Production preflight: A ==
PASS  public health 200
PASS  API healthy
PASS  edge fixed IP 172.20.0.16
PASS production preflight A
```

失败路径保留子检查结果，但不输出总体 PASS。

操作人员必须能区分：

- 目标不支持。
- 本地检查失败。
- 生产 A preflight 失败。
- 远端分支失败。
- 部署步骤失败。

## 9. 自动测试

新增：

```text
scripts/tests/test-deploy-p0-preflight.sh
```

测试不得连接生产。

### 9.1 沙盘结构

测试创建临时仓库结构：

```text
$tmp/
├── scripts/
│   ├── deploy-p0.sh
│   └── preflight-production.sh   # 成功或失败替身
├── zhoujian_pachong.pem          # 空假 key
└── bin/
    ├── git
    ├── ssh
    ├── curl
    └── python3
```

将临时 `bin` 放在 PATH 最前。

不得 `source scripts/deploy-p0.sh`。该脚本会直接执行主流程。

### 9.2 测试场景

1. A dry-run：preflight 在远端分支检查前执行。
2. A preflight 失败：脚本非零退出，且不执行分支检查、构建、迁移或替换。
3. B dry-run：立即失败并输出稳定文案。
4. both dry-run：立即失败并输出稳定文案。
5. B/both 缺少 key：仍先输出 B 门禁错误。
6. A grants dry-run：跳过代码发布 preflight。
7. B grants dry-run：保留现有 grants 行为。
8. unhealthy 容器：preflight 失败。
9. edge IP 为 `172.20.0.160`：失败。
10. vault 长度 440：失败。
11. HEAD 非十六进制：失败。
12. dry-run：不执行发布后 `verify_public`。

### 9.3 CI

在现有 CI 的 shell/脚本门禁位置加入：

```bash
bash scripts/tests/test-deploy-p0-preflight.sh
```

该步骤必须阻断，不得设置 `continue-on-error`。

SP-41 也修改 CI。实施前必须合并最新 main，保留目录守卫与本测试。

## 10. 人工只读验收

以下命令连接生产 A，不能放进离线 shell 测试：

```bash
bash scripts/preflight-production.sh
scripts/deploy-p0.sh --host a --dry-run
```

前置条件：

- 工作区干净。
- 本地分支包含 `origin/main`。
- 生产 A 可访问。

预期：

- preflight 输出 `ALL CHECKS PASSED`。
- dry-run 输出 `PASS production preflight A`。
- 生产没有 Git、镜像、数据库或容器状态变化。

## 11. 文档更新

### 11.1 `docs/ops/production-restart.md`

写明：

- `deploy-p0.sh --host a` 在构建前自动运行本地编排 preflight。
- preflight 失败时停止。
- B 与 `both` 在 B 门禁完成前不可用于代码发布。
- grants 模式跳过代码发布 preflight，但仍会替换 API 并重启 edge。

### 11.2 `docs/workflows/workflow-release-rollback-stable.md`

区分两类检查：

1. 本地编排检查：

```bash
bash scripts/preflight-production.sh
```

2. 生产主机内部检查：

```bash
bash scripts/deploy-preflight-scrapy.sh
```

两者都必须执行，不是二选一。

## 12. 帮助文本

更新 `deploy-p0.sh --help`：

- `--host a` 支持代码发布。
- `--host b` 与 `--host both` 在 B 门禁完成前拒绝代码发布。
- `--grants-file` 的 b/both 行为保持。
- `--dry-run` 会执行只读 preflight，不只是打印命令。

## 13. 抢修

生产 API 不健康时，常规门禁会阻止代码发布。

本批不增加 `--skip-preflight`。

抢修必须使用独立 runbook，并明确记录：

- 事故编号。
- 批准人。
- 目标主机。
- 回滚锚点。
- 验收结果。

不得通过修改环境变量或替换 preflight 脚本绕过门禁。

## 14. 发布影响

本任务只修改：

- 发布脚本。
- preflight 脚本。
- shell 测试。
- CI。
- 运维文档。

不执行：

- 生产部署。
- 容器重启。
- 数据库迁移。
- 飞书通知。

## 15. 回滚

回滚提交即可恢复旧发布脚本。

不需要：

- 数据库 downgrade。
- 镜像回滚。
- 容器重建。
- 环境变量回滚。

回滚记录必须说明：自动生产门禁已被移除。

## 16. 验收判据

以下条件必须全部满足：

- A 代码发布在任何生产写操作前运行 preflight。
- A preflight 校验生产健康自洽，不硬编码仓库最新迁移号。
- A preflight 失败时发布脚本立即退出。
- B 与 both 的代码发布在任何 key/SSH/生产检查前失败。
- `--dry-run` 执行只读 preflight，但不执行 post-deploy 验收。
- `--grants-file` 不执行代码发布 preflight，现有行为不变。
- unhealthy 容器、错误 HEAD、错误 edge IP、错误 vault 长度都无法假通过。
- 自动测试不连接生产环境。
- shell 测试进入 CI 且为阻断式。
- 两份运维文档与脚本行为一致。
- 本任务不产生生产写操作。

## 17. 后续任务

生产 B 门禁必须单独立项。该任务至少需要冻结：

- B 的 SSH 目标与密钥。
- B 的部署分支。
- B 的公网 URL。
- B 的 schema 自洽检查。
- B 的 edge 网络与 IP 约束。
- B 的 Provider 配置检查。
- B 的回滚锚点。
