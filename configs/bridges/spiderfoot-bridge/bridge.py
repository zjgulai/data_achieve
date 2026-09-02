"""Bridge: wraps SpiderFoot Web UI routes into /api/v1/ REST API."""
import asyncio, os, json, uuid, re
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
SF_URL = os.environ.get("SF_UPSTREAM", "http://spiderfoot:5001")


async def _sf_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{SF_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def _sf_post_form(path: str, data: dict):
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as c:
        r = await c.post(f"{SF_URL}{path}", data=data,
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
        if r.status_code in (301, 302, 303, 307, 308):
            location = r.headers.get("location", "")
            m = re.search(r"id=([A-Z0-9]+)", location)
            return [m.group(1)] if m else []
        r.raise_for_status()
        return r.json()


@app.post("/api/v1/scan/")
async def start_scan(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    scan_name = body.get("scanname", f"dih-{uuid.uuid4().hex[:8]}")
    target = body.get("scantarget", "")
    modules = body.get("modulelist", "")
    typelist = body.get("typelist", "")
    usecase = body.get("usecase", "all")
    try:
        result = await _sf_post_form("/startscan", {
            "scanname": scan_name,
            "scantarget": target,
            "modulelist": modules,
            "typelist": typelist,
            "usecase": usecase,
        })
        if isinstance(result, list) and result:
            scan_id = result[0]
        else:
            scan_id = str(result) if result else ""
        return {"id": scan_id, "status": "STARTING"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v1/scan/{scan_id}/status")
async def scan_status(scan_id: str):
    try:
        result = await _sf_get(f"/scanstatus", params={"id": scan_id})
        if isinstance(result, list) and len(result) > 5:
            status = result[5]
        else:
            status = "UNKNOWN"
        return {"status": status}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v1/scan/{scan_id}/results")
async def scan_results(scan_id: str):
    try:
        result = await _sf_get(f"/scaneventresults", params={"id": scan_id})
        if isinstance(result, list):
            items = [{"type": r[4], "data": r[1], "source": r[2]}
                     for r in result if isinstance(r, list) and len(r) > 4]
            return {"data": items, "total": len(items)}
        return {"data": [], "total": 0}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v1/scanlist")
async def scanlist():
    try:
        result = await _sf_get("/scanlist")
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

