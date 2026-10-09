# 平台坑点策展源

每个平台一个 `<platform_id>.json`（稀疏——没有坑点的平台不需要文件）。
本目录**位于 API 包内**，因为 playbook / SKILL / README 是 API 请求时实时渲染的，
生成器与运行时都从这里读取（顶层 `configs/` 不在 api 镜像构建上下文里）。

## 文件格式

```json
{
  "platform_id": "x",
  "notes": [
    {
      "scope": "endpoint",
      "target": "tikhub_x_search",
      "symptom": "调用返回 upstream returned 400",
      "cause": "演示参数缺失或被上游拒绝",
      "workaround": "补齐 required_params，参考 manifest.json",
      "failure_class": "upstream_4xx",
      "severity": "warning",
      "verified_at": "2026-10-09",
      "source_ref": "reports/live-sweep/latest.json",
      "tags": ["tikhub"]
    }
  ]
}
```

- `scope`：`platform`（`target` = platform_id）或 `endpoint`（`target` = endpoint_type）。
- `severity`：`info` | `warning` | `blocker`。
- 顶层也可直接是 note 数组。

## 生效路径

1. 编辑本目录的 `*.json`。
2. `cd apps/api && uv run python ../../scripts/generate_platform_packages.py --update-lock`
   （notes 进 digest，必须同步 lock）。
3. 重新生成会把坑点渲染进 `SKILL.md` / `README.md` / `references/playbook.md` /
   `docs/playbooks/platforms/<id>.md`，并汇总到 `docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md`。
4. 部署后 `GET /api/platform-packages/<id>/playbook` 与 MCP `get_playbook` 返回带坑点的 Markdown，
   控制台 `/skills/<id>` 显示坑点卡片。

## 红线

- 不得写入任何密钥：`API_KEY=`、`PASSWORD=`、`SECRET=`、`Bearer ` 或私钥头。
  加载器会直接拒绝（`notes.py` 的 `_SECRET_MARKERS`）。
- `scope=endpoint` 的 `target` 必须是该平台真实存在的 endpoint_type。
