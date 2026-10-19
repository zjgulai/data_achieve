"""飞书事件回调的加密与验签。

飞书规则（事件订阅 v2）：
- Encrypt Key 开启后，请求体是 {"encrypt": "<base64>"}。
- AES 密钥 = SHA256(encrypt_key)，AES-256-CBC，IV 是密文前 16 字节，PKCS7 填充。
- 签名 = SHA256(timestamp + nonce + encrypt_key + raw_body)。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class FeishuCryptoError(ValueError):
    pass


def decrypt_event(encrypt: str, encrypt_key: str) -> dict[str, object]:
    if not encrypt_key:
        raise FeishuCryptoError("encrypt_key is not configured")
    try:
        raw = base64.b64decode(encrypt)
    except Exception as exc:  # noqa: BLE001 - 输入来自外部，统一转成可读错误
        raise FeishuCryptoError("invalid base64 payload") from exc
    if len(raw) < 32:
        raise FeishuCryptoError("encrypted payload is too short")

    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    iv, ciphertext = raw[:16], raw[16:]
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    try:
        plaintext = unpadder.update(padded) + unpadder.finalize()
    except ValueError as exc:
        raise FeishuCryptoError("invalid PKCS7 padding") from exc

    try:
        decoded = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeishuCryptoError("decrypted payload is not JSON") from exc
    if not isinstance(decoded, dict):
        raise FeishuCryptoError("decrypted payload is not an object")
    return decoded


def verify_signature(
    *,
    encrypt_key: str,
    timestamp: str,
    nonce: str,
    body: str,
    signature: str,
) -> bool:
    if not encrypt_key or not timestamp or not nonce or not signature:
        return False
    expected = hashlib.sha256(
        f"{timestamp}{nonce}{encrypt_key}{body}".encode()
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
