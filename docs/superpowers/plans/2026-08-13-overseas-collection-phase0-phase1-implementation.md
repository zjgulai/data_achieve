---
title: 海外数据采集能力打通实施计划 Phase 0 + Phase 1
doc_type: plan
status: approved
created: 2026-08-13
owner: self
scope: phase0_migration + phase1_tikhub + phase1_apify
provider_call: true
production_boundary: phase0_read_only_then_migration; phase1_new_collectors_only
---

# 海外数据采集能力打通实施计划

## 决策记录

- 决策 1：不使用 YouTube 官方 API Key，主路线为 TikHub + Apify，Browser/Agent 兜底
- 决策 2：TikHub 和 Apify 同步推进，都接入
- 决策 3：生产 migration 先推 Batch 1（023→033），验证稳定后推 Batch 2（035 credential vault）

---

## Phase 0：生产 Migration 同步（Batch 1）

### 目标

把生产 schema 从 `202606110023` 推进到 `202606110033`，消除本地与生产的主要功能 gap，同时为 Phase 1 collector 接入打好数据库基础。

### 范围分析

Batch 1 覆盖的 revision（023 → 033）：

| Revision | 内容 | 破坏性 |
|---|---|---|
| `202606110024` | email_channel_test_runs 表 | 无，纯新增 |
| `202606110025` | email_provider_live_gate_runs 表 | 无，纯新增 |
| `202606110026` | email_provider_live_send_runs 表 | 无，纯新增 |
| `202606110027` | workflow_plan_persistence 表 | 无，纯新增 |
| `202606110028` | capability_governance 表 | 无，纯新增 |
| `202606110029` | workflow_execution_fixture 表 | 无，纯新增 |
| `202607160030` | plan_clone_scope_templates 表 | 无，纯新增 |
| `202607160031` | workflow_template_lifecycle 表 | 无，纯新增 |
| `202607160032` | workflow_template_revision_association | 无，纯新增 |
| `202607160033` | workflow_raw_dataset_lineage（RawRecord/DatasetVersion provenance 列） | **注意：ALTER TABLE，需要核验** |

**特别注意 revision 033**：该 revision 对 `raw_records` 和 `dataset_versions` 表新增列，属于 ALTER TABLE。需要在 staging 先验证，确认为 nullable 新增列无默认值冲突后再推生产。

### 执行步骤

#### 步骤 0-1：在本地验证 Batch 1 migration 链

```bash
# 启动隔离 PostgreSQL 容器
docker run -d \
  --name data-scrapy-phase0-batch1-verify \
  -e POSTGRES_DB=phase0_batch1_test \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 55445:5432 \
  postgres:15

# 等待容器就绪
sleep 3

# 设置测试目标并执行 migration
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:55445/phase0_batch1_test"
cd apps/api
uv run alembic upgrade 202606110033

# 验证 head
uv run alembic heads
# 期望输出：202606110033 (head)

# 验证 revision 033 的新增列存在
# raw_records 表应有 workflow_run_id, workflow_step_run_id 等新列
# dataset_versions 表应有对应的 provenance 列

# 测试降级路径
uv run alembic downgrade 202606110023
uv run alembic upgrade 202606110033

# 清理
docker stop data-scrapy-phase0-batch1-verify
docker rm data-scrapy-phase0-batch1-verify
```

期望结果：migration 双向通过，revision 033 新增列为 nullable，无约束冲突。

#### 步骤 0-2：准备生产部署包

```bash
# 在本地打包当前代码（含 migration 文件）
cd /opt/data-achieve-scrapy
git fetch origin main
git log --oneline origin/main -5  # 确认最新 commit

# 确认生产当前状态
curl https://scrapy.lute-tlz-dddd.top/api/health
# 期望：schema_revision=202606110023, status=ok
```

#### 步骤 0-3：生产执行 Batch 1 migration

```bash
# SSH 进生产服务器
# 1. 备份数据库快照
docker exec data_achieve_scrapy_db pg_dump -U postgres data_intelligence_hub \
  > /opt/data-achieve-scrapy/backups/pre_batch1_$(date +%Y%m%d_%H%M%S).sql

# 2. 拉取最新代码（到 revision 033 对应的 commit）
cd /opt/data-achieve-scrapy/app
git pull origin main

# 3. 执行 migration（目标 head 033）
docker exec data_achieve_scrapy_api \
  uv run alembic upgrade 202606110033

# 4. 验证
curl https://scrapy.lute-tlz-dddd.top/api/health
# 期望：schema_revision=202606110033, status=ok, database=connected

# 5. 验证 API 正常工作
curl -s https://scrapy.lute-tlz-dddd.top/api/automation/platform-packages | python3 -m json.tool
```

### 成功标准

- [ ] `GET /api/health` 返回 `schema_revision=202606110033`
- [ ] `GET /api/health` 返回 `status=ok, database=connected`
- [ ] GitHub API collector 正常工作（创建一个 Source 并运行验证）
- [ ] RSS collector 正常工作
- [ ] 现有 `/dashboard` 等页面全部返回 200

---

## Phase 1A：TikHub Collector 接入

### 目标

实现 TikHub REST API 的通用 collector，覆盖 TikTok / Instagram / 小红书三个平台，打通从 Source → Task → RawRecord → EntitySnapshot → Signal 的完整链路。

