from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Header, Request, Response

from .collector_client import collect
from .config import get_cdo_settings
from .models import Action, TikTokIntent

router = APIRouter(tags=["tiktok-cdo"])


def verify_signature(token: str, timestamp: str, nonce: str, body: str, signature: str) -> bool:
    expected = hashlib.sha256(f"{timestamp}{nonce}{token}{body}".encode()).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_intent(text: str) -> TikTokIntent:
    normalized = text.strip()
    is_sentiment = any(word in normalized for word in ("舆情", "新闻", "监控"))
    action: Action = "sentiment" if is_sentiment else "search"
    return TikTokIntent(action=action, keyword=normalized)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_lark_signature: str | None = Header(None),
    x_lark_request_timestamp: str | None = Header(None),
    x_lark_request_nonce: str | None = Header(None),
) -> Response:
    body = await request.body()
    text = body.decode()
    event = json.loads(text)
    if event.get("type") == "url_verification":
        return Response(
            content=json.dumps({"challenge": event.get("challenge", "")}),
            media_type="application/json",
        )

    settings = get_cdo_settings()
    if settings.lark_cdo_verification_token and not verify_signature(
        settings.lark_cdo_verification_token,
        x_lark_request_timestamp or "",
        x_lark_request_nonce or "",
        text,
        x_lark_signature or "",
    ):
        return Response(content='{"code":403,"msg":"invalid signature"}', status_code=403)

    message = ((event.get("event") or {}).get("message") or {}).get("content", "{}")
    content = json.loads(message) if isinstance(message, str) else message
    query = str(content.get("text", "")).strip()
    if query:
        await collect(parse_intent(query))
    return Response(content='{"code":0}', media_type="application/json")
