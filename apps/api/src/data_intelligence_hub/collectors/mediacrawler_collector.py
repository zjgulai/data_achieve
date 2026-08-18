"""MediaCrawler-based collectors for Chinese social platforms.

Wraps MediaCrawler's HTTP API mode to collect content from:
  - Bilibili (B站): video search, user videos, video comments
  - Weibo (微博): keyword search, user posts, trending topics
  - Zhihu (知乎): question answers, keyword search, hot list

Deployment model:
  MediaCrawler runs as a separate HTTP service started via:
    python main.py --platform xhs --type search --lt qrcode --mode api
  and exposes a REST API on port 8080 (configurable).

Environment variables:
    MEDIACRAWLER_BASE_URL   Base URL of the MediaCrawler service
                            (default: http://localhost:8080)
    MEDIACRAWLER_TIMEOUT    Request timeout in seconds (default: 30)

Account notes:
  - Bilibili: BILIBILI_COOKIES env var in the MediaCrawler container
  - Weibo: WEIBO_COOKIES env var in the MediaCrawler container
  - Zhihu: ZHIHU_COOKIES env var in the MediaCrawler container
  Configure these in docker-compose.yml under the mediacrawler service.
"""
from __future__ import annotations

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

_DEFAULT_BASE_URL = "http://localhost:8080"
_DEFAULT_TIMEOUT = 30.0