### 架构位置

```
新增文件：
  apps/api/src/data_intelligence_hub/collectors/tikhub_social.py
  
修改文件：
  apps/api/src/data_intelligence_hub/collectors/registry.py
  apps/api/.env.example（新增 TIKHUB_API_KEY 说明）
```

**设计原则：**
- 遵循现有 `BaseCollector` 接口，不引入新的抽象层
- API Key 从环境变量读取（`TIKHUB_API_KEY`），Phase 2 后接入 credential vault
- 输出 `CollectorRawRecord`，复用现有的 `collector_service.py` 处理链路
- 不修改 `social_api/` 下任何 disabled 相关代码
- 错误处理复用 `collector_http_error_message()` 模式

### TikHub API 端点覆盖（P0）

| collector_type | TikHub 端点 | 数据 | 输入参数 |
|---|---|---|---|
| `tikhub_tiktok_video_search` | `/api/v1/tiktok/app/v3/fetch_search_result` | TikTok 视频搜索 | `keyword`, `count`, `cursor` |
| `tikhub_tiktok_user_posts` | `/api/v1/tiktok/app/v3/fetch_user_post` | TikTok 账号视频 | `unique_id`, `count`, `cursor` |
| `tikhub_tiktok_hashtag_posts` | `/api/v1/tiktok/app/v3/fetch_hashtag_video` | TikTok 话题视频 | `ch_id`, `count`, `cursor` |
| `tikhub_instagram_user_posts` | `/api/v1/instagram/web_app/fetch_user_post_by_username` | Instagram 账号帖子 | `username`, `end_cursor` |
| `tikhub_instagram_search` | `/api/v1/instagram/web_app/fetch_search_result` | Instagram 搜索 | `keyword` |
| `tikhub_xiaohongshu_search` | `/api/v1/xiaohongshu/web/search_notes` | 小红书笔记搜索 | `keyword`, `page`, `page_size` |

**TikHub API 基础信息：**
- Base URL: `https://api.tikhub.io`
- 认证：`Authorization: Bearer <TIKHUB_API_KEY>`
- 频率限制：根据套餐，一般 10 req/s
- 计费：按 API 调用次数，约 $0.001-0.002/call

### 实现代码

#### `apps/api/src/data_intelligence_hub/collectors/tikhub_social.py`

