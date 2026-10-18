---
name: http-grant-runbook
description: 批准受控 HTTP 采集域名的操作步骤、分批规则与验收方法
---

# 受控 HTTP 域名批准手册

## 适用场景

本文用于批准 `generic_web`、`public_feed`、`ecommerce_product_page`、
`ecommerce_product_discovery` 四类采集器的外访域名。

策略本身见 [采集外访安全边界](./collection-outbound-safety.md)。本文只写操作。

## 三条硬约束

开工前先记住这三条。违反任一条，配置不会生效或会让整类采集被拒。

1. **每个 collector 只能有一条配置。** 写两条时，该类型的全部请求都被拒。
2. **每条配置最多 5 个主机。** 没有通配符。子域不自动包含。
3. **改 `.env.production` 必须改 compose。** 生产 Compose 用显式变量列表。
   只写 `.env.production` 不会进容器。

## 第 1 步：确认要批准哪些主机

先看目录里哪些端点缺批准。

```bash
curl -s https://scrapy.luteos.com/api/collectors/catalog \
  | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [e for g in d["collectors"] for e in g["endpoints"]]
for e in rows:
    reason = e.get("policy_block_reason") or ""
    if "域名批准" in reason:
        print(e["endpoint_type"], "|", e["status"], "|", e.get("label"))
'
```

`status` 为 `disabled` 的端点不要批准。前端只放行 `verified` 的端点。

记录每个端点访问的精确主机名。主机名写在端点说明（`description`）里。

## 第 2 步：确认主机名合法

用项目虚拟环境验一遍。不合法的主机会让该类采集全部被拒。

```bash
cd apps/api && ./.venv/bin/python -c '
from data_intelligence_hub.collectors.outbound_policy import canonical_host
for h in ["www.forbes.com"]:
    print(canonical_host(h))
'
```

规则：小写、不含端口与路径、不是 IP、不以 `.local` 或 `.onion` 结尾、必须含点。

## 第 3 步：写配置文件

写一个 JSON 文件。不要直接改 `.env.production`，也不要写进命令行。

`/tmp/grants.json`：

```json
[
  {
    "collector_type": "public_feed",
    "hosts": ["www.forbes.com", "www.nytimes.com"],
    "expires_at": "2027-01-15T00:00:00Z",
    "max_requests": 50,
    "max_domains": 2,
    "timeout_seconds": 60
  }
]
```

字段要求：

| 字段 | 取值 |
|---|---|
| `collector_type` | 四类之一。必须精确匹配 |
| `hosts` | 1 到 5 个主机名。不带协议、路径、端口 |
| `expires_at` | 带时区的 ISO 8601。过期即拒 |
| `max_requests` | 1 到 50。单次运行的请求上限 |
| `max_domains` | 1 到 5，且不小于 `hosts` 的数量 |
| `timeout_seconds` | 大于 0，不超过 60 |

`max_domains` 写在 `hosts` 之前容易出错。先定 `hosts` 的数量，再把 `max_domains` 写成同一个数。

## 第 4 步：确认 Compose 已接住变量

`configs/deploy/scrapy/docker-compose.yml` 的 api 服务必须有这两行：

```yaml
COLLECTION_NETWORK_MODE: ${COLLECTION_NETWORK_MODE:-restricted}
COLLECTION_HTTP_GRANTS: ${COLLECTION_HTTP_GRANTS:-[]}
```

默认值必须写 `:-[]`。未设置或空串会让服务启动失败。

2026-10-17 起这两行已在仓库里。脚本会先检查，缺失时拒绝执行。

## 第 5 步：用脚本上线

脚本会完成剩下的所有步骤。

```bash
# 先看要做什么
./scripts/deploy-p0.sh --host both --grants-file /tmp/grants.json --dry-run

# 正式执行
./scripts/deploy-p0.sh --host both --grants-file /tmp/grants.json
```

脚本按以下顺序执行，任一步失败即中止：

1. 校验 JSON 结构。检查类型是否合法、是否重复、主机数量与字段范围。
2. 读取当前被阻断行数，作为基线。
3. 上传批准文件到远端，用文件传输而非命令行参数。
4. 备份 `.env.production`，保留原权限与属主。
5. 原子替换文件里那一行 `COLLECTION_HTTP_GRANTS`。
6. 用镜像里的真实策略代码验证。失败则恢复备份，容器不动。
7. 替换 api 容器，重启 edge。
8. 等 api 健康。
9. 重新取被阻断行数。若上升，自动回滚并报错。

只有脚本会做第 9 步。手工改配置时没有这道兜底。

## 第 6 步：手工执行时要注意什么

若不用脚本，按下面的顺序做。顺序错了会让服务起不来。

```bash
cd /opt/data-achieve-scrapy/app
envf=/opt/data-achieve-scrapy/.env.production
compose="docker compose --env-file $envf -f configs/deploy/scrapy/docker-compose.yml"

# 1. 备份
cp -p "$envf" "$envf.bak.$(date +%Y%m%dT%H%M%S)"

# 2. 改那一行（保持文件权限）
#    用编辑器改，或先删后追加
grep -v '^COLLECTION_HTTP_GRANTS=' "$envf" > "$envf.new"
printf 'COLLECTION_HTTP_GRANTS=%s\n' '<一行 JSON>' >> "$envf.new"
chown --reference="$envf" "$envf.new" && chmod --reference="$envf" "$envf.new"
mv "$envf.new" "$envf"

# 3. 先验证再上线
$compose run --rm --no-deps -T api python -c \
  'from data_intelligence_hub.collectors.outbound_policy import http_grant; import json,os; [http_grant(g["collector_type"]) for g in json.loads(os.environ["COLLECTION_HTTP_GRANTS"])]; print("ok")'

# 4. 重建 api
$compose up -d --no-deps api
$compose restart edge
```

