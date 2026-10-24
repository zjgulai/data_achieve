# SP-36 部署前置检查接入发布流程实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将生产 A 的只读 preflight 接入 `deploy-p0.sh`，让代码发布在任何生产写操作前 fail-closed；在生产 B 门禁完成前拒绝 B 与 `both` 代码发布。

**Architecture:** `preflight-production.sh` 负责单一生产检查逻辑，并以 health 自洽语义校验 schema。`deploy-p0.sh` 只负责编排目标策略、本地检查、A preflight 和发布步骤。离线 shell 测试在临时目录复制脚本并注入假命令，证明失败路径不会触发 SSH、构建、迁移或容器替换。

**Tech Stack:** Bash 3.2+、curl、ssh、Docker Compose、Python 3.12（JSON 解析）、GitHub Actions、GitNexus。

## Global Constraints

- `--host a` 代码发布必须在任何生产写操作前运行 A preflight。
- `--host b` 与 `--host both` 的代码发布必须立即失败，且失败发生在 key、SSH、本地工作区和远端分支检查之前。
- `--grants-file` 必须跳过代码发布 preflight，并保持现有 A/B/both 授权更新行为。
- `--dry-run` 必须运行只读 preflight，但不得执行 post-deploy `verify_public`。
- Schema 门禁必须检查生产自洽：`schema == "current"` 且 `schema_revision == schema_head`。不得用仓库最新迁移号阻断迁移发布。
- API 健康必须通过 `docker inspect` 精确比较 `healthy`，不得匹配文本子串。
- 远端 HEAD、edge IP、vault key 长度必须精确匹配。
- curl 和 SSH 必须有明确超时。SSH 选项必须与部署脚本一致。
- 不新增 `--skip-preflight` 或环境变量绕过入口。
- 自动测试不得连接生产环境。
- Shell 测试必须进入 CI，且不得 `continue-on-error`。
- 本任务不部署、不迁移、不重启容器、不更新飞书。
- 中文文档使用短句、主动语态。机器可读路径、变量和命令保持原样。
- 编辑函数前运行 GitNexus impact。`risk: UNKNOWN` 时用文本搜索补证。
- 写中文文件后用临时文件、`fsync()` 与 `os.replace()` 重写，确认 NUL=0。

---

## File Structure

- Modify: `scripts/preflight-production.sh`
  - 提供精确、可复用的生产 A 只读门禁。
- Modify: `scripts/deploy-p0.sh`
  - 编排目标策略、A preflight、grants 分流和 dry-run。
- Create: `scripts/tests/test-preflight-production.sh`
  - 在临时沙盘中验证 preflight 的精确判定。
- Create: `scripts/tests/test-deploy-p0-preflight.sh`
  - 在临时沙盘中验证发布脚本顺序和 fail-closed 行为。
- Modify: `.github/workflows/ci.yml`
  - 运行两个 shell 测试，阻断失败。
- Modify: `docs/ops/production-restart.md`
  - 更新 A/B/both/grants/dry-run 操作说明。
- Modify: `docs/workflows/workflow-release-rollback-stable.md`
  - 区分本地编排 preflight 与生产主机内部 preflight。

---

### Task 1: 加固生产 A preflight

**Files:**
- Modify: `scripts/preflight-production.sh:1-94`
- Create: `scripts/tests/test-preflight-production.sh`

**Interfaces:**
- Consumes:
  - `SCRAPY_PROD_KEY`：生产 A SSH key 路径。
  - `SCRAPY_PROD_HOST`：默认 `ubuntu@43.163.92.244`。
  - `SCRAPY_PUBLIC_URL`：默认 `https://scrapy.luteos.com`。
  - `SCRAPY_EDGE_FIXED_IP`：默认 `172.20.0.16`。
- Produces:
  - 退出码 0：所有生产 A 检查通过。
  - 非零：至少一项检查失败。
  - 稳定 PASS/FAIL 输出；不打印 secret。

- [ ] **Step 1: 运行影响分析与调用方搜索**

```bash
cd /Users/lute/Project/data_scrapy-sp36
node /Users/lute/Project/data_scrapy/.gitnexus/run.cjs impact \
  "preflight-production.sh" --direction upstream --repo /Users/lute/Project/data_scrapy || true
grep -rn "preflight-production.sh" scripts docs .github --exclude-dir=.git
```

预期：GitNexus 可能无法索引 shell 文件。文本搜索确认现有调用点仅为人工文档或脚本，本任务将新增 `deploy-p0.sh` 与 CI 调用。