```python
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
    require_text,
)

TIKHUB_BASE_URL = "https://api.tikhub.io"
TIKHUB_TIMEOUT = 30.0
TIKHUB_MAX_RETRY = 2
TIKHUB_RETRY_BACKOFF = (1.0, 3.0)

# collector_type → (endpoint_path, record_type, platform)
TIKHUB_ENDPOINT_MAP: dict[str, tuple[str, str, str]] = {
    "tikhub_tiktok_video_search":   ("/api/v1/tiktok/app/v3/fetch_search_result",            "tiktok_video",      "tiktok"),
    "tikhub_tiktok_user_posts":     ("/api/v1/tiktok/app/v3/fetch_user_post",                 "tiktok_video",      "tiktok"),
    "tikhub_tiktok_hashtag_posts":  ("/api/v1/tiktok/app/v3/fetch_hashtag_video",             "tiktok_video",      "tiktok"),
    "tikhub_instagram_user_posts":  ("/api/v1/instagram/web_app/fetch_user_post_by_username", "instagram_post",    "instagram"),
    "tikhub_instagram_search":      ("/api/v1/instagram/web_app/fetch_search_result",          "instagram_post",    "instagram"),
    "tikhub_xiaohongshu_search":    ("/api/v1/xiaohongshu/web/search_notes",                  "xiaohongshu_note",  "xiaohongshu"),
}


def _get_api_key() -> str:
    key = os.getenv("TIKHUB_API_KEY", "").strip()
    if not key:
        raise CollectorError("tikhub_api_key_missing: TIKHUB_API_KEY env var not set")
    return key


def _tikhub_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "DataIntelligenceHub/1.0",
    }


async def _tikhub_get(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    """单次 TikHub GET，带有限次 retry。"""
    url = f"{TIKHUB_BASE_URL}{path}"
    last_exc: Exception | None = None
    for attempt in range(TIKHUB_MAX_RETRY + 1):
        try:
            resp = await client.get(
                url,
                params={k: v for k, v in params.items() if v is not None},
                headers=_tikhub_headers(api_key),
                timeout=TIKHUB_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise CollectorError("tikhub_response_invalid: expected JSON object")
            return data
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < TIKHUB_MAX_RETRY and _is_retryable(exc):
                await asyncio.sleep(TIKHUB_RETRY_BACKOFF[attempt])
                continue
            raise CollectorError(collector_http_error_message(exc)) from exc
    raise CollectorError(f"tikhub_retry_exhausted: {last_exc}")


def _is_retryable(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


# ──────────────────────────────────────────
# 规范化函数：各平台 → CollectorRawRecord
# ──────────────────────────────────────────

def _normalize_tiktok_video(item: dict[str, Any], collector_type: str) -> CollectorRawRecord | None:
    """TikTok 视频条目规范化。"""
    video_id = (
        item.get("aweme_id")
        or item.get("id")
        or (item.get("video") or {}).get("id")
    )
    if not isinstance(video_id, str) or not video_id.strip():
        return None
    video_id = video_id.strip()

    desc = item.get("desc") or item.get("text") or ""
    author = item.get("author") or {}
    stats = item.get("statistics") or item.get("stats") or {}
    video_meta = item.get("video") or {}

    return CollectorRawRecord(
        record_type="tiktok_video",
        source_url=f"https://www.tiktok.com/@{author.get('unique_id', 'unknown')}/video/{video_id}",
        content={
            "provider": "tikhub",
            "platform": "tiktok",
            "collector_type": collector_type,
            "schema_version": "tikhub_tiktok_video.v1",
            "video_id": video_id,
            "text": str(desc)[:2000],
            "author_id": str(author.get("uid") or author.get("id") or ""),
            "author_username": str(author.get("unique_id") or ""),
            "author_nickname": str(author.get("nickname") or ""),
            "created_at": _safe_ts(item.get("create_time")),
            "play_count":    _safe_int(stats.get("play_count")),
            "like_count":    _safe_int(stats.get("digg_count") or stats.get("like_count")),
            "comment_count": _safe_int(stats.get("comment_count")),
            "share_count":   _safe_int(stats.get("share_count")),
            "collect_count": _safe_int(stats.get("collect_count")),
            "duration":      _safe_int(video_meta.get("duration")),
            "cover_url":     _safe_str((video_meta.get("cover") or {}).get("url_list", [None])[0]),
            "music_title":   _safe_str((item.get("music") or {}).get("title")),
            "hashtags": [
                ch.get("cha_name") or ch.get("title") or ""
                for ch in (item.get("cha_list") or item.get("challenges") or [])
                if isinstance(ch, dict)
            ][:20],
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_instagram_post(item: dict[str, Any], collector_type: str) -> CollectorRawRecord | None:
    """Instagram 帖子规范化。"""
    post_id = (
        item.get("id")
        or item.get("pk")
        or item.get("shortcode")
    )
    if not isinstance(post_id, str | int) or not str(post_id).strip():
        return None
    post_id_str = str(post_id).strip()
    shortcode = item.get("shortcode") or item.get("code") or post_id_str

    caption_data = item.get("caption") or {}
    caption = (
        caption_data.get("text")
        if isinstance(caption_data, dict)
        else str(caption_data or "")
    )
    user = item.get("user") or item.get("owner") or {}

    return CollectorRawRecord(
        record_type="instagram_post",
        source_url=f"https://www.instagram.com/p/{shortcode}/",
        content={
            "provider": "tikhub",
            "platform": "instagram",
            "collector_type": collector_type,
            "schema_version": "tikhub_instagram_post.v1",
            "post_id": post_id_str,
            "shortcode": str(shortcode),
            "caption": str(caption or "")[:2000],
            "author_id": str(user.get("pk") or user.get("id") or ""),
            "author_username": str(user.get("username") or ""),
            "media_type": _safe_str(item.get("media_type") or item.get("type")),
            "like_count":    _safe_int(item.get("like_count")),
            "comment_count": _safe_int(item.get("comment_count")),
            "taken_at":      _safe_ts(item.get("taken_at")),
            "hashtags": _extract_hashtags(str(caption or "")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_xiaohongshu_note(item: dict[str, Any], collector_type: str) -> CollectorRawRecord | None:
    """小红书笔记规范化。"""
    note_id = (
        item.get("id")
        or item.get("note_id")
        or (item.get("noteCard") or {}).get("noteId")
    )
    if not isinstance(note_id, str) or not note_id.strip():
        return None
    note_id = note_id.strip()

    note_card = item.get("noteCard") or item
    title = note_card.get("title") or note_card.get("displayTitle") or ""
    desc = note_card.get("desc") or note_card.get("description") or ""
    user = note_card.get("user") or note_card.get("noteUser") or {}
    interact_info = note_card.get("interactInfo") or {}

    return CollectorRawRecord(
        record_type="xiaohongshu_note",
        source_url=f"https://www.xiaohongshu.com/explore/{note_id}",
        content={
            "provider": "tikhub",
            "platform": "xiaohongshu",
            "collector_type": collector_type,
            "schema_version": "tikhub_xiaohongshu_note.v1",
            "note_id": note_id,
            "title": str(title)[:500],
            "desc": str(desc)[:2000],
            "author_id": str(user.get("userId") or user.get("user_id") or ""),
            "author_nickname": str(user.get("nickname") or ""),
            "like_count":    _safe_int(interact_info.get("likedCount")),
            "comment_count": _safe_int(interact_info.get("commentCount")),
            "collect_count": _safe_int(interact_info.get("collectCount")),
            "note_type": _safe_str(note_card.get("type")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _safe_ts(value: Any) -> str | None:
    """Unix timestamp 或 ISO 字符串 → ISO 8601 字符串。"""
    if value is None:
        return None
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(value, tz=UTC).isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_hashtags(text: str) -> list[str]:
    import re
    return re.findall(r"#(\w+)", text)[:20]


def _normalize_item(
    item: dict[str, Any],
    record_type: str,
    platform: str,
    collector_type: str,
) -> CollectorRawRecord | None:
    if platform == "tiktok":
        return _normalize_tiktok_video(item, collector_type)
    if platform == "instagram":
        return _normalize_instagram_post(item, collector_type)
    if platform == "xiaohongshu":
        return _normalize_xiaohongshu_note(item, collector_type)
    return None


def _extract_items_from_response(data: dict[str, Any], platform: str) -> list[dict[str, Any]]:
    """从 TikHub 响应中提取条目列表。"""
    # TikHub 通用响应结构：data.data 或 data.data.aweme_list 等
    inner = data.get("data") or {}
    if not isinstance(inner, dict):
        # 有时 data 直接是列表
        if isinstance(inner, list):
            return inner
        return []

    # TikTok 视频列表
    for key in ("aweme_list", "item_list", "items", "video_list", "note_list", "result_list"):
        candidate = inner.get(key)
        if isinstance(candidate, list):
            return candidate

    # 如果 inner 本身是列表形式，退回 data
    if isinstance(data.get("data"), list):
        return data["data"]

    return []


# ──────────────────────────────────────────────
# 主 Collector 类（每个 collector_type 一个实例）
# ──────────────────────────────────────────────

class TikHubSocialCollector(BaseCollector):
    """
    TikHub REST API 通用 collector。

    config 必填字段：
      - `endpoint_type`：TIKHUB_ENDPOINT_MAP 中的 key，如 "tikhub_tiktok_video_search"
      - 各端点所需参数（见 TIKHUB_ENDPOINT_MAP 注释）

    config 可选字段：
      - `max_items`：最多返回条目数，默认 20，上限 100
    """

    collector_type = "tikhub_social"

    # 以下子类型在 registry 中以同一类注册，通过 endpoint_type 区分
    SUPPORTED_ENDPOINT_TYPES = set(TIKHUB_ENDPOINT_MAP.keys())

    def validate_config(self) -> dict[str, Any]:
        endpoint_type = require_text(self.config, "endpoint_type")
        if endpoint_type not in self.SUPPORTED_ENDPOINT_TYPES:
            raise CollectorError(
                f"tikhub_endpoint_type_unknown: {endpoint_type!r}. "
                f"Supported: {sorted(self.SUPPORTED_ENDPOINT_TYPES)}"
            )
        return {
            "endpoint_type": endpoint_type,
            "max_items": min(int(self.config.get("max_items") or 20), 100),
            **{k: v for k, v in self.config.items() if k not in ("endpoint_type", "max_items")},
        }

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        endpoint_type = config["endpoint_type"]
        endpoint_path, _, _ = TIKHUB_ENDPOINT_MAP[endpoint_type]
        api_key = _get_api_key()

        # 构造最小参数测试连通性
        test_params = self._build_params(config, max_items=1)
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient() as client:
                data = await _tikhub_get(client, endpoint_path, test_params, api_key)
            items = _extract_items_from_response(data, TIKHUB_ENDPOINT_MAP[endpoint_type][2])
            msg = f"TikHub endpoint {endpoint_type!r} reachable; got {len(items)} items."
            logs.append(collector_log("tikhub_test", msg))
            return CollectorTestResult(status="ok", message=msg, logs=logs)
        except CollectorError as exc:
            msg = f"TikHub test failed: {exc}"
            logs.append(collector_log("tikhub_test_failed", msg, level="error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        endpoint_type = config["endpoint_type"]
        endpoint_path, record_type, platform = TIKHUB_ENDPOINT_MAP[endpoint_type]
        api_key = _get_api_key()
        max_items = config["max_items"]

        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        raw_records: list[CollectorRawRecord] = []

        params = self._build_params(config, max_items=max_items)
        logs.append(collector_log("tikhub_collect_start", f"endpoint={endpoint_type}, max_items={max_items}"))

        try:
            async with httpx.AsyncClient() as client:
                data = await _tikhub_get(client, endpoint_path, params, api_key)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("tikhub_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        items = _extract_items_from_response(data, platform)
        logs.append(collector_log("tikhub_items_received", f"raw_count={len(items)}"))

        for item in items[:max_items]:
            if not isinstance(item, dict):
                continue
            record = _normalize_item(item, record_type, platform, endpoint_type)
            if record is not None:
                raw_records.append(record)

        logs.append(collector_log(
            "tikhub_collect_done",
            f"normalized={len(raw_records)}/{len(items)} items for {platform}",
        ))

        if not raw_records and items:
            errors.append(f"tikhub_normalize_all_failed: {len(items)} items received but 0 normalized")

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)

    def _build_params(self, config: dict[str, Any], max_items: int) -> dict[str, Any]:
        """按 endpoint_type 构建请求参数。"""
        endpoint_type = config["endpoint_type"]
        count = max_items

        if endpoint_type == "tikhub_tiktok_video_search":
            return {
                "keyword": config.get("keyword") or "",
                "count": count,
                "cursor": config.get("cursor") or 0,
                "sort_type": config.get("sort_type") or 0,
            }
        if endpoint_type == "tikhub_tiktok_user_posts":
            return {
                "unique_id": config.get("unique_id") or config.get("username") or "",
                "count": count,
                "cursor": config.get("cursor") or 0,
            }
        if endpoint_type == "tikhub_tiktok_hashtag_posts":
            return {
                "ch_id": config.get("ch_id") or config.get("hashtag_id") or "",
                "count": count,
                "cursor": config.get("cursor") or 0,
            }
        if endpoint_type == "tikhub_instagram_user_posts":
            return {
                "username": config.get("username") or "",
                "end_cursor": config.get("end_cursor") or None,
            }
        if endpoint_type == "tikhub_instagram_search":
            return {
                "keyword": config.get("keyword") or "",
            }
        if endpoint_type == "tikhub_xiaohongshu_search":
            return {
                "keyword": config.get("keyword") or "",
                "page": config.get("page") or 1,
                "page_size": count,
                "sort": config.get("sort") or "general",
                "note_type": config.get("note_type") or 0,
            }
        return {}
```

