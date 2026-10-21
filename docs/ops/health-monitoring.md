# 生产 A 健康监控与飞书告警

本文说明生产 A 的定时健康检查、告警规则和操作方法。

## 范围

监控脚本在 API 容器内运行。它检查生产 A 的公开端点，不检查生产 B。

检查项：

| 检查名 | 端点 | 通过条件 |
| --- | --- | --- |
| `health` | `/api/health` | HTTP 200；`database=connected`；`schema_revision=202610210051`；`schema=current` |
| `collectors_docs` | `/api/collectors/docs` | HTTP 200 |
| `platform_packages` | `/api/platform-packages` | HTTP 200 |
| `tools` | `/api/tools` | HTTP 200 或 401 |
| `mcp_auth` | `/mcp/` | HTTP 401 |

`/api/tools` 允许 200 或 401，是因为不同环境的鉴权配置不同。
`/mcp/` 必须是 401，用于确认 MCP 入口没有裸奔。

脚本输出的 JSON 含每项检查的 `status_code`、`detail` 和 `elapsed_ms`。

## 运行

在宿主机上执行单次检查：

```bash
cd /opt/data-achieve-scrapy/app
docker exec data_achieve_scrapy_api \
  python -m data_intelligence_hub.maintenance.prod_health_check
```

退出码：

- `0`：全部检查通过。
- `1`：至少一项检查失败。

脚本向 stdout 打印一行紧凑 JSON。示例：

```json
{"alert":{"disabled":false,"reason":"healthy","sent":false,"should_alert":false},"base_url":"http://127.0.0.1:8000","checked_at":"2026-10-21T04:00:00+00:00","checks":[{"detail":"","elapsed_ms":32,"name":"health","ok":true,"status_code":200,"url":"http://127.0.0.1:8000/api/health"}],"status":"ok"}
```

## 定时任务

安装 cron。每 10 分钟运行一次：

```bash
sudo bash scripts/install-health-cron.sh
```

脚本写入当前用户的 crontab。重复执行安全：已有同一条命令时不再追加。

cron 行：

```cron
*/10 * * * * cd /opt/data-achieve-scrapy/app && docker exec data_achieve_scrapy_api python -m data_intelligence_hub.maintenance.prod_health_check >> /var/log/scrapy-health.log 2>&1
```

确认安装结果：

```bash
crontab -l | grep scrapy-health
```

查看日志：

```bash
tail -f /var/log/scrapy-health.log
```

日志只追加。长期运行后按需轮转，例如用 `logrotate`。

## 配置

脚本从环境变量读取配置。默认值适用于生产 A。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SCRAPY_HEALTH_BASE_URL` | `http://127.0.0.1:8000` | 被检查的 API 根地址 |
| `SCRAPY_HEALTH_EXPECTED_SCHEMA` | `202610210051` | 期望的 Alembic schema revision |
| `SCRAPY_HEALTH_STATE_FILE` | `/tmp/scrapy_health_state.json` | 告警去重状态文件 |
| `HEALTH_ALERT_OPEN_IDS` | `ou_b49d21f41d8b2f119e466d29782d29ff` | 告警接收人 open_id，逗号分隔 |
| `HEALTH_ALERTS_DISABLED` | 未设置 | 设为 `1` 时只检查、不发送飞书消息 |
| `LARK_SHUSUO_APP_ID` | 无 | 数说机器人 App ID |
| `LARK_SHUSUO_APP_SECRET` | 无 | 数说机器人 App Secret |

默认接收人是周健（`ou_b49d21f41d8b2f119e466d29782d29ff`）。

`LARK_SHUSUO_APP_ID` 和 `LARK_SHUSUO_APP_SECRET` 已在 `configs/deploy/scrapy/docker-compose.yml`
的 `environment` 列表内。覆盖其他变量时，也要把变量加入该列表，否则容器内不可见。
只做一次性临时覆盖时，可用 `docker exec -e` 传给单次执行。

## 告警规则

告警通过数说机器人发送飞书文本消息。消息含失败检查名、HTTP 状态、错误详情、
检查时间、API 地址和多维表格链接：

<https://momcozy-in.feishu.cn/base/XXz5bHAwCa7qv5sTzrCci3jPnxd?table=tbli8kAkAqrndUvJ>

发送时机：

1. 状态从健康变为失败时，立即发送。
2. 失败检查集合变化时，立即发送。这视为新的故障。
3. 同一故障持续时，每 6 小时重发一次。
4. 恢复健康时，不发送消息，并清空失败状态。

状态文件默认是 `/tmp/scrapy_health_state.json`。字段：

| 字段 | 说明 |
| --- | --- |
| `status` | `healthy` 或 `failed` |
| `failed_since` | 本轮故障开始时间 |
| `failed_checks` | 本轮失败的检查名 |
| `last_alert_at` | 上次成功发送告警的时间 |
| `updated_at` | 上次检查时间 |

状态文件写入是原子的：先写临时文件，再 `os.replace` 覆盖。

容器重启后 `/tmp` 丢失。若故障仍在，下一轮会再次发送一次“首次失败”告警。
这是预期行为。

## 静默告警

临时静默：在 compose 的 `environment` 列表加入 `HEALTH_ALERTS_DISABLED: "1"`，
然后重建容器。检查仍会运行，退出码仍反映健康状态，但不发送飞书消息。

恢复告警：删除该键并重建容器。

完全停止检查：

```bash
crontab -l | grep -v "prod_health_check" | crontab -
```

只暂停时不要删除状态文件。恢复后会沿用已记录的 `last_alert_at`，避免重复告警。

## 排查

1. 查看 `/var/log/scrapy-health.log` 的 JSON 行。
2. 看 `checks[].detail`。`ConnectError` 表示请求未到达 API。
3. 看 `alert.error`。这里记录飞书取 token 或发消息的错误。
4. 看 `state_error`。这里记录状态文件写入错误。
5. 手工执行一次上面的 `docker exec` 命令，确认 API 容器在运行。

飞书发送失败不会改变退出码。失败详情只写入 JSON 和日志。
