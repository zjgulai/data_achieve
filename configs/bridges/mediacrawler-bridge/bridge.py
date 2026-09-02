"""Bridge server: translates collector routes to bllxk/mediacrawler-api format."""
import asyncio
import os
import uuid
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
MC_URL = os.environ.get("MC_UPSTREAM", "http://mediacrawler:8001")


async def _crawl(platform: str, ctype: str, keyword: str = "", limit: int = 20,
                 extra: dict | None = None) -> list[dict]:
    _PLATFORM_MAP = {"bilibili": "bili", "weibo": "wb", "zhihu": "zhihu", "kuaishou": "ks"}
    api_platform = _PLATFORM_MAP.get(platform, platform)
    payload = {"platform": api_platform, "type": ctype, "keyword": keyword,
               "limit": limit, **(extra or {})}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{MC_URL}/api/crawler", json=payload)
        r.raise_for_status()
        body = r.json()
    if isinstance(body, dict):
        if body.get("success") is False:
            raise RuntimeError(body.get("message", "MediaCrawler task failed"))
        task_id = body.get("task_id")
        if not task_id:
            data = body.get("data", [])
            return data if isinstance(data, list) else []
        for _ in range(30):
            await asyncio.sleep(2)
            async with httpx.AsyncClient(timeout=10) as client:
                tr = await client.get(f"{MC_URL}/api/task/{task_id}")
            td = tr.json()
            task_data = td.get("data")
            if task_data is None:
                raise RuntimeError("MediaCrawler requires platform cookies (BILIBILI_COOKIES / WEIBO_COOKIES / ZHIHU_COOKIES / KUAISHOU_COOKIES)")
            if task_data.get("status") in ("completed", "failed"):
                return task_data.get("result", [])
        return []
    return body if isinstance(body, list) else []


def ok(data):
    return JSONResponse({"code": 0, "data": data})


def fail(msg):
    return JSONResponse({"code": -1, "msg": msg})


@app.get("/bilibili/health")
async def bilibili_health():
    return {"status": "ok"}


@app.get("/bilibili/search")
async def bilibili_search(keyword: str = "", limit: int = 20):
    try:
        data = await _crawl("bilibili", "search", keyword=keyword, limit=limit)
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/bilibili/user/videos")
async def bilibili_user_videos(uid: str = "", limit: int = 20):
    try:
        data = await _crawl("bilibili", "detail", keyword=uid, limit=limit,
                             extra={"uid": uid})
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/bilibili/video/comments")
async def bilibili_video_comments(bvid: str = "", limit: int = 20):
    try:
        data = await _crawl("bilibili", "comment", keyword=bvid, limit=limit,
                             extra={"bvid": bvid})
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/weibo/search")
async def weibo_search(keyword: str = "", limit: int = 20):
    try:
        data = await _crawl("weibo", "search", keyword=keyword, limit=limit)
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/weibo/user/posts")
async def weibo_user_posts(uid: str = "", limit: int = 20):
    try:
        data = await _crawl("weibo", "detail", keyword=uid, limit=limit,
                             extra={"uid": uid})
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/weibo/trending")
async def weibo_trending():
    try:
        data = await _crawl("weibo", "trending", keyword="", limit=50)
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/zhihu/question/answers")
async def zhihu_question_answers(question_id: str = "", limit: int = 20):
    try:
        data = await _crawl("zhihu", "search", keyword=question_id, limit=limit)
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/zhihu/search")
async def zhihu_search(keyword: str = "", limit: int = 20):
    try:
        data = await _crawl("zhihu", "search", keyword=keyword, limit=limit)
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/zhihu/hot")
async def zhihu_hot():
    try:
        data = await _crawl("zhihu", "search", keyword="hot", limit=50)
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/kuaishou/search")
async def kuaishou_search(keyword: str = "", limit: int = 20):
    try:
        data = await _crawl("kuaishou", "search", keyword=keyword, limit=limit)
        return ok(data)
    except Exception as e:
        return fail(str(e))


@app.get("/kuaishou/user/videos")
async def kuaishou_user_videos(user_id: str = "", limit: int = 20):
    try:
        data = await _crawl("kuaishou", "detail", keyword=user_id, limit=limit,
                             extra={"user_id": user_id})
        return ok(data)
    except Exception as e:
        return fail(str(e))