- [ ] **Step 2: 写 preflight 失败测试脚本**

创建 `scripts/tests/test-preflight-production.sh`。

测试脚本必须：

1. 创建临时目录。
2. 将 `preflight-production.sh` 复制到临时目录。
3. 在临时 PATH 中提供假 `git`、`curl`、`ssh`。
4. 通过环境变量控制假命令输出。
5. 每个用例运行独立子进程，避免全局变量污染。

核心 helper：

```bash
run_case() {
  local name="$1"
  shift
  local stdout="$TMP_DIR/$name.out"
  local stderr="$TMP_DIR/$name.err"
  set +e
  env PATH="$FAKE_BIN:$PATH" "$@" \
    bash "$TMP_DIR/scripts/preflight-production.sh" \
    >"$stdout" 2>"$stderr"
  local rc=$?
  set -e
  printf '%s' "$rc"
}

assert_contains() {
  local file="$1" expected="$2"
  grep -Fq -- "$expected" "$file" || {
    echo "missing: $expected" >&2
    return 1
  }
}
```

首批失败用例：

- `schema_revision != schema_head` 应失败。
- `schema != current` 应失败。
- API health 为 `unhealthy` 应失败。
- edge IP 为 `172.20.0.160` 应失败。
- vault key 长度 440 应失败。
- HEAD 为 `not-a-sha` 应失败。
- HTTP 超时应失败。

假 health JSON：

```json
{
  "status": "ok",
  "database": "connected",
  "schema": "current",
  "schema_revision": "202610220056",
  "schema_head": "202610220056"
}
```

- [ ] **Step 3: 运行测试并确认红灯**

```bash
cd /Users/lute/Project/data_scrapy-sp36
bash scripts/tests/test-preflight-production.sh
```

预期：多个用例失败。现有实现仍会接受 `unhealthy`、错误 IP/长度，且使用固定 schema 号。

- [ ] **Step 4: 实现精确检查**

修改脚本头：

```bash
set -euo pipefail

PUBLIC_URL="${SCRAPY_PUBLIC_URL:-https://scrapy.luteos.com}"
SSH_TARGET="${SCRAPY_PROD_HOST:-ubuntu@43.163.92.244}"
KEY_FILE="${SCRAPY_PROD_KEY:-}"
EXPECTED_EDGE_IP="${SCRAPY_EDGE_FIXED_IP:-172.20.0.16}"
CURL=(curl --connect-timeout 5 --max-time 15 -fsS)
SSH=(ssh -i "$KEY_FILE" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no)
```

公网 health 读取：

```bash
health_json="$(${CURL[@]} "$PUBLIC_URL/api/health")"
python3 - "$health_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
checks = {
    "status": payload.get("status") == "ok",
    "database": payload.get("database") == "connected",
    "schema": payload.get("schema") == "current",
    "schema_alignment": payload.get("schema_revision") == payload.get("schema_head"),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("health mismatch: " + ", ".join(failed))
PY
```

远端脚本必须输出稳定键值：

```bash
printf 'HEAD %s\n' "$(git rev-parse --short HEAD)"
printf 'EDGE_IP %s\n' "$(docker inspect -f '{{with index .NetworkSettings.Networks "lighthouse_ai_video_net"}}{{.IPAddress}}{{end}}' data_achieve_scrapy_edge)"
printf 'API_HEALTH %s\n' "$(docker inspect -f '{{.State.Health.Status}}' data_achieve_scrapy_api)"
printf 'VAULT_KEY_LEN %s\n' "${#PLATFORM_CREDENTIAL_MASTER_KEY}"
printf 'TIKTOK_TOOL_COUNT %s\n' "$tool_count"
```

本地精确断言：

```bash
grep -Eq '^HEAD [0-9a-f]{7,}$' "$remote_output"
grep -Fxq "EDGE_IP $EXPECTED_EDGE_IP" "$remote_output"
grep -Fxq 'API_HEALTH healthy' "$remote_output"
grep -Fxq 'VAULT_KEY_LEN 44' "$remote_output"
grep -Fxq 'TIKTOK_TOOL_COUNT 16' "$remote_output"
```

删除硬编码 `EXPECTED_SCHEMA` 比较与未使用的 `ENV_FILE`。

- [ ] **Step 5: 运行测试并确认绿灯**

```bash
cd /Users/lute/Project/data_scrapy-sp36
bash scripts/tests/test-preflight-production.sh
bash -n scripts/preflight-production.sh
```

