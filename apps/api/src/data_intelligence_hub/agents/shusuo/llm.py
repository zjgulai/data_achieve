"""数说的自由文本问答层。

只回答，不执行采集。未配置 DEEPSEEK_API_KEY 时返回 None，由调用方回退到帮助文本。
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是「数说」，Data Intelligence Hub（DIH）的飞书数据采集助手。

回答规则：
1. 用简洁中文回答，最多 400 字。
2. 你可以解释平台能力、采集命令、飞书事件回调、网络与部署问题。
3. 不要声称已经执行采集。需要数据时，给出确切命令，例如「搜 reddit AI」或「采集 <端点> key=value」。
4. 不要编造端点名。不确定时，建议用户发「平台」或「能力 <关键词>」。
5. 涉及权限、密钥、生产变更时，说明需要管理员操作。
6. 不要泄露任何密钥、token 或内部环境变量。
7. 当前能力口径：70 个平台包、286 个能力视图、258 个唯一端点；实时可用性以「总览」为准。
8. 如果问题与 DIH 无关，简短回答后把话题引回数据采集能力。"""


def _settings() -> tuple[str, str, str] | None:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "").strip() or "https://api.deepseek.com"
    model = os.environ.get("DEEPSEEK_MODEL", "").strip() or "deepseek-chat"
    return api_key, base_url.rstrip("/"), model


async def answer_question(question: str) -> str | None:
    """返回回答；未配置 key 或调用失败时返回 None。"""
    settings = _settings()
    if settings is None:
        return None
    api_key, base_url, model = settings
    question = question.strip()
    if not question:
        return None
    if len(question) > 2000:
        question = question[:2000]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - 问答失败必须回退，不能影响命令层
        logger.warning("shusuo_llm_failed: %s", exc)
        return None

    choices = data.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    return content.strip()
