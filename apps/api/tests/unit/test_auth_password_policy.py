"""Pin the password length floor.

2026-10-29 the floor was lowered from 8 to 3 to unblock a test account, then
restored the same day. A release went out in between. Nothing in the test suite
noticed, because no test asserted the floor. This file is that assertion.

It also pins the register and login limits together. If they drift, one of two
deadlocks appears: an account can register but not log in, or the login form
accepts a password the register form rejects.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.auth import LoginRequest, RegisterRequest


def test_register_rejects_password_shorter_than_eight() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", password="a" * 7, name="User")


def test_register_accepts_eight_character_password() -> None:
    request = RegisterRequest(email="user@example.com", password="a" * 8, name="User")
    assert request.password == "a" * 8


def test_login_rejects_password_shorter_than_eight() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="a" * 7)


def test_register_and_login_share_the_same_floor() -> None:
    register = RegisterRequest.model_fields["password"].metadata
    login = LoginRequest.model_fields["password"].metadata

    def minimum(metadata: list[object]) -> int:
        for item in metadata:
            value = getattr(item, "min_length", None)
            if value is not None:
                return int(value)
        raise AssertionError("password field has no min_length constraint")

    assert minimum(register) == minimum(login) == 8


def test_password_max_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", password="a" * 129, name="User")
