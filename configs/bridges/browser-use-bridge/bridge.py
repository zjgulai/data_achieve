"""Bridge: runs browser-use tasks in an isolated container.

browser-use 0.13.x hard-pins a large dependency set (pydantic, openai,
google-api-python-client, protobuf, websockets, ...). Installing it into the API
image would re-resolve roughly 190 extra packages and downgrade 18 of them, so
it lives in its own service instead — the same pattern as the Maigret and
SpiderFoot sidecars. The API image keeps its own lock untouched.

API:

    GET  /health   -> {"status", "provider", "model", "cdp", "browser_use"}
    POST /v1/run   -> {"ok", "result", "success", "steps", "urls", "backend",
                       "duration_ms"}  |  {"ok": false, "error", ...}

Environment:
    BROWSER_USE_LLM_PROVIDER   "anthropic" (default) or "openai"
    ANTHROPIC_API_KEY          required when provider=anthropic
    OPENAI_API_KEY             required when provider=openai
    BROWSER_USE_MODEL          overrides the per-provider default model
    OBSCURA_CDP_URL            optional CDP endpoint (anti-detect browser)
    OBSCURA_CDP_TOKEN          optional bearer token for that endpoint
    BROWSER_USE_TASK_TIMEOUT   default per-task timeout in seconds (120)
    BROWSER_USE_STEP_TIMEOUT   per-step timeout in seconds (180)
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="browser-use bridge")

SUPPORTED_PROVIDERS = {"anthropic", "openai"}
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-4o",
}
_CDP_PROBE_TIMEOUT_SECONDS = 5.0
_CLEANUP_TIMEOUT_SECONDS = 15.0


class RunRequest(BaseModel):
    task: str = Field(min_length=1)
    url: str = ""
    max_steps: int = Field(default=10, ge=1, le=50)
    timeout: int | None = None


def _provider() -> str:
    return os.environ.get("BROWSER_USE_LLM_PROVIDER", "anthropic").strip().lower()


def _model(provider: str) -> str:
    return os.environ.get("BROWSER_USE_MODEL", "").strip() or DEFAULT_MODELS[provider]


def _task_timeout(override: int | None) -> int:
    if override and override > 0:
        return override
    try:
        return int(os.environ.get("BROWSER_USE_TASK_TIMEOUT", "120"))
    except ValueError:
        return 120


def _step_timeout() -> float:
    try:
        return float(os.environ.get("BROWSER_USE_STEP_TIMEOUT", "180"))
    except ValueError:
        return 180.0


def _obscura_cdp_url() -> str | None:
    return os.environ.get("OBSCURA_CDP_URL", "").strip().rstrip("/") or None


def _obscura_headers() -> dict[str, str]:
    token = os.environ.get("OBSCURA_CDP_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"} or host.startswith("192.168."):
        raise ValueError("private or loopback URLs are not allowed")


def _build_llm() -> Any:
    provider = _provider()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported BROWSER_USE_LLM_PROVIDER={provider!r}. "
            "Must be 'anthropic' or 'openai'."
        )

    model = _model(provider)
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        from browser_use.llm.anthropic.chat import ChatAnthropic

        return ChatAnthropic(model=model, api_key=key)

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY not set")
    from browser_use.llm.openai.chat import ChatOpenAI

    return ChatOpenAI(model=model, api_key=key)


def _build_browser_session() -> Any:
    """Obscura over CDP when configured, otherwise a local headless Chromium."""
    from browser_use import BrowserProfile, BrowserSession

    profile_kwargs: dict[str, Any] = {}
    cdp_url = _obscura_cdp_url()
    if cdp_url:
        profile_kwargs["cdp_url"] = cdp_url
        headers = _obscura_headers()
        if headers:
            profile_kwargs["headers"] = headers
    else:
        profile_kwargs["headless"] = True
    return BrowserSession(browser_profile=BrowserProfile(**profile_kwargs))


async def _probe_cdp(cdp_url: str) -> str | None:
    """Return an error message when the CDP endpoint is unreachable, else None."""
    url = f"{cdp_url}/json/version"
    try:
        # trust_env=False: container-to-obscura traffic must not go via HTTP_PROXY.
        async with httpx.AsyncClient(
            timeout=_CDP_PROBE_TIMEOUT_SECONDS, trust_env=False
        ) as client:
            response = await client.get(url, headers=_obscura_headers() or {})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"cdp_unreachable: {url} ({exc.__class__.__name__})"
    return None


def _backend() -> str:
    return "obscura" if _obscura_cdp_url() else "chromium"


@app.get("/health")
async def health() -> dict[str, Any]:
    # browser_use has no __version__ attribute; the distribution metadata does.
    from importlib.metadata import PackageNotFoundError, version

    try:
        browser_use_version = version("browser-use")
    except PackageNotFoundError:
        browser_use_version = "unknown"

    provider = _provider()
    cdp_error: str | None = None
    cdp_url = _obscura_cdp_url()
    if cdp_url:
        cdp_error = await _probe_cdp(cdp_url)

    try:
        _build_llm()
        llm_error = None
    except (ValueError, ImportError) as exc:
        llm_error = str(exc)

    return {
        "status": "ok" if not (cdp_error or llm_error) else "degraded",
        "browser_use": browser_use_version,
        "provider": provider,
        "model": _model(provider) if provider in SUPPORTED_PROVIDERS else None,
        "llm_error": llm_error,
        "cdp_url": cdp_url,
        "cdp_error": cdp_error,
        "backend": _backend(),
    }


@app.post("/v1/run")
async def run_task(request: RunRequest) -> dict[str, Any]:
    from browser_use import Agent

    started = time.monotonic()
    try:
        if request.url:
            _assert_public_url(request.url)
        llm = _build_llm()
        browser_session = _build_browser_session()
    except (ValueError, ImportError) as exc:
        return {"ok": False, "error": str(exc), "backend": _backend()}

    timeout = _task_timeout(request.timeout)
    task = f"Starting at {request.url}\n\n{request.task}" if request.url else request.task
    agent: Any = None
    completed = False
    try:
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser_session,
            # This process is a FastAPI service; uvicorn owns signal handling.
            enable_signal_handler=False,
            step_timeout=_step_timeout(),
        )
        # agent.run() has no total-duration argument (max_steps defaults to 500),
        # so the wall clock is bounded here.
        history = await asyncio.wait_for(agent.run(max_steps=request.max_steps), timeout=timeout)
        completed = True
    except TimeoutError:
        return {
            "ok": False,
            "error": f"task_timeout: exceeded {timeout}s",
            "backend": _backend(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001 — surface any agent failure to the caller
        return {
            "ok": False,
            "error": f"{exc.__class__.__name__}: {exc}"[:500],
            "backend": _backend(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    finally:
        if agent is not None and not completed:
            # run() only closes the session on the happy path.
            try:
                await asyncio.wait_for(agent.close(), timeout=_CLEANUP_TIMEOUT_SECONDS)
            except Exception:  # noqa: BLE001 — cleanup must never mask the result
                pass

    result = history.final_result()
    urls = [u for u in (history.urls() or []) if u]
    return {
        "ok": True,
        "result": result,
        "success": history.is_successful(),
        "steps": len(history.history or []),
        "urls": list(dict.fromkeys(urls))[:20],
        "backend": _backend(),
        "provider": _provider(),
        "model": _model(_provider()),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "finished_at": datetime.now(UTC).isoformat(),
    }