#### 修改 `registry.py`

在现有 `COLLECTOR_REGISTRY` 中新增：

```python
from data_intelligence_hub.collectors.tikhub_social import TikHubSocialCollector

COLLECTOR_REGISTRY: dict[str, CollectorClass] = {
    # ... 现有条目 ...
    TikHubSocialCollector.collector_type: TikHubSocialCollector,
}
```

#### 修改 `apps/api/.env.example`

新增：
```bash
# TikHub API Key（https://tikhub.io）
# 用于 TikTok / Instagram / 小红书 数据采集
# TIKHUB_API_KEY=your_tikhub_api_key_here
```

### 测试计划

#### 单元测试（`tests/collectors/test_tikhub_social.py`）

覆盖：
1. `validate_config()` - 缺少 `endpoint_type` 应报错
2. `validate_config()` - 未知 `endpoint_type` 应报错
3. `_normalize_tiktok_video()` - 正常条目规范化
4. `_normalize_tiktok_video()` - 缺少 `aweme_id` 应返回 None
5. `_normalize_instagram_post()` - 正常条目规范化
6. `_normalize_xiaohongshu_note()` - 正常条目规范化
7. `_extract_items_from_response()` - 各种响应结构
8. `collect()` - mock httpx，验证完整流程
9. `test()` - mock httpx，验证连通性检查

