"""Bounded fuzz: parsers must not hang, crash unbounded, or silently normalize."""

import pytest

from ctlab.cashtokens.prefix import TokenPrefixError, decode_token_prefix
from ctlab.psbt.codec import PsbtError, decode_psbt
from ctlab.protocol.compact_size import CompactSizeError, decode_compact_size


def test_compact_size_truncated():
    for raw in [b"", b"\xfd", b"\xfd\x00", b"\xfe\x00\x00", b"\xff" + b"\x00" * 3]:
        with pytest.raises(CompactSizeError):
            decode_compact_size(raw, 0)


def test_token_prefix_garbage_does_not_become_bch_only():
    # 0xef followed by junk must error, not return token=None (BCH-only).
    for blob in [b"\xef", b"\xef" + b"\x00" * 10, b"\xef" + b"\xff" * 33 + b"\x80"]:
        with pytest.raises(TokenPrefixError):
            decode_token_prefix(blob)


def test_psbt_truncated_and_bad_magic():
    with pytest.raises(PsbtError):
        decode_psbt(b"psbt")
    with pytest.raises(PsbtError):
        decode_psbt(b"XXXX\xff")
    with pytest.raises(PsbtError):
        decode_psbt(b"psbt\xff")


def test_psbt_duplicate_key_rejected():
    # magic + global map with two unsigned-tx keys of empty tx-like value
    from ctlab.protocol.compact_size import encode_compact_size

    def kv(k, v):
        return encode_compact_size(len(k)) + k + encode_compact_size(len(v)) + v

    fake_tx = b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # too short but key is duplicate
    body = kv(b"\x00", fake_tx) + kv(b"\x00", fake_tx) + b"\x00"
    with pytest.raises(PsbtError) as e:
        decode_psbt(b"psbt\xff" + body)
    assert e.value.code == "duplicate_key"