预期：全部用例通过。

- [ ] **Step 6: 字节级重写与 lint**

```bash
python3 - <<'PY'
import os
from pathlib import Path

for name in (
    "scripts/preflight-production.sh",
    "scripts/tests/test-preflight-production.sh",
):
    path = Path(name)
    data = path.read_bytes().rstrip(b"\x00")
    if b"\x00" in data:
        raise SystemExit(f"embedded NUL: {name}")
    if not data.endswith(b"\n"):
        data += b"\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
PY
bash -n scripts/preflight-production.sh
bash -n scripts/tests/test-preflight-production.sh
python3 scripts/check_file_integrity.py
```

- [ ] **Step 7: 提交 Task 1**

```bash
git add scripts/preflight-production.sh scripts/tests/test-preflight-production.sh
git commit -m "fix(deploy): 加固生产 A preflight"
```

---

### Task 2: 将 preflight 接入代码发布控制流

**Files:**
- Modify: `scripts/deploy-p0.sh:1-711`
- Create: `scripts/tests/test-deploy-p0-preflight.sh`

**Interfaces:**
- Consumes: Task 1 的 `scripts/preflight-production.sh`。
- Produces:
  - `require_supported_deploy_target()`
  - `preflight_production_a()`
  - A/B/both/grants/dry-run 的冻结行为。

- [ ] **Step 1: 运行影响分析与控制流定位**

```bash
cd /Users/lute/Project/data_scrapy-sp36
grep -nE '^preflight_local|^check_remote_branches|^deploy_one|^verify_public|^apply_grants_one|^if \[\[ -n' scripts/deploy-p0.sh
node /Users/lute/Project/data_scrapy/.gitnexus/run.cjs impact \
  "deploy_one" --direction upstream --repo /Users/lute/Project/data_scrapy || true
```

文本搜索必须确认 main flow 位于文件末尾，grants 分支发生在代码发布路径之前。

- [ ] **Step 2: 写发布脚本失败测试**

创建 `scripts/tests/test-deploy-p0-preflight.sh`。

测试必须复制两份脚本到临时目录：

```bash
mkdir -p "$TMP_DIR/scripts" "$TMP_DIR/bin"
cp scripts/deploy-p0.sh "$TMP_DIR/scripts/"
cp scripts/preflight-production.sh "$TMP_DIR/scripts/"
: > "$TMP_DIR/zhoujian_pachong.pem"
: > "$TMP_DIR/DDDD.pem"
chmod 600 "$TMP_DIR"/*.pem
```

不能 `source` 被测脚本。

假命令将调用顺序写入 `CALL_LOG`：

```bash
cat > "$TMP_DIR/bin/git" <<'SH'
#!/usr/bin/env bash
echo "git $*" >> "$CALL_LOG"
case "$1 $2" in
  "status --porcelain") exit 0 ;;
  "rev-parse HEAD") echo "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" ;;
  "rev-parse --short") echo "aaaaaaa" ;;
  "ls-remote --heads") echo -e "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/heads/$4" ;;
esac
SH
```

测试场景：

1. `--host a --dry-run`：调用顺序为 target → local → production preflight → remote branch。
2. A preflight 返回 1：脚本非零退出；调用日志没有 `ls-remote`、`ssh`、build、alembic、up 或 restart。
3. `--host b --dry-run`：立即返回稳定 B 文案；不查 key，不运行 preflight。
4. `--host both --dry-run`：同上。
5. grants 模式：A/B/both 都不调用代码发布 preflight。
6. dry-run 不调用 `verify_public`。通过假 curl 调用数断言。

- [ ] **Step 3: 运行测试并确认红灯**

```bash
bash scripts/tests/test-deploy-p0-preflight.sh
```

预期：失败。现有脚本没有目标门禁，也没有 A preflight 调用。

- [ ] **Step 4: 更新帮助文本**

`usage()` 必须写明：

```text
--host a             支持代码发布。
--host b|both        B 门禁完成前拒绝代码发布；grants 模式仍可使用。
--dry-run            不改变生产状态；仍执行只读 preflight。
```

- [ ] **Step 5: 新增目标策略函数**

```bash
require_supported_deploy_target() {
  case "$HOST" in
    a) return 0 ;;
    b|both)
      die "生产 B 的 preflight 尚未接入。请使用 --host a，或先完成 B 门禁。"
      ;;
    *) die "host 只能是 a、b 或 both" ;;
  esac
}
```

