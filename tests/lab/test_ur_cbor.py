"""CBOR bstr wrap of Paytaca v145 PSBT (BCR-2020-006 crypto-psbt)."""

from ctlab.engine import generate
from ctlab.lab.ur import roundtrip_ur, unwrap_psbt_cbor, wrap_psbt_cbor


def test_wrap_unwrap_gen04() -> None:
    vec = generate("GEN-04", dialect="paytaca-145", sign="unsigned")
    x = bytes.fromhex(vec["psbt_hex"])
    wrapped = wrap_psbt_cbor(x)
    assert not wrapped.startswith(b"psbt")
    assert unwrap_psbt_cbor(wrapped) == x
    assert unwrap_psbt_cbor(x) == x


def test_roundtrip_ur_gen04_preserves_bytes() -> None:
    vec = generate("GEN-04", dialect="paytaca-145", sign="unsigned")
    r = roundtrip_ur(vec["psbt_hex"])
    if r.get("live") == "SKIPPED":
        return
    assert r.get("ok") is True
    assert r.get("preserved") is True
    assert r["decoded_hex"] == bytes.fromhex(vec["psbt_hex"]).hex()