#### 本地集成测试（需要真实 API Key）

```bash
# 设置环境变量
export TIKHUB_API_KEY="your_key"

# 运行真实 TikTok 搜索（小样本）
python -c "
import asyncio
from data_intelligence_hub.collectors.tikhub_social import TikHubSocialCollector

async def main():
    collector = TikHubSocialCollector(config={
        'endpoint_type': 'tikhub_tiktok_video_search',
        'keyword': 'wearable breast pump',
        'max_items': 5,
    })
    result = await collector.collect()
    print(f'records={len(result.raw_records)}, errors={result.errors}')
    for r in result.raw_records:
        print(r.record_type, r.content.get('video_id'), r.content.get('text', '')[:80])

asyncio.run(main())
"
```

### 成功标准

- [ ] 单元测试全部通过（mock，无真实 API 调用）
- [ ] `validate_config()` 能识别无效配置
- [ ] 规范化函数对标准响应输出正确的 `CollectorRawRecord`
- [ ] 集成测试（真实 API Key）：TikTok 搜索返回 ≥1 条规范化记录
- [ ] 集成测试：Instagram 账号帖子返回 ≥1 条规范化记录
- [ ] `TIKHUB_API_KEY` 缺失时 `collect()` 返回明确错误，不 panic
- [ ] `lsp_diagnostics` 无类型错误

---

## Phase 1B：Apify Actor Collector 接入

### 目标

实现 Apify Actor 通用 collector，覆盖 56 个代表 Actor（尤其 P0 优先级），实现异步 Run → 轮询 → Dataset 读取完整流程。

### 架构位置

```
新增文件：
  apps/api/src/data_intelligence_hub/collectors/apify_actor.py

修改文件：
  apps/api/src/data_intelligence_hub/collectors/registry.py
  apps/api/.env.example（新增 APIFY_API_TOKEN 说明）
```

### P0 优先 Actor 清单

基于 Apify 技术文档的深潜层 56 个代表 Actor，P0 级别优先接入：

| Actor | 平台 | 能力 | `record_type` |
|---|---|---|---|
| `apify/instagram-scraper` | Instagram | 帖子/Reels/评论 | `instagram_post` |
| `apify/instagram-profile-scraper` | Instagram | 账号画像 | `instagram_profile` |
| `clockworks/tiktok-scraper` | TikTok | 视频/话题/账号 | `tiktok_video` |
| `streamers/youtube-scraper` | YouTube | 视频搜索 | `youtube_video` |
| `streamers/youtube-comments-scraper` | YouTube | 视频评论 | `youtube_comment` |
| `trudax/reddit-scraper-lite` | Reddit | 帖子/评论 | `reddit_post` |
| `apify/facebook-posts-scraper` | Facebook | 帖子 | `facebook_post` |
| `apify/facebook-comments-scraper` | Facebook | 评论 | `facebook_comment` |
| `junglee/amazon-crawler` | Amazon | 商品 | `amazon_product` |
| `memo23/trustpilot-scraper-ppe` | Trustpilot | 评论 | `review` |
| `agents/appstore-reviews` | App Store | 评论 | `review` |

### 实现代码

#### `apps/api/src/data_intelligence_hub/collectors/apify_actor.py`