- [ ] **Step 6: 新增 A preflight 编排函数**

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

不得传 schema 版本常量。

- [ ] **Step 7: 调整 main flow**

目标结构：

```bash
if [[ -n "$GRANTS_FILE" ]]; then
  preflight_local
  if [[ "$HOST" == "a" || "$HOST" == "both" ]]; then
    apply_grants_one A "$A_KEY" "$A_SSH" "$A_URL"
  fi
  if [[ "$HOST" == "b" || "$HOST" == "both" ]]; then
    apply_grants_one B "$B_KEY" "$B_SSH" "$B_URL"
  fi
  echo "外访批准更新完成"
  exit 0
fi

require_supported_deploy_target
preflight_local
preflight_production_a
check_remote_branches

if [[ "$HOST" == "a" ]]; then
  deploy_one A "$A_KEY" "$A_SSH" "$A_BRANCH" "$A_URL"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    verify_public A "$A_URL"
  fi
fi
```

B/both 必须在 `preflight_local` 前失败。

- [ ] **Step 8: 运行测试并确认绿灯**

```bash
bash scripts/tests/test-deploy-p0-preflight.sh
bash -n scripts/deploy-p0.sh
```

预期：全部通过。

- [ ] **Step 9: 回归 grants 模式**

```bash
bash scripts/tests/test-deploy-p0-preflight.sh --case grants
```

如果测试脚本不支持 `--case`，运行全部测试并单独打印 grants 用例名称。必须证明 A/B/both grants 不调用 `preflight-production.sh`。

- [ ] **Step 10: 提交 Task 2**

```bash
git add scripts/deploy-p0.sh scripts/tests/test-deploy-p0-preflight.sh
git commit -m "feat(deploy): 发布前自动运行生产 preflight"
```

---

### Task 3: 将 shell 门禁接入 CI

**Files:**
- Modify: `.github/workflows/ci.yml`
- Test: `scripts/tests/test-preflight-production.sh`
- Test: `scripts/tests/test-deploy-p0-preflight.sh`

**Interfaces:**
- Consumes: Tasks 1-2 的两个 shell 测试。
- Produces: CI 阻断步骤。

- [ ] **Step 1: 检查当前 CI 与 SP-41 改动**

```bash
git fetch origin main
git diff -- .github/workflows/ci.yml
grep -nE 'check_catalog_locks|continue-on-error|scripts/tests' .github/workflows/ci.yml
```

必须保留 SP-41 的目录锁守卫和所有分支/PR 触发配置。

- [ ] **Step 2: 写 CI 静态失败测试**

在 `scripts/tests/test-deploy-p0-preflight.sh` 或新建 `scripts/tests/test-ci-deploy-preflight.sh` 中断言：

- CI 包含 `bash scripts/tests/test-preflight-production.sh`。
- CI 包含 `bash scripts/tests/test-deploy-p0-preflight.sh`。
- 这两个 step 附近没有 `continue-on-error: true`。
- SP-41 的 `check_catalog_locks.py --json --require-generated` 仍存在。

推荐新建：

```text
scripts/tests/test-ci-deploy-preflight.sh
```

- [ ] **Step 3: 运行测试并确认红灯**

```bash
bash scripts/tests/test-ci-deploy-preflight.sh
```

预期：失败，因为 CI 尚未调用这两个脚本。

- [ ] **Step 4: 修改 CI**

在 API Quality Gate 的依赖安装后、Ruff 前加入：

```yaml
      - name: Test production preflight scripts
        working-directory: .
        run: |
          bash scripts/tests/test-preflight-production.sh
          bash scripts/tests/test-deploy-p0-preflight.sh
```

不得添加 `continue-on-error`。

- [ ] **Step 5: 运行 CI 测试与 YAML 解析**

```bash
bash scripts/tests/test-ci-deploy-preflight.sh
python3 - <<'PY'
from pathlib import Path
import yaml

path = Path('.github/workflows/ci.yml')
data = yaml.safe_load(path.read_text(encoding='utf-8'))
assert isinstance(data, dict)
print('CI YAML OK')
PY
```

- [ ] **Step 6: 提交 Task 3**

```bash
git add .github/workflows/ci.yml scripts/tests/test-ci-deploy-preflight.sh
git commit -m "ci(deploy): 阻断 preflight 回归"
```

---

### Task 4: 更新运维文档与执行最终验收

**Files:**
- Modify: `docs/ops/production-restart.md`
- Modify: `docs/workflows/workflow-release-rollback-stable.md`