`get_settings()` 有进程内缓存。改环境变量不会热加载，必须重建容器。

不要用 `restart api`。`restart` 不重新读取 `--env-file` 的变量，容器拿到的仍是旧值。要用 `up -d --no-deps api`。

```bash
cd /opt/data-achieve-scrapy/app
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml up -d --no-deps api
```

只重启 api。不要重建 console 或 edge。

## 第 7 步：验收

```bash
curl -s https://scrapy.luteos.com/api/collectors/catalog \
  | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [e for g in d["collectors"] for e in g["endpoints"]]
blocked = [e for e in rows if e.get("policy_block_reason")]
print("被阻断行:", len(blocked))
for e in blocked[:5]:
    print(" ", e["endpoint_type"], "|", e["policy_block_reason"])
'
```

被阻断的行数应当下降。若反而上升，说明配置写错，该类型被整体拒绝。

再看 `providers/status` 里对应端点的 `availability`。
`config-gated` 应当变成 `verified` 或其他真实状态。

## 第 8 步：分批轮换

超过 5 个主机时只能分批。每批是一份现成的配置文件，放在
`configs/deploy/scrapy/grants/`。切换是一条命令：

```bash
./scripts/deploy-p0.sh --host both \
  --grants-file configs/deploy/scrapy/grants/batch-1-regulatory.json
```

先加 `--dry-run` 看它要做什么。

### 现有批次

| 文件 | `public_feed` 的主机 | 用途 |
|---|---|---|
| `batch-0-fix-generic-web.json` | forbes、nytimes、goodhousekeeping、momjunction、madeformums | 母婴媒体基线。`generic_web` 含 scrapingbee |
| `batch-1-regulatory.json` | gov.uk、fda.gov、prnewswire、mumsnet、healthline | 监管源优先。当前生产在用 |
| `batch-2-media.json` | 同 batch-0 | 回切到母婴媒体 |
| `batch-3-remaining.json` | gov.uk、fda.gov、prnewswire、babygaga、romper | 补齐剩余两个已验证媒体源 |

`generic_web` 四份都相同：babycenter、babylist、forbes、goodhousekeeping、scrapingbee。
其中 `scrapingbee.com` 是生产任务「竞品公开页面快照采集」的目标，移出会让该任务失败。

### 轮换前必须确认

换出某个主机前，先确认没有任务依赖它。策略拒绝不会自动重试，
任务会在下次执行时失败，并把 `next_run_at` 置空。

```bash
curl -s https://scrapy.luteos.com/api/tasks | python3 -c '
import json, sys
tasks = json.load(sys.stdin)
for t in tasks:
    if t.get("collector_type") not in ("public_feed", "generic_web"):
        continue
    url = (t.get("config") or {}).get("url") or t.get("source_url") or ""
    host = url.split("//")[-1].split("/")[0].lower()
    print(t["name"], "|", host, "| next:", t.get("next_run_at"))
'
```

2026-10-18 实测：全库 577 个任务的 `schedule_cron` 全为空，
唯一依赖 `public_feed` 的任务采集 `hnrss.org`（未批准），
唯一依赖 `generic_web` 的定时任务采集 `www.scrapingbee.com`。

### 换出后再换回会怎样

不会自动恢复。任务收到 `collection_policy_denied` 或
`outbound_domain_denied` 后，`next_run_at` 变为空，scheduler 不重试。
需要手动跑一次成功，调度才回来：

```bash
curl -s -X POST https://scrapy.luteos.com/api/tasks/<task_id>/run
```

## 常见错误

| 现象 | 原因 |
|---|---|
| 该类全部被拒 | 写了两条同 `collector_type` 的配置 |
| 改环境变量后无效 | 没重启 api，或没改 compose |
| 服务起不来 | 默认值写成 `${VAR}` 而不是 `${VAR:-[]}` |
| 主机名被拒 | 带了端口、路径、大写或 IP |
| 批准了仍被拒 | 端点 `status` 是 `disabled`，前端不放行 |
| 改 host 后被阻断行数没变 | 该主机不是目录固定端点，是任务自带 URL。看任务运行结果判断 |
| 任务每天失败一次 | 目标主机未批准。查容器里 `COLLECTION_HTTP_GRANTS` 的实际值 |

## 2026-10-17 的实测基线

供后续判断变化。

| collector | 待批主机 | 上限 | 能否一次批完 |
|---|---|---|---|
| `public_feed` | 21 | 5 | 否 |
| `generic_web` | 7（2 个端点 disabled） | 5 | 否 |
| `ecommerce_product_page` | 由调用方传入 | 5 | 需先定站点 |
| `ecommerce_product_discovery` | 由调用方传入 | 5 | 需先定站点 |

该日上线后，两套生产各有 89 行被策略阻断。
其中 32 行缺域名批准，57 行永久不可达。