```python
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
    require_text,
)

APIFY_BASE_URL = "https://api.apify.com/v2"
APIFY_TIMEOUT = 30.0
APIFY_RUN_WAIT_TIMEOUT = 600       # 最长等待 Actor 运行 10 分钟
APIFY_POLL_INTERVAL = 5.0          # 每 5 秒轮询一次
APIFY_MAX_DATASET_LIMIT = 1000     # 单次 Dataset 读取上限

# Actor 运行的终态
APIFY_TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"})


def _get_api_token() -> str:
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not token:
        raise CollectorError("apify_token_missing: APIFY_API_TOKEN env var not set")
    return token


def _apify_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _apify_post(
    client: httpx.AsyncClient,
    path: str,
    json_body: dict[str, Any],
    params: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    resp = await client.post(
        f"{APIFY_BASE_URL}{path}",
        json=json_body,
        params=params,
        headers=_apify_headers(token),
        timeout=APIFY_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


async def _apify_get(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    resp = await client.get(
        f"{APIFY_BASE_URL}{path}",
        params=params,
        headers=_apify_headers(token),
        timeout=APIFY_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


async def _wait_for_run(
    client: httpx.AsyncClient,
    run_id: str,
    token: str,
    timeout: float,
) -> dict[str, Any]:
    """轮询等待 Actor Run 完成，返回最终 Run 状态对象。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        resp = await _apify_get(client, f"/actor-runs/{run_id}", {}, token)
        run_data = resp.get("data") or {}
        status = run_data.get("status", "")
        if status in APIFY_TERMINAL_STATUSES:
            return run_data
        if asyncio.get_event_loop().time() >= deadline:
            raise CollectorError(
                f"apify_run_timeout: run {run_id!r} did not finish within {timeout}s"
            )
        await asyncio.sleep(APIFY_POLL_INTERVAL)


async def _fetch_dataset_items(
    client: httpx.AsyncClient,
    dataset_id: str,
    limit: int,
    token: str,
) -> list[dict[str, Any]]:
    """从 Apify Dataset 读取条目。"""
    resp = await _apify_get(
        client,
        f"/datasets/{dataset_id}/items",
        {"format": "json", "clean": "1", "limit": str(min(limit, APIFY_MAX_DATASET_LIMIT))},
        token,
    )
    # Dataset items API 直接返回列表
    if isinstance(resp, list):
        return resp
    # 也可能包在 data 里
    if isinstance(resp, dict) and isinstance(resp.get("data"), list):
        return resp["data"]
    return []


def _actor_id_to_path(actor_id: str) -> str:
    """将 'username/name' 转为 URL 路径 'username~name'。"""
    return actor_id.replace("/", "~")


# ──────────────────────────────────────────
# 通用规范化：Apify 输出 → CollectorRawRecord
# ──────────────────────────────────────────

def _infer_record_type(actor_id: str, item: dict[str, Any]) -> str:
    """根据 Actor ID 推断 record_type。"""
    lower = actor_id.lower()
    if "instagram" in lower:
        if "profile" in lower:
            return "instagram_profile"
        return "instagram_post"
    if "tiktok" in lower:
        if "profile" in lower:
            return "tiktok_profile"
        return "tiktok_video"
    if "youtube" in lower:
        if "comment" in lower:
            return "youtube_comment"
        return "youtube_video"
    if "reddit" in lower:
        return "reddit_post"
    if "facebook" in lower:
        if "comment" in lower:
            return "facebook_comment"
        return "facebook_post"
    if "amazon" in lower:
        return "amazon_product"
    if "trustpilot" in lower or "appstore" in lower or "google-play" in lower:
        return "review"
    if "linkedin" in lower:
        return "linkedin_post"
    if "twitter" in lower or "tweet" in lower:
        return "twitter_post"
    return "social_post"


def _infer_platform(actor_id: str) -> str:
    lower = actor_id.lower()
    for platform in ("instagram", "tiktok", "youtube", "reddit", "facebook",
                     "amazon", "trustpilot", "linkedin", "twitter", "threads",
                     "bluesky", "shopify", "walmart", "ebay"):
        if platform in lower:
            return platform
    return "web"


def _extract_source_url(item: dict[str, Any], platform: str) -> str | None:
    """尝试从 item 中提取 source URL。"""
    for key in ("url", "postUrl", "videoUrl", "productUrl", "reviewUrl",
                "facebookUrl", "profileUrl", "webVideoUrl"):
        val = item.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None


def normalize_apify_item(
    item: dict[str, Any],
    actor_id: str,
    record_type: str | None = None,
) -> CollectorRawRecord | None:
    """将 Apify Actor 输出条目规范化为 CollectorRawRecord。"""
    if not isinstance(item, dict) or not item:
        return None

    platform = _infer_platform(actor_id)
    rt = record_type or _infer_record_type(actor_id, item)
    source_url = _extract_source_url(item, platform)

    # 提取文本内容（尽力而为）
    text = ""
    for key in ("text", "caption", "description", "title", "body", "content",
                "reviewText", "comment", "postText"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            text = val.strip()[:2000]
            break

    return CollectorRawRecord(
        record_type=rt,
        source_url=source_url,
        content={
            "provider": "apify",
            "platform": platform,
            "actor_id": actor_id,
            "schema_version": f"apify_{rt}.v1",
            "text": text,
            "raw": item,  # 保留原始数据，便于后续字段提取
        },
        collected_at=datetime.now(UTC),
    )


# ──────────────────────────────────────────
# 主 Collector 类
# ──────────────────────────────────────────

class ApifyActorCollector(BaseCollector):
    """
    Apify Actor 通用 collector。

    config 必填字段：
      - `actor_id`：Actor 标识符，格式 'username/name'，如 'apify/instagram-scraper'
      - `actor_input`：传给 Actor 的输入参数（dict）

    config 可选字段：
      - `max_items`：最多返回条目数，默认 20，上限 1000
      - `run_timeout_seconds`：等待 Actor 完成的超时（秒），默认 600
      - `max_total_charge_usd`：最高费用上限（USD），默认 1.0
      - `record_type`：强制指定 record_type，不自动推断
    """

    collector_type = "apify_actor"

    def validate_config(self) -> dict[str, Any]:
        actor_id = require_text(self.config, "actor_id")
        if "/" not in actor_id:
            raise CollectorError(
                f"apify_actor_id_invalid: expected 'username/name' format, got {actor_id!r}"
            )
        actor_input = self.config.get("actor_input")
        if not isinstance(actor_input, dict):
            raise CollectorError("apify_actor_input_missing: 'actor_input' must be a dict")
        return {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": min(int(self.config.get("max_items") or 20), APIFY_MAX_DATASET_LIMIT),
            "run_timeout_seconds": int(self.config.get("run_timeout_seconds") or APIFY_RUN_WAIT_TIMEOUT),
            "max_total_charge_usd": float(self.config.get("max_total_charge_usd") or 1.0),
            "record_type": self.config.get("record_type"),
        }

    async def test(self) -> CollectorTestResult:
        """验证 API Token 有效（调用 /v2/users/me）。"""
        token = _get_api_token()
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await _apify_get(client, "/users/me", {}, token)
            username = (resp.get("data") or {}).get("username", "unknown")
            msg = f"Apify token valid; user={username!r}"
            logs.append(collector_log("apify_test", msg))
            return CollectorTestResult(status="ok", message=msg, logs=logs)
        except (CollectorError, httpx.HTTPError) as exc:
            msg = f"Apify token test failed: {exc}"
            logs.append(collector_log("apify_test_failed", msg, level="error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        token = _get_api_token()
        actor_id: str = config["actor_id"]
        actor_input: dict[str, Any] = config["actor_input"]
        max_items: int = config["max_items"]
        run_timeout: float = float(config["run_timeout_seconds"])
        max_charge: float = config["max_total_charge_usd"]
        record_type: str | None = config["record_type"]

        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        raw_records: list[CollectorRawRecord] = []

        actor_path = _actor_id_to_path(actor_id)
        logs.append(collector_log(
            "apify_run_start",
            f"actor={actor_id}, max_items={max_items}, max_charge=${max_charge}",
        ))

        try:
            async with httpx.AsyncClient() as client:
                # 1. 启动 Actor Run
                run_resp = await _apify_post(
                    client,
                    f"/acts/{actor_path}/runs",
                    json_body=actor_input,
                    params={"maxTotalChargeUsd": str(max_charge)},
                    token=token,
                )
                run_id = (run_resp.get("data") or {}).get("id")
                if not run_id:
                    raise CollectorError("apify_run_id_missing: no run ID in response")

                logs.append(collector_log("apify_run_created", f"run_id={run_id}"))

                # 2. 等待 Actor 完成
                run_data = await _wait_for_run(client, run_id, token, timeout=run_timeout)
                status = run_data.get("status", "")
                logs.append(collector_log("apify_run_completed", f"run_id={run_id}, status={status}"))

                if status != "SUCCEEDED":
                    errors.append(f"apify_run_failed: run {run_id!r} ended with status={status!r}")
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)

                # 3. 读取 Dataset
                dataset_id = run_data.get("defaultDatasetId")
                if not dataset_id:
                    errors.append("apify_dataset_id_missing: no defaultDatasetId in run data")
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)

                items = await _fetch_dataset_items(client, dataset_id, max_items, token)
                logs.append(collector_log("apify_dataset_fetched", f"dataset_id={dataset_id}, count={len(items)}"))

        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("apify_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("apify_http_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        # 4. 规范化
        for item in items[:max_items]:
            record = normalize_apify_item(item, actor_id, record_type)
            if record is not None:
                raw_records.append(record)

        logs.append(collector_log(
            "apify_collect_done",
            f"normalized={len(raw_records)}/{len(items)} items from {actor_id}",
        ))

        if not raw_records and items:
            errors.append(f"apify_normalize_all_failed: {len(items)} items received but 0 normalized")

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)
```