**Interfaces:**
- Consumes: Tasks 1-3 的真实脚本行为。
- Produces: 操作人员可直接执行的发布说明。

- [ ] **Step 1: 更新生产重启手册**

必须写明：

- A 代码发布自动运行 `scripts/preflight-production.sh`。
- 失败时在构建前停止。
- B 与 both 代码发布当前被拒绝。
- grants 模式不运行代码发布 preflight，但会替换 API 并重启 edge。
- dry-run 会连接生产执行只读检查，但不执行发布后验收。
- 抢修必须走独立 runbook，不提供 `--skip-preflight`。

- [ ] **Step 2: 更新发布回滚工作流文档**

区分：

```text
本地编排门禁：scripts/preflight-production.sh
生产主机内部门禁：scripts/deploy-preflight-scrapy.sh
```

说明二者都要执行，不是二选一。

- [ ] **Step 3: 字节级重写并检查文档**

```bash
python3 - <<'PY'
import os
from pathlib import Path

for name in (
    "docs/ops/production-restart.md",
    "docs/workflows/workflow-release-rollback-stable.md",
):
    path = Path(name)
    data = path.read_bytes().rstrip(b"\x00")
    if b"\x00" in data:
        raise SystemExit(f"embedded NUL: {name}")
    if not data.endswith(b"\n"):
        data += b"\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
PY
python3 scripts/check_file_integrity.py
git diff --check
grep -nE 'TBD|TODO|待定|待确认' \
  docs/ops/production-restart.md \
  docs/workflows/workflow-release-rollback-stable.md || true
```

- [ ] **Step 4: 运行全部离线门禁**

```bash
bash scripts/tests/test-preflight-production.sh
bash scripts/tests/test-deploy-p0-preflight.sh
bash scripts/tests/test-ci-deploy-preflight.sh
bash -n scripts/preflight-production.sh
bash -n scripts/deploy-p0.sh
```

- [ ] **Step 5: 运行真实只读 preflight**

前置条件：工作区干净，分支包含 `origin/main`。

```bash
bash scripts/preflight-production.sh
scripts/deploy-p0.sh --host a --dry-run
```

预期：

- preflight 输出 `ALL CHECKS PASSED`。
- dry-run 输出 `PASS production preflight A`。
- 没有远端写操作。
- 不执行 post-deploy `verify_public`。

- [ ] **Step 6: 故障注入验收**

离线测试已经覆盖脚本内部故障。补充直接命令：

```bash
SCRAPY_PUBLIC_URL=https://127.0.0.1:9 \
  bash scripts/preflight-production.sh
```

预期：非零退出，并输出公网健康失败。

不得向生产写入。

- [ ] **Step 7: 提交前图分析**

```bash
node /Users/lute/Project/data_scrapy/.gitnexus/run.cjs detect-changes \
  --scope compare --base-ref origin/main --repo /Users/lute/Project/data_scrapy-sp36
```

如果 `partial` 或 `truncated`，记录风险并补文本搜索。

- [ ] **Step 8: 提交文档与最终记录**

```bash
git add \
  docs/ops/production-restart.md \
  docs/workflows/workflow-release-rollback-stable.md
git commit -m "docs(deploy): 记录自动 preflight 门禁"
```

---

### Task 5: 全分支复核与票据状态建议

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes: Tasks 1-4 的提交。
- Produces: 合并结论与 SP-36 状态建议。

- [ ] **Step 1: 新鲜验证**

```bash
bash scripts/tests/test-preflight-production.sh
bash scripts/tests/test-deploy-p0-preflight.sh
bash scripts/tests/test-ci-deploy-preflight.sh
python3 scripts/check_file_integrity.py
git diff --check origin/main..HEAD
```

- [ ] **Step 2: 最终代码审查**

审查重点：

- A 失败是否能在任何生产写操作前停止。
- B/both 是否无绕过。
- grants 是否保持现状。
- dry-run 是否不会触发 post-deploy 验收。
- 测试是否完全离线。
- CI 是否保留 SP-41 门禁。
- preflight 是否可能假通过。

- [ ] **Step 3: 票据状态建议**

只有以下证据全部成立时，建议将 SP-36 标为「已完成」：

- 脚本与文档已合入 main。
- shell 测试在 CI 为阻断式。
- 真实 A preflight 与 A dry-run 通过。
- 故障注入确认 fail-closed。

本任务不直接更新飞书，由每日票据同步流程按证据更新。
