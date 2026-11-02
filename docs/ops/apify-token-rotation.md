# Apify / TikHub 凭证轮换清单（2026-11-02）

- 原因：5 个 Apify token 与 1 个 TikHub token 曾在会话中明文出现。没有轮换完成的证据。
- 目标：旧 token 全部失效；新 token 只进密钥文件与生产 env；仓库、记忆、图谱、日志 0 明文。
- 现状（2026-11-02 只读检查）：5 个 Apify token 全部有效；`t1`-`t4` 属于 `complex_homage`，`t5` 属于 `yueguz`；两个账号都是 SCALE 计划。

## 1. 轮换前检查

```bash
python3 scripts/check_apify_tokens.py
python3 scripts/check_apify_tokens.py --json
```

脚本只打印序号、账号、计划与状态，不打印 token。

## 2. Apify 控制台

1. 登录 `https://console.apify.com/`。
2. 对 `complex_homage` 与 `yueguz` 各创建 1 个新 token；命名带日期，例如 `source-20261102`。
3. 撤销 `t1`-`t5` 对应的旧 token。
4. 把新 token 写入 `~/.config/apify-lake/tokens.txt`，每行 `label token`，权限 600。
5. 再跑一次 `python3 scripts/check_apify_tokens.py`，确认只剩新 token。

## 3. 生产 A/B

每个主机执行：

```bash
# 只改 .env.production 的 APIFY_API_TOKEN，不要 echo 值到终端历史。
# 编辑后确认 compose 的 api 环境声明里含 APIFY_API_TOKEN。
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  up -d --no-deps api abi-export
```

如果需要让 `abi-ingest` 也使用新 token，重启对应容器。ABI `meta.apify_token` 表若存了密文，按 `docs/plans/abi-external-datacenter.md` 的 token 流程更新，并保留指纹与前四位。

## 4. TikHub

1. 登录 TikHub 控制台，撤销旧 key，创建新 key。
2. 更新 A/B 的 `TIKHUB_API_KEY`。
3. 重启 api；确认 `/api/tiktok/tools` 仍 401（鉴权正常），并跑一次最小工具调用。

## 5. 验收

| 检查 | 通过条件 |
|---|---|
| 旧 token | 控制台显示 revoked；旧 token 调用返回 401 |
| 新 token | `check_apify_tokens.py` 全部 valid |
| 明文扫描 | 仓库 `git grep -n "apify_api_"` 为 0；记忆与文档为 0 |
| 生产 | A/B `/api/health` ok；`abi-export` running |
| 调用 | 一次 Apify run 成功；一次 TikHub 工具调用返回 200 |

## 6. 不能做的事

- 不把新 token 写进仓库、记忆、图谱、工单或聊天。
- 不在共享 shell 历史里 `export TOKEN=...`；用文件或密钥管理。
- 不因为轮换而删除 `~/.config/apify-lake/tokens.txt` 的历史备份；先确认新 token 可用。