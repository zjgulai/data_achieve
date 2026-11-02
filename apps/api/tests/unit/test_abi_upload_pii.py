"""Pin the credit-card scan against public platform IDs.

TikTok hashtag IDs are 16 digits and video IDs are 19 digits. A bare numeric
ID can pass the Luhn check by chance and be rejected as a credit card. The ETL
first slice hit two such rows out of 100.

The fix skips bare candidates that start with 1 or 7: no major card network
uses those prefixes. Separated candidates are still checked.
"""

from __future__ import annotations

from data_intelligence_hub.services.abi_upload import _contains_credit_card


def test_public_id_starting_with_one_is_not_a_card() -> None:
    assert _contains_credit_card("1654949266294789") is False


def test_public_id_starting_with_seven_is_not_a_card() -> None:
    # 16 digits, Luhn-valid, but starts with 7 and has no separators.
    assert _contains_credit_card("7000000000000005") is False


def test_visa_test_number_is_still_a_card() -> None:
    assert _contains_credit_card("4111111111111111") is True


def test_separated_visa_number_is_still_a_card() -> None:
    assert _contains_credit_card("4111 1111 1111 1111") is True


def test_text_without_digits_is_not_a_card() -> None:
    assert _contains_credit_card("no digits here") is False
