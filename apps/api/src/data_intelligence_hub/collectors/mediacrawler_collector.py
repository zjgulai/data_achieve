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
from data_intelligence_hub.collectors.empty_result_policy import (
    empty_result_error,
    resolve_empty_result_policy,
)
from data_intelligence_hub.collectors.outbound_policy import assert_collector_allowed

_DEFAULT_BASE_URL = "http://localhost:8080"
_DEFAULT_TIMEOUT = 30.0


def _apply_empty_result_policy(
    collector: BaseCollector,
    collected_records: int,
    errors: list[str],
    logs: list[dict[str, Any]],
    endpoint_type: str | None = None,
) -> None:
    """Turn a strict zero-record run into a structured error.

    A permissive policy leaves the result untouched: the service emits the
    `empty` warning log so the two layers never log the same event twice.
    """
    if collected_records > 0:
        return
    policy = resolve_empty_result_policy(
        collector_type=collector.collector_type,
        config=collector.config,
        collector_class=type(collector),
        task_config=collector.config,
    )
    if policy.allow_empty:
        return
    message = empty_result_error(
        collector_type=collector.collector_type,
        endpoint_type=endpoint_type,
        expected_records=policy.effective_min_expected_records,
    )
    errors.append(message)
    log = collector_log("collector_empty_result", message, level="error")
    log.update(
        {
            "collector_type": collector.collector_type,
            "endpoint_type": endpoint_type,
            "allow_empty": policy.allow_empty,
            "min_expected_records": policy.min_expected_records,
            "collected_records": collected_records,
            "enforced": True,
        }
    )
    logs.append(log)


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


def _dict_items(items: list[Any], path: str) -> list[dict[str, Any]]:
    """Keep object items; any other item type means the shape is unknown."""
    result = [item for item in items if isinstance(item, dict)]
    if len(result) != len(items):
        raise CollectorError(
            "mediacrawler_response_shape_unknown: expected list items to be JSON "
            f"objects, got {len(items) - len(result)} non-object item(s) (path={path})"
        )
    return result


async def _mc_get(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Call a MediaCrawler API endpoint and return the data list."""
    url = f"{_base_url()}{path}"
    try:
        async with _client() as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc

    try:
        body = r.json()
    except ValueError as exc:
        if not r.text.strip():
            raise CollectorError(
                f"mediacrawler_upstream_empty: upstream returned an empty body (path={path})"
            ) from exc
        raise CollectorError(
            "mediacrawler_response_shape_unknown: upstream response is not valid JSON "
            f"(path={path})"
        ) from exc

    # MediaCrawler API responds with {"code": 0, "data": [...]}.
    if isinstance(body, dict):
        if "code" not in body:
            raise CollectorError(
                "mediacrawler_response_shape_unknown: response has no 'code' field "
                f"(path={path})"
            )
        if body.get("code") != 0:
            detail = body.get("msg") or body.get("message") or "unknown error"
            raise CollectorError(f"MediaCrawler API error: {detail}")
        if "data" not in body:
            raise CollectorError(
                "mediacrawler_response_shape_unknown: response has no 'data' field "
                f"(path={path})"
            )
        data = body["data"]
        if data is None:
            raise CollectorError(
                f"mediacrawler_upstream_empty: response 'data' is null (path={path})"
            )
        if not isinstance(data, list):
            raise CollectorError(
                "mediacrawler_response_shape_unknown: expected 'data' to be a list, "
                f"got {type(data).__name__} (path={path})"
            )
        return _dict_items(data, path)
    if isinstance(body, list):
        return _dict_items(body, path)
    if body is None:
        raise CollectorError(
            f"mediacrawler_upstream_empty: upstream returned JSON null (path={path})"
        )
    raise CollectorError(
        "mediacrawler_response_shape_unknown: expected a JSON object or array, "
        f"got {type(body).__name__} (path={path})"
    )


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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
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
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        uid = require_text(self.config, "uid")
        max_items = int(self.config.get("max_items", 30))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"uid": uid, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("bilibili_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = True

    def validate_config(self) -> dict[str, Any]:
        bvid = require_text(self.config, "bvid")
        max_items = int(self.config.get("max_items", 50))
        if max_items < 1 or max_items > 500:
            raise CollectorError("max_items must be between 1 and 500")
        return {"bvid": bvid, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("bilibili_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("weibo_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        uid = require_text(self.config, "uid")
        max_items = int(self.config.get("max_items", 30))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"uid": uid, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("weibo_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        return {}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("weibo_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get("/weibo/trending")
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("weibo_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        _apply_empty_result_policy(self, len(items), errors, logs)
        if not items:
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
    allow_empty = True

    def validate_config(self) -> dict[str, Any]:
        question_id = require_text(self.config, "question_id")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"question_id": question_id, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("zhihu_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("zhihu_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        return {}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("zhihu_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            items = await _mc_get("/zhihu/hot")
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("zhihu_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        _apply_empty_result_policy(self, len(items), errors, logs)
        if not items:
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("kuaishou_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
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
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        user_id = require_text(self.config, "user_id")
        max_items = int(self.config.get("max_items", 30))
        if max_items < 1 or max_items > 200:
            raise CollectorError("max_items must be between 1 and 200")
        return {"user_id": user_id, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        return CollectorTestResult(
            status="ok",
            message=f"MediaCrawler base URL: {_base_url()}",
            logs=[collector_log("kuaishou_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
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

        _apply_empty_result_policy(self, len(items), errors, logs)
        records = _records_from(items, "post", "url", collected_at)
        logs.append(
            collector_log(
                "kuaishou_user_videos_collected",
                f"user_id={config['user_id']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
