"""Adversarial PSBT maps: never crash, never silent-accept truncation."""

import pytest

from ctlab.psbt.codec import PsbtError, decode_psbt
from ctlab.protocol.compact_size import encode_compact_size


def test_empty_after_magic():
    with pytest.raises(PsbtError):
        decode_psbt(b"psbt\xff")


def test_global_separator_only():
    with pytest.raises(PsbtError):
        decode_psbt(b"psbt\xff\x00")


def test_duplicate_full_key_rejected():
    kv = encode_compact_size(1) + b"\xfb" + encode_compact_size(4) + (145).to_bytes(4, "little")
    body = kv + kv + b"\x00"
    with pytest.raises(PsbtError) as e:
        decode_psbt(b"psbt\xff" + body)
    assert e.value.code == "duplicate_key"


def test_paytaca_extra_separator_roundtrip():
    from ctlab.vectors.catalog import build_catalog
    from ctlab.vectors.generator import generate_vector
    from ctlab.psbt.codec import decode_psbt

    sc = next(s for s in build_catalog() if s["id"] == "PSBT-02")
    v = generate_vector(sc, dialect="paytaca-145", sign_state="unsigned")
    raw = bytes.fromhex(v["psbt_hex"])
    decoded = decode_psbt(raw)
    assert decoded.serialize() == raw


def test_huge_keylen_does_not_allocate_past_buffer():
    # CompactSize 0xfe + uint32 0x7fffffff as key length, no payload
    body = b"\xfe\xff\xff\xff\x7f"
    with pytest.raises(PsbtError):
        decode_psbt(b"psbt\xff" + body)
