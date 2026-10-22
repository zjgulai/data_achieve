---
name: shusuo-secret-rotation
description: 数说飞书应用 App Secret 轮换步骤。轮换在飞书开发者后台完成，服务器侧用脚本更新。
---

# 数说 App Secret 轮换

## 结论

1. 飞书不提供公开的 App Secret 轮换 API。重置只能在飞书开发者后台完成。
2. 重置后旧 Secret 立即作废。不要回滚到旧值。
3. 服务器侧执行 `scripts/rotate-shusuo-secret.sh`。脚本先验证新 Secret，再写 env。
4. 写 env 后失败时保留新值，修好问题后继续，不回滚。

## 前置检查

1. 只有生产 A（`ubuntu@43.163.92.244`）执行。
2. `/api/agents/shusuo/health` 返回 `ready=true`。
3. 记录当前时间，预留 10 到 15 分钟维护窗口。

## 飞书后台

1. 打开飞书开发者后台，进入数说应用。
2. 进入「凭证与基础信息」。
3. 重置 App Secret。
4. 新 Secret 直接输入服务器隐藏提示，或存入密码管理器。不要发到聊天、工单或截图。

## 服务器

在项目根目录执行：

```bash
bash scripts/rotate-shusuo-secret.sh
```

脚本按以下顺序执行：

1. 从 env 读取 App ID。
2. 隐藏输入读取新 Secret。
3. 先用新 Secret 换取 tenant token。失败则退出，env 不变。
4. 原子替换 env，保留权限与属主。
5. 校验 compose 配置。
6. 强制重建 api，只重建 api。
7. 重启 edge，不重建 edge。
8. 轮询 `/api/agents/shusuo/health`，要求 `ready=true`。
9. 在容器内再用新 Secret 换一次 token。

## 失败处理

写 env 之前失败：env 不变。重新在飞书后台重置，再执行脚本。

写 env 之后失败：新 Secret 已生效，旧值已作废。不要回滚。按报错修好后执行：

```bash
curl -sS https://scrapy.luteos.com/api/agents/shusuo/health
```

需要时手工重建 api 并重启 edge：

```bash
cd /opt/data-achieve-scrapy/app
ENVF=/opt/data-achieve-scrapy/.env.production
CF=configs/deploy/scrapy/docker-compose.yml
docker compose --env-file "$ENVF" -f "$CF" up -d --no-deps --force-recreate api
docker compose --env-file "$ENVF" -f "$CF" restart edge
```

## 验收

1. `/api/agents/shusuo/health` 返回 `ready=true`。
2. `/api/health` 返回 200。
3. 在飞书私聊机器人发送「帮助」，能收到回复。
4. 日志没有 `shusuo_webhook_bad_signature`。

## 轮换后清理

1. 本机 `.env` 权限改为 `600`。
2. 扫描本机 Claude 会话文件与 shell 历史，确认旧 Secret 已被替换或删除。
3. 扫描生产日志与备份，确认没有旧 Secret 明文。
4. 旧 Secret 已作废。清理只降低残留风险，不能替代轮换。
