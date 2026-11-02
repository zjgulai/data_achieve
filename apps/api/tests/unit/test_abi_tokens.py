"""Pin the ABI token encryption and file parsing."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from data_intelligence_hub.abi.tokens import (
    TokenDecryptError,
    decrypt,
    encrypt,
    fingerprint,
    last4,
    parse_token_file,
)


def test_encrypt_roundtrip() -> None:
    key = Fernet.generate_key().decode()
    token = "apify_api_example_token_value"
    payload = encrypt(token, key)
    assert payload != token
    assert decrypt(payload, key) == token


def test_wrong_key_fails_closed() -> None:
    key = Fernet.generate_key().decode()
    other = Fernet.generate_key().decode()
    payload = encrypt("token", key)
    with pytest.raises(TokenDecryptError):
        decrypt(payload, other)


def test_fingerprint_and_last4_do_not_leak_token() -> None:
    token = "example-value-abcd"
    assert len(fingerprint(token)) == 32
    assert last4(token) == "abcd"
    assert token not in repr(fingerprint(token))


def test_parse_token_file_uses_last_field() -> None:
    entries = parse_token_file("t1 apify_api_one\nt2 apify_api_two\n")
    assert entries == [("t1", "apify_api_one"), ("t2", "apify_api_two")]


def test_parse_token_file_skips_comments_and_blank_lines() -> None:
    entries = parse_token_file("# comment\n\nt1 token\n")
    assert entries == [("t1", "token")]
