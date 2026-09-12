"""Hostile PSBT: reject cleanly, never silent-accept truncation."""

import pytest

from ctlab.protocol.compact_size import encode_compact_size
from ctlab.psbt.codec import PsbtError, decode_psbt


def _kv(k: bytes, v: bytes) -> bytes:
    return encode_compact_size(len(k)) + k + encode_compact_size(len(v)) + v


def test_truncated_key_rejected():
    # keylen=10 but only 1 byte follows
    body = b"\x0a\xff" + b"\x00"
    with pytest.raises(PsbtError) as e:
        decode_psbt(b"psbt\xff" + body)
    assert e.value.code in ("truncated_key", "truncated_map", "truncated_value")


def test_value_length_past_eof_rejected():
    # global unsigned-tx key with value length 0xfd 0xff 0xff (65535) and no payload
    body = b"\x01\x00\xfd\xff\xff"
    with pytest.raises(PsbtError) as e:
        decode_psbt(b"psbt\xff" + body)
    assert e.value.code in ("truncated_value", "truncated_map")


def test_trailing_garbage_rejected():
    from ctlab.vectors.catalog import build_catalog
    from ctlab.vectors.generator import generate_vector

    sc = next(s for s in build_catalog() if s["id"] == "PSBT-01")
    v = generate_vector(sc, dialect="bip174-v0", sign_state="unsigned")
    raw = bytes.fromhex(v["psbt_hex"]) + b"\xff"
    with pytest.raises(PsbtError) as e:
        decode_psbt(raw)
    assert e.value.code == "trailing_bytes"