def _base_url() -> str:
    return os.environ.get("MEDIACRAWLER_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _timeout() -> float:
    try:
        return float(os.environ.get("MEDIACRAWLER_TIMEOUT", str(_DEFAULT_TIMEOUT)))
    except ValueError:
        return _DEFAULT_TIMEOUT


def _client() -> httpx.AsyncClient:
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    return httpx.AsyncClient(timeout=_timeout(), proxy=proxy or None)


async def _mc_get(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Call a MediaCrawler API endpoint and return the data list."""
    url = f"{_base_url()}{path}"
    try:
        async with _client() as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc

    body = r.json()
    # MediaCrawler API responds with {"code": 0, "data": [...]}
    if isinstance(body, dict):
        if body.get("code") != 0:
            detail = body.get("msg") or body.get("message") or "unknown error"
            raise CollectorError(f"MediaCrawler API error: {detail}")
        data = body.get("data", [])
        return data if isinstance(data, list) else [data]
    if isinstance(body, list):
        return body
    return []


def _records_from(
    items: list[dict[str, Any]],
    record_type: str,
    source_url_key: str | None,
    collected_at: datetime,
) -> list[CollectorRawRecord]:
    records = []
    for item in items:
        source_url = item.get(source_url_key) if source_url_key else None
        records.append(
            CollectorRawRecord(
                record_type=record_type,
                source_url=str(source_url) if source_url else None,
                content=item,
                collected_at=collected_at,
            )
        )
    return records


# ─────────────────────────────────────────────
#  Bilibili collectors
# ─────────────────────────────────────────────

class BilibiliVideoSearchCollector(BaseCollector):
    """Search Bilibili videos by keyword via MediaCrawler."""

    collector_type = "bilibili_video_search"

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        url = f"{_base_url()}/bilibili/health"
        try:
            async with _client() as client:
                r = await client.get(url)
            if r.status_code not in {200, 404}:
                msg = f"MediaCrawler Bilibili not reachable (HTTP {r.status_code})"
                return CollectorTestResult(
                    status="failed", message=msg,
                    logs=[collector_log("bilibili_test_failed", msg, level="error")],
                )
        except httpx.HTTPError as exc:
            msg = f"MediaCrawler not reachable: {exc}"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("bilibili_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler reachable at {_base_url()}",
            logs=[collector_log("bilibili_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/bilibili/search",
                params={"keyword": config["keyword"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("bilibili_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "bilibili_search_collected",
                f"keyword={config['keyword']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class BilibiliUserVideosCollector(BaseCollector):
    """Collect a Bilibili user's public video list via MediaCrawler."""

    collector_type = "bilibili_user_videos"

    def validate_config(self) -> dict[str, Any]:
        uid = require_text(self.config, "uid")
        max_items = int(self.config.get("max_items", 30))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"uid": uid, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("bilibili_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/bilibili/user/videos",
                params={"uid": config["uid"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("bilibili_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "bilibili_user_videos_collected",
                f"uid={config['uid']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class BilibiliVideoCommentsCollector(BaseCollector):
    """Collect comments for a Bilibili video via MediaCrawler."""

    collector_type = "bilibili_video_comments"

    def validate_config(self) -> dict[str, Any]:
        bvid = require_text(self.config, "bvid")
        max_items = int(self.config.get("max_items", 50))
        if max_items < 1 or max_items > 500:
            raise CollectorError("max_items must be between 1 and 500")
        return {"bvid": bvid, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("bilibili_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/bilibili/video/comments",
                params={"bvid": config["bvid"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("bilibili_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "comment", None, collected_at)
        logs.append(
            collector_log(
                "bilibili_comments_collected",
                f"bvid={config['bvid']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  Weibo collectors
# ─────────────────────────────────────────────

class WeiboKeywordSearchCollector(BaseCollector):
    """Search Weibo posts by keyword via MediaCrawler."""

    collector_type = "weibo_keyword_search"

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("weibo_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/weibo/search",
                params={"keyword": config["keyword"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("weibo_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "weibo_search_collected",
                f"keyword={config['keyword']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class WeiboUserPostsCollector(BaseCollector):
    """Collect a Weibo user's public posts via MediaCrawler."""

    collector_type = "weibo_user_posts"

    def validate_config(self) -> dict[str, Any]:
        uid = require_text(self.config, "uid")
        max_items = int(self.config.get("max_items", 30))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"uid": uid, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("weibo_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/weibo/user/posts",
                params={"uid": config["uid"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("weibo_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "weibo_user_posts_collected",
                f"uid={config['uid']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class WeiboTrendingTopicsCollector(BaseCollector):
    """Collect Weibo trending topics list via MediaCrawler."""

    collector_type = "weibo_trending_topics"

    def validate_config(self) -> dict[str, Any]:
        return {}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("weibo_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get("/weibo/trending")
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("weibo_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        record = CollectorRawRecord(
            record_type="trend",
            source_url="https://weibo.com/hot/search",
            content={"trending": items, "total": len(items)},
            collected_at=collected_at,
        )
        logs.append(collector_log("weibo_trending_collected", f"count={len(items)}"))
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  Zhihu collectors
# ─────────────────────────────────────────────

class ZhihuQuestionAnswersCollector(BaseCollector):
    """Collect answers for a Zhihu question via MediaCrawler."""

    collector_type = "zhihu_question_answers"

    def validate_config(self) -> dict[str, Any]:
        question_id = require_text(self.config, "question_id")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"question_id": question_id, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("zhihu_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/zhihu/question/answers",
                params={
                    "question_id": config["question_id"],
                    "limit": config["max_items"],
                },
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("zhihu_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "zhihu_answers_collected",
                f"question_id={config['question_id']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class ZhihuKeywordSearchCollector(BaseCollector):
    """Search Zhihu questions/answers by keyword via MediaCrawler."""

    collector_type = "zhihu_keyword_search"

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("zhihu_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/zhihu/search",
                params={"keyword": config["keyword"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("zhihu_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "zhihu_search_collected",
                f"keyword={config['keyword']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class ZhihuHotListCollector(BaseCollector):
    """Collect the Zhihu hot list (热榜) via MediaCrawler."""

    collector_type = "zhihu_hot_list"

    def validate_config(self) -> dict[str, Any]:
        return {}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("zhihu_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get("/zhihu/hot")
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("zhihu_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        record = CollectorRawRecord(
            record_type="trend",
            source_url="https://www.zhihu.com/hot",
            content={"hot_list": items, "total": len(items)},
            collected_at=collected_at,
        )
        logs.append(collector_log("zhihu_hot_collected", f"count={len(items)}"))
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  Kuaishou collectors
# ─────────────────────────────────────────────

class KuaishouVideoSearchCollector(BaseCollector):
    """Search Kuaishou videos by keyword via MediaCrawler."""

    collector_type = "kuaishou_video_search"

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("kuaishou_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/kuaishou/search",
                params={"keyword": config["keyword"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("kuaishou_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "kuaishou_search_collected",
                f"keyword={config['keyword']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class KuaishouUserVideosCollector(BaseCollector):
    """Collect a Kuaishou user's public video list via MediaCrawler."""

    collector_type = "kuaishou_user_videos"

    def validate_config(self) -> dict[str, Any]:
        user_id = require_text(self.config, "user_id")
        max_items = int(self.config.get("max_items", 30))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"user_id": user_id, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("kuaishou_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get(
                "/kuaishou/user/videos",
                params={"user_id": config["user_id"], "limit": config["max_items"]},
            )
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("kuaishou_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "kuaishou_user_videos_collected",
                f"user_id={config['user_id']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
