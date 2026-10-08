"""Independent Python CHIP prefix reference versus the production encoder."""

from __future__ import annotations

from core.cashtokens.prefix import Token, TokenNft, encode_token_prefix
from core.validators.differential import try_prefix_reference

UI = "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"


def test_python_reference_prefix_non_palindrome_ft():
    oracle = try_prefix_reference({"category_ui_hex": UI, "amount": 1})
    assert oracle["status"] == "ok", oracle
    lab = encode_token_prefix(Token(category=UI, amount=1))
    assert oracle["prefix_hex"] == lab.hex()


def test_python_reference_prefix_hybrid():
    oracle = try_prefix_reference(
        {
            "category_ui_hex": UI,
            "amount": 253,
            "nft": {"capability": "mutable", "commitment_hex": "ccdd"},
        }
    )
    assert oracle["status"] == "ok", oracle
    lab = encode_token_prefix(
        Token(category=UI, amount=253, nft=TokenNft("mutable", bytes.fromhex("ccdd")))
    )
    assert oracle["prefix_hex"] == lab.hex()
