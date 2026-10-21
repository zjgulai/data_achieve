---
name: shusuo-secret-rotation
description: 数说飞书应用 App Secret 轮换步骤。轮换在飞书开发者后台完成，服务器侧用脚本更新。
---

# 数说 App Secret 轮换

## 结论

1. 飞书不提供公开的 App Secret 轮换 API。重置只能在飞书开发者后台完成。
2. 重置后立即执行 `scripts/rotate-shusuo-secret.sh`。脚本备份 env、更新密钥、重建 API、验证 tenant token。
3. 失败时脚本自动恢复旧 env 并重启 API。

## 前置检查

1. 只有生产 A（`ubuntu@43.163.92.244`）执行。
2. 当前 `/api/agents/shusuo/health` 返回 `ready=true`。
3. 已备份 `/opt/data-achieve-scrapy/.env.production`。

## 飞书后台

1. 打开飞书开发者后台，进入数说应用。
2. 进入「凭证与基础信息」。
3. 重置 App Secret。
4. 记录新 Secret，不写入聊天、不写入仓库。

## 服务器

在项目根目录执行：

```bash
bash scripts/rotate-shusuo-secret.sh
```

脚本提示时输入新 Secret。输入不回显。

脚本执行以下动作：

1. 备份 env 文件。
2. 替换 `LARK_SHUSUO_APP_SECRET`。
3. 校验 compose 配置。
4. 只重建 api，不动 edge。
5. 轮询 `/api/agents/shusuo/health`。
6. 用新 Secret 换取 tenant token。
7. 任一步失败时恢复备份并重启。

## 验收

1. `/api/agents/shusuo/health` 返回 `ready=true`。
2. `/api/health` 返回 200。
3. 在飞书私聊机器人发送「帮助」，能收到回复。
4. 日志没有 `shusuo_webhook_bad_signature`。

## 回滚

脚本失败会自动回滚。手工回滚：

```bash
cp /opt/data-achieve-scrapy/.env.production.bak.<stamp> /opt/data-achieve-scrapy/.env.production
cd /opt/data-achieve-scrapy/app
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml up -d api
```
