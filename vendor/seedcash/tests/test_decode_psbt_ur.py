"""UR:crypto-psbt must unwrap CBOR before parse_psbt (invalid PSBT magic)."""

from seedcash.helpers.ur2.cbor_lite import CBOREncoder
from seedcash.helpers.ur2.crypto_psbt import unwrap_psbt_cbor, wrap_psbt_cbor
from seedcash.helpers.ur2.ur import UR
from seedcash.helpers.ur2.ur_decoder import URDecoder
from seedcash.helpers.ur2.ur_encoder import UREncoder


PSBT_STUB = b"psbt\xff" + b"\x00" + b"\x00" + b"\x00" + b"\x00" * 24


def _roundtrip(cbor_payload: bytes) -> bytes:
    ur = UR("crypto-psbt", cbor_payload)
    encoder = UREncoder(ur=ur, max_fragment_len=200)
    dec = URDecoder()
    assert dec.receive_part(encoder.next_part())
    assert dec.is_complete()
    return unwrap_psbt_cbor(dec.result_message().cbor)


def test_unwrap_raw_legacy():
    assert unwrap_psbt_cbor(PSBT_STUB) == PSBT_STUB


def test_unwrap_cbor_bstr():
    wrapped = wrap_psbt_cbor(PSBT_STUB)
    assert wrapped[:1] != b"p"
    assert unwrap_psbt_cbor(wrapped) == PSBT_STUB


def test_unwrap_tag_310():
    inner = wrap_psbt_cbor(PSBT_STUB)
    enc = CBOREncoder()
    enc.encodeTagAndValue(6 << 5, 310)
    tagged = bytes(enc.get_bytes()) + inner
    assert unwrap_psbt_cbor(tagged) == PSBT_STUB


def test_ur_paytaca_style_roundtrip():
    out = _roundtrip(wrap_psbt_cbor(PSBT_STUB))
    assert out == PSBT_STUB
    assert out[:5] == b"psbt\xff"


def test_ur_legacy_raw_still_works():
    assert _roundtrip(PSBT_STUB) == PSBT_STUB
