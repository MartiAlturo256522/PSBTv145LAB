"""Live libauth encodeTokenPrefix vs lab encoder. SKIPPED if Node/libauth missing."""

from __future__ import annotations

from ctlab.cashtokens.prefix import Token, TokenNft, encode_token_prefix
from ctlab.validators.differential import try_libauth

UI = "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"


def test_libauth_prefix_non_palindrome_ft():
    oracle = try_libauth({"category_ui_hex": UI, "amount": 1})
    if oracle["status"] == "SKIPPED":
        import pytest

        pytest.skip(oracle["reason"])
    assert oracle["status"] == "ok", oracle
    lab = encode_token_prefix(Token(category=UI, amount=1))
    assert oracle["prefix_hex"] == lab.hex()


def test_libauth_prefix_hybrid():
    oracle = try_libauth(
        {
            "category_ui_hex": UI,
            "amount": 253,
            "nft": {"capability": "mutable", "commitment_hex": "ccdd"},
        }
    )
    if oracle["status"] == "SKIPPED":
        import pytest

        pytest.skip(oracle["reason"])
    lab = encode_token_prefix(
        Token(category=UI, amount=253, nft=TokenNft("mutable", bytes.fromhex("ccdd")))
    )
    assert oracle["prefix_hex"] == lab.hex()