### 修改 `registry.py`（追加 Apify）

```python
from data_intelligence_hub.collectors.apify_actor import ApifyActorCollector

COLLECTOR_REGISTRY: dict[str, CollectorClass] = {
    # ... 现有条目 + TikHub ...
    ApifyActorCollector.collector_type: ApifyActorCollector,
}
```

### 修改 `.env.example`（追加）

```bash
# Apify API Token（https://apify.com）
# 用于通过 Apify Actor 采集 Instagram/TikTok/YouTube/Reddit/Facebook 等平台数据
# APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 测试计划

#### 单元测试（`tests/collectors/test_apify_actor.py`）

覆盖：
1. `validate_config()` - 缺少 `actor_id` 应报错
2. `validate_config()` - `actor_id` 格式错误（无斜杠）应报错
3. `validate_config()` - `actor_input` 非 dict 应报错
4. `_actor_id_to_path()` - 正确转换 `apify/instagram-scraper` → `apify~instagram-scraper`
5. `normalize_apify_item()` - Instagram 帖子 item 规范化
6. `normalize_apify_item()` - TikTok 视频 item 规范化
7. `normalize_apify_item()` - 空 item 返回 None
8. `collect()` - mock httpx，验证完整 Run→轮询→Dataset 流程
9. `collect()` - Actor 运行失败时返回 errors，不 panic
10. `test()` - mock /users/me 验证 token

#### 本地集成测试（需要真实 API Token）

```bash
export APIFY_API_TOKEN="apify_api_xxx"

