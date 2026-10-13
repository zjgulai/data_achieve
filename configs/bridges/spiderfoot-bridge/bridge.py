"""Bridge: wraps SpiderFoot Web UI routes into /api/v1/ REST API.

Row layouts below are fixed by the upstream web UI (sfwebui.py):

  /scaneventresults  -> [lastseen, data, source, module, confidence, visibility,
                         risk, hash, false_positive, parent_false_positive, type]
                        `data` and `source` arrive HTML-escaped (upstream calls
                        html.escape), so they are unescaped here. The event type
                        sits at index 10 — index 4 is the confidence.
  /scanstatus        -> [name, target, created, started, ended, status, riskmatrix]
  /scanerrors        -> [generated, component, message]
  /scancorrelations  -> [id, title, rule_id, rule_risk, rule_name, rule_descr,
                         rule_logic, event_count]
"""
import asyncio, os, json, uuid, re, html
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
SF_URL = os.environ.get("SF_UPSTREAM", "http://spiderfoot:5001")

# "passive" is the only use case that never runs active/invasive modules
# (port scanners, nmap). Callers can request a broader group explicitly.
DEFAULT_USECASE = "passive"


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
    usecase = body.get("usecase") or DEFAULT_USECASE
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
            items = [
                {
                    "type": r[10],
                    "data": html.unescape(str(r[1])),
                    "source": html.unescape(str(r[2])),
                    "module": r[3],
                    "confidence": r[4],
                    "visibility": r[5],
                    "risk": r[6],
                    "false_positive": r[8],
                    "parent_false_positive": r[9],
                    "lastseen": r[0],
                }
                for r in result if isinstance(r, list) and len(r) >= 11
            ]
            return {"data": items, "total": len(items)}
        return {"data": [], "total": 0}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v1/scan/{scan_id}/errors")
async def scan_errors(scan_id: str, limit: int = 50):
    """Module-level errors (upstream filters tbl_scan_log by type='ERROR')."""
    try:
        result = await _sf_get(
            "/scanerrors", params={"id": scan_id, "limit": str(limit)}
        )
        if isinstance(result, list):
            items = [
                {
                    "time": r[0],
                    "component": r[1],
                    "message": html.unescape(str(r[2])),
                }
                for r in result if isinstance(r, list) and len(r) >= 3
            ]
            return {"data": items, "total": len(items)}
        return {"data": [], "total": 0}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v1/scan/{scan_id}/correlations")
async def scan_correlations(scan_id: str):
    """Cross-module correlation rules that fired during the scan."""
    try:
        result = await _sf_get("/scancorrelations", params={"id": scan_id})
        if isinstance(result, list):
            items = [
                {
                    "id": r[0],
                    "title": r[1],
                    "rule_id": r[2],
                    "rule_risk": r[3],
                    "rule_name": r[4],
                    "rule_descr": r[5],
                    "rule_logic": r[6],
                    "event_count": r[7],
                }
                for r in result if isinstance(r, list) and len(r) >= 8
            ]
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

