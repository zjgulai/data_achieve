---
name: dih-p0-delivery-2026-10-18
description: DIH 前端 P0 与采集外访策略的上线记录：改了什么、部署了什么、遗留什么
---

# DIH P0 交付记录（2026-10-18）

## 一句话

DIH 前端按新 IA 上线两套生产，同时启用采集外访策略的域名批准。
当前状态：新增路由全部可用，78 个端点被策略阻断（其中 21 行可争，已批 5 个主机）。

## 上线范围

代码提交 `512895a`，两台生产均为 `c9c441d`（`512895a` 只含文档与配置，无需重新部署）。

| 生产 | 域名 | 分支 |
|---|---|---|
| A | `https://scrapy.luteos.com` | `main` |
| B | `https://scrapy.lute-tlz-dddd.top` | `deploy/tiktok-cdo-codex` |

没有数据库迁移。没有新增依赖。

## 前端（`apps/scraper-console`）

### 新增路由

| 路由 | 内容 |
|---|---|
| `/tools` | 能力目录。契约驱动，替代原 `/platforms` |
| `/tools/[toolId]` | 平台详情 |
| `/docs` | 采集文档。证据状态改为五态 |
| `/connect` | 接入方式（REST / MCP / Skill） |
| `/settings/providers` | 提供方状态。原样呈现服务端六态可用性 |
| `/settings/members` | 成员与工作区。后端无成员接口，页面如实说明 |

旧路径全部重定向：`/platforms`、`/skills`、`/collector-docs`、`/datasets`、`/raw-records`、`/collect/:runId`。

### 修复的缺陷

- `providers` 页初版用 `resolveReachability` 派生，把 `degraded` 与 `empty` 压成「可用」。实测 236 与真实 209/17/10 不符。改为直接按服务端枚举计数。
- `/settings/providers` 与 `/settings/members` 曾在 `NEW_ROUTES` 声明但无页面，用户得到 404。补页面，并加测试断言「每条新路由必须有 page.tsx」。

## 采集外访策略

### 三态可达性

`policy_block_reason` 分两级：

- **类型级**：该采集器有没有有效的服务端域名批准。
- **主机级**：目标主机是否在批准列表内。

修前只做类型级，导致 15 行未批准主机的端点显示可用，点采集才失败。

修法是新增 `host_block_reason()`（`collectors/outbound_policy.py`），并给 24 个固定目标端点补齐 `param_fields["url"]`——此前 19 个 RSS 端点的 URL 只写在人类可读的 `description` 里，目录无法机读。

### 当前阻断

两台一致：286 行中 77 行被阻断。

| 原因 | 行数 | 能否恢复 |
|---|---|---|
| 永久不可达（`unsupported` 采集器） | 57 | 否，策略设计如此 |
| 主机未获批准 | 18 | 是，需轮换或拆类型 |
| 缺类型级批准（两个电商） | 2 | 是，需定白名单站点 |

`executable_count`：198 / 258。

### 已批准的主机

`COLLECTION_NETWORK_MODE=restricted`。

| collector | 主机 | 用了几 / 上限 |
|---|---|---|
| `public_feed` | gov.uk、fda.gov、prnewswire.com、babygaga.com、romper.com | 5 / 5 |
| `generic_web` | babycenter.com、babylist.com、forbes.com、goodhousekeeping.com、scrapingbee.com | 5 / 5 |

`scrapingbee.com` 是生产任务「竞品公开页面快照采集」的目标。移出会让该任务失败。

## 关键约束

**每个 collector 只能有一条配置，`hosts` 最多 5 个。** 追加第二条会让该类型全部被拒，不是扩容。

因此：`public_feed` 有 21 个唯一固定主机、`generic_web` 有 7 个，都不能一次批完。

已验证主机共 12 个（监管 4 + 媒体 8），轮换可覆盖。四份现成批次在 `configs/deploy/scrapy/grants/`，切换一条命令：

```bash
./scripts/deploy-p0.sh --host both \
  --grants-file configs/deploy/scrapy/grants/batch-1-regulatory.json
```

操作细节见 [受控 HTTP 域名批准手册](../standards/http-grant-runbook.md)。

## 发布工具

`scripts/deploy-p0.sh` 两种模式：

- 发布模式：拉源码、构建、替换 api 与 console、重启 edge、公网验收。
- 批准模式 `--grants-file`：只改外访批准，不构建镜像。校验、备份、写入、用真实策略代码验证、上线后对比阻断行数，上升则自动回滚。

两条防线来自实测的失败：

1. 不能用 `deploy_one ... || status=1`。那会让 bash 关闭函数体内的 `errexit`，任一步失败不中止，验收对旧代码同样返回 200，脚本打印「发布完成」。
2. 重建 api/console 后必须 `restart edge`。edge 的 nginx 静态解析主机名，容器换 IP 后公网 502，而容器健康检查仍通过。

## 本轮踩过的坑

| 现象 | 原因 |
|---|---|
| 部署后某任务每天失败 | 批准列表缺该任务的主机。策略拒绝不自动重试，`next_run_at` 被置空 |
| 改 host 后阻断行数不变 | 该主机不是目录固定端点，是任务自带 URL。看任务运行结果判断 |
| 批准后仍显示可用但采集失败 | 修前的类型级误报。已修 |
| `public_feed` 主机数写成 19 | 只统计了 `description` 里的 URL，漏了 `param_fields.url`。实际 21 |

## 遗留

| 项 | 说明 |
|---|---|
| 18 行主机未获批准 | 16 行是 `disabled` 端点，前端本就不放行；2 行（mumsnet、healthline）被批次 3 换出 |
| 2 个电商端点 | 目标由调用方传入，需先定白名单站点 |
| 57 个 `unsupported` 采集器 | 需要受控执行环境与出口验证，不是加布尔参数能放行的 |
| 12 个已验证主机不能同时可用 | 要突破需拆 `collector_type`。**HIGH 风险**：15–20 个文件，聚合主机上限从 5 抬到 10+，单次请求预算从 50 抬到 100+，属安全边界变更，需策略变更评审 |

## 验收命令

```bash
# 公网路由
for p in /api/tools /tools /docs /connect /settings/providers /settings/members; do
  printf '%-22s %s\n' "$p" "$(curl -sL -o /dev/null -w '%{http_code}' https://scrapy.luteos.com$p)"
done

# 阻断明细
curl -s https://scrapy.luteos.com/api/collectors/catalog | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [e for g in d["collectors"] for e in g["endpoints"]]
print("目录", len(rows), "被阻断", sum(1 for e in rows if e.get("policy_block_reason")))
'

# 容器内实际生效的批准
docker exec data_achieve_scrapy_api printenv COLLECTION_HTTP_GRANTS
```