python -c "
import asyncio
from data_intelligence_hub.collectors.apify_actor import ApifyActorCollector

async def main():
    # 用最小样本测试 Instagram Scraper
    collector = ApifyActorCollector(config={
        'actor_id': 'apify/instagram-scraper',
        'actor_input': {
            'search': 'wearable breast pump',
            'resultsType': 'posts',
            'resultsLimit': 3,
        },
        'max_items': 3,
        'max_total_charge_usd': 0.1,  # 严格费用上限
    })
    result = await collector.collect()
    print(f'records={len(result.raw_records)}, errors={result.errors}')
    for r in result.raw_records:
        print(r.record_type, r.source_url, r.content.get('text', '')[:80])

asyncio.run(main())
"
```

### 成功标准

- [ ] 单元测试全部通过（mock，无真实 API 调用，零 Apify 费用）
- [ ] `validate_config()` 能识别无效配置
- [ ] `normalize_apify_item()` 对 Instagram/TikTok/YouTube 标准输出规范化正确
- [ ] 集成测试（真实 Token，`max_total_charge_usd=0.1`）：Instagram Scraper 返回 ≥1 条记录
- [ ] Actor Run 失败时返回明确错误，不引发异常
- [ ] `APIFY_API_TOKEN` 缺失时 `collect()` 返回明确错误
- [ ] `lsp_diagnostics` 无类型错误

---

## Phase 1 整体验收

### 端到端测试流程

完成 Phase 0 生产 migration 和 Phase 1A/1B 编码后，执行以下端到端验证：

```
1. 在平台 /sources 新建 Source
   type = "tikhub_social"
   config = {
     "endpoint_type": "tikhub_tiktok_video_search",
     "keyword": "wearable breast pump",
     "max_items": 10
   }

2. 启用 Source，触发 Task Run

3. 验证链路：
   TaskRun → RawRecord (record_type=tiktok_video) → EntitySnapshot → Signal

4. 在 /raw-records 查看写入的原始记录

5. 在 /datasets 创建 Dataset，选择上述 RawRecord

6. 验证 /intelligence 生成了洞察条目（mock LLM 阶段）
```

重复以上流程验证：
- `tikhub_instagram_user_posts`（Instagram 账号采集）
- `apify_actor` with `apify/instagram-scraper`（Apify Instagram）

### 性能基线

| 指标 | 目标 |
|---|---|
| TikHub 单次采集 10 条 | < 5 秒 |
| Apify Actor 运行（小样本 3-5 条） | < 3 分钟 |
| 每条 RawRecord 写入 | < 100ms |

---

## 依赖和阻塞

### Phase 0 阻塞 Phase 1

Phase 1 collector 开发**不依赖** Phase 0 migration（本地开发使用本地 DB）。但 Phase 1 推生产时，需要 Phase 0 先完成。

### 新增 Python 依赖

`apps/api/pyproject.toml` 无需新增依赖：
- `httpx` 已有
- `asyncio` 标准库
- `os` 标准库

TikHub 和 Apify 都是纯 REST HTTP，不需要 SDK。

### 环境变量

```bash
TIKHUB_API_KEY=    # Phase 1A 必需
APIFY_API_TOKEN=   # Phase 1B 必需
```

生产部署时加入 `/opt/data-achieve-scrapy/.env.production`。

---

## 执行顺序

```
Day 1:  Phase 0 - 本地验证 migration Batch 1 (023→033)
Day 1:  Phase 1A - 实现 tikhub_social.py + 单元测试
Day 2:  Phase 1A - 本地集成测试（真实 API Key）
Day 2:  Phase 1B - 实现 apify_actor.py + 单元测试
Day 3:  Phase 1B - 本地集成测试（真实 Token，小样本）
Day 3:  Phase 0 - 生产执行 Batch 1 migration
Day 4:  Phase 1 - 端到端验证（生产或本地均可）
Day 4:  Phase 1 - 代码提交 + CI 验证
```

---

## 下一步（Phase 2）

Phase 1 完成验证后，进入 Phase 2：
1. Batch 2 migration（035 credential vault 推生产）
2. TikHub API Key 接入 Fernet vault（通过 `/settings/platforms` 配置）
3. Apify Token 接入 vault
4. WorkflowPlan Planner 新增 `tikhub_social` 和 `apify_actor` 能力注册
5. 增量采集 cursor 持久化（Task Run 结果存储 `cursor` 用于下次接续）
