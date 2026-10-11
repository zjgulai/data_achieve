---
name: production-sync-revision
description: "把生产主机（A：scrapy.luteos.com / B：scrapy.lute-tlz-dddd.top）的代码同步到指定 revision。Use when 发布前同步生产源码、生产落后于 GitHub、或 git fetch 失败/超时/报 GnuTLS 错误时。涵盖 GitHub 抖动重试参数、bundle 兜底、ff-only 同步与验证。"
---

# 生产代码同步

## 适用场景

- 发布前把生产主机同步到目标 revision。
- 生产落后于 GitHub，需要对齐。
- `git fetch` 失败：GnuTLS 错误、超时、速度过慢。

## 环境事实

| 项 | 生产 A | 生产 B |
|---|---|---|
| 主机 | `ubuntu@43.163.92.244` | `ubuntu@101.34.52.232` |
| 密钥 | `zhoujian_pachong.pem` | `DDDD.pem` |
| 分支 | `main` | `deploy/tiktok-cdo-codex` |
| 域名 | `scrapy.luteos.com` | `scrapy.lute-tlz-dddd.top` |

共同：代码路径 `/opt/data-achieve-scrapy/app`。生产主机只读。不在生产工作区提交或改文件。

## 步骤

### 1. 记录起点

先记录当前 revision。这是回滚锚点。

```bash
cd /opt/data-achieve-scrapy/app
git log -1 --format='%h %s'
git status --porcelain; echo "[porcelain 结束]"
```

工作区必须干净。有输出就先停下，问用户。不要清理他人的改动。

### 2. fetch（带重试）

生产 B 到 GitHub 经常失败。必须重试。参数必须加上。

```bash
ok=0
for i in 1 2 3 4 5; do
  out=$(git -c http.version=HTTP/1.1 \
            -c http.lowSpeedLimit=1000 \
            -c http.lowSpeedTime=20 \
            fetch origin <分支> 2>&1); rc=$?
  [ $rc = 0 ] && ok=1 && break
  echo "第 $i 次失败: $(echo "$out" | tail -1)"
  sleep 4
done
[ $ok = 1 ] || echo FETCH_FAILED
```

通常第 2 到 4 次成功。

### 3. 同步

用 ff-only。它非破坏性。工作区有冲突改动时它会拒绝。

```bash
git merge --ff-only FETCH_HEAD
```

不要用 `git reset --hard`。它丢弃工作区内容。权限分类器也会拦它。

若本地分支无 upstream，`git pull` 会静默返回 "Already up to date"。不要用 `git pull`。

### 4. 验证

```bash
git log -1 --format='%h %s'
git status --short --branch
```

revision 必须与目标一致。分支状态必须干净。

## 兜底：bundle 传输

fetch 重试全部失败时，改用增量 bundle。

本地执行：

```bash
git bundle create /tmp/deploy-<短SHA>.bundle <旧rev>..<分支>
git bundle verify /tmp/deploy-<短SHA>.bundle
scp -i <密钥> /tmp/deploy-<短SHA>.bundle ubuntu@<主机>:/tmp/
```

服务器执行：

```bash
cd /opt/data-achieve-scrapy/app
git fetch /tmp/deploy-<短SHA>.bundle <分支>
git merge --ff-only FETCH_HEAD
rm -f /tmp/deploy-<短SHA>.bundle
```

传输后核对 revision。bundle 的起点必须是服务器上已有的 revision。

## 坑点

1. **不要把 fetch 管道给 `tail` 等命令。** 管道会吞掉退出码。`&& break` 会在第一次失败时触发。
2. **不要用 `reset --hard`。** 用 `merge --ff-only`。它更安全，也能过权限检查。
3. **`--single-branch` 克隆有历史包袱。** 这类仓库的 `origin/<分支>` 可能不存在。修复：`git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"`，再 fetch。
4. **后台构建用 nohup 时给 stdin 接 `/dev/null`。** 否则 ssh 会话不返回。
5. **`pkill -f "docker compose.*build"` 会自匹配。** 远程 shell 的命令行含同样文本。模式写成 `[c]ompose`，例如 `docker [c]ompose.*build`。

## 完成后

发布时继续 `.claude/skills/production/production-image-build/`。验收用 `.claude/skills/production/production-acceptance/`。
