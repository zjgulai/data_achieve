"""Apify token encryption and account lookup for the ABI worker.

The long-term design stores one encrypted token per account in
``meta.apify_token``. The encryption key is ``ABI_FERNET_KEY``, separate from
``PLATFORM_CREDENTIAL_MASTER_KEY`` so one leak does not unlock both.

The plaintext token never leaves this module except as the return value of
``get_active_token``. Do not log it.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

KEY_VERSION = "abi.fernet.v1"


class TokenDecryptError(RuntimeError):
    """The stored payload cannot be decrypted with the configured key."""


def fingerprint(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def last4(token: str) -> str:
    return token[-4:]


def encrypt(token: str, key: str) -> str:
    return Fernet(key.encode("utf-8")).encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt(payload: str, key: str) -> str:
    try:
        return Fernet(key.encode("utf-8")).decrypt(payload.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise TokenDecryptError("abi_token_decrypt_failed") from exc


async def upsert_token(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    label: str,
    token: str,
    key: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO meta.apify_token
                (id, account_id, label, token_fingerprint, token_last4,
                 encrypted_payload, key_version, status)
            VALUES
                (gen_random_uuid(), :account_id, :label, :fingerprint, :last4,
                 :payload, :key_version, 'active')
            ON CONFLICT (account_id, label) DO UPDATE
            SET token_fingerprint = EXCLUDED.token_fingerprint,
                token_last4 = EXCLUDED.token_last4,
                encrypted_payload = EXCLUDED.encrypted_payload,
                key_version = EXCLUDED.key_version,
                status = 'active',
                last_error_code = NULL
            """
        ),
        {
            "account_id": account_id,
            "label": label,
            "fingerprint": fingerprint(token),
            "last4": last4(token),
            "payload": encrypt(token, key),
            "key_version": KEY_VERSION,
        },
    )


async def get_active_token(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    key: str,
) -> str | None:
    row = (
        await session.execute(
            text(
                """
                SELECT encrypted_payload
                FROM meta.apify_token
                WHERE account_id = :account_id AND status = 'active'
                ORDER BY last_used_at NULLS FIRST, created_at
                LIMIT 1
                """
            ),
            {"account_id": account_id},
        )
    ).first()
    if row is None:
        return None
    return decrypt(str(row.encrypted_payload), key)


async def mark_used(session: AsyncSession, *, account_id: uuid.UUID) -> None:
    await session.execute(
        text(
            """
            UPDATE meta.apify_token
            SET last_used_at = clock_timestamp()
            WHERE account_id = :account_id AND status = 'active'
            """
        ),
        {"account_id": account_id},
    )


async def account_has_token(session: AsyncSession, account_id: uuid.UUID) -> bool:
    row = (
        await session.execute(
            text(
                "SELECT 1 FROM meta.apify_token "
                "WHERE account_id = :account_id AND status = 'active' LIMIT 1"
            ),
            {"account_id": account_id},
        )
    ).first()
    return row is not None


def parse_token_file(text_value: str) -> list[tuple[str, str]]:
    """Parse ``label token`` lines. Only the last field is the token."""
    entries: list[tuple[str, str]] = []
    for line in text_value.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        token = parts[-1]
        label = " ".join(parts[:-1]) or f"t{len(entries) + 1}"
        entries.append((label, token))
    return entries


def mask_account(row: Any) -> dict[str, Any]:
    """Return a safe account summary for logs."""
    return {
        "id": str(row.id),
        "label": row.label,
        "apify_user_id": row.apify_user_id,
        "plan": row.plan,
    }
