"""BCR-2020-006 crypto-psbt: UR payload is a CBOR byte-string of the PSBT."""

from .cbor_lite import (
    CBORDecoder,
    CBOREncoder,
    Flag_None,
    Tag_Major_byteString,
    Tag_Major_mask,
    Tag_Major_semantic,
    Tag_Minor_cborEncodedData,
)

PSBT_MAGIC = b"psbt\xff"
CRYPTO_PSBT_TAG = 310  # registry tag; omitted in UR because the type is in the path


def wrap_psbt_cbor(psbt) -> bytes:
    """CBOR-encode PSBT bytes as a bstr (Paytaca / Keystone / SeedSigner)."""
    if isinstance(psbt, (bytearray, memoryview)):
        psbt = bytes(psbt)
    if not isinstance(psbt, bytes):
        raise TypeError(f"PSBT must be bytes-like, got {type(psbt).__name__}")
    encoder = CBOREncoder()
    encoder.encodeBytes(psbt)
    return bytes(encoder.get_bytes())


def unwrap_psbt_cbor(cbor, _depth: int = 0) -> bytes:
    """Return raw PSBT bytes from a crypto-psbt UR CBOR payload.

    Accepts:
    - raw PSBT (legacy SeedCash encoder stored magic bytes as the UR message)
    - CBOR bstr wrapping the PSBT (BCR-2020-006 / Paytaca / Keystone)
    - optional tag 310 or tag 24 around that bstr
    """
    if isinstance(cbor, (bytearray, memoryview)):
        cbor = bytes(cbor)
    if not isinstance(cbor, bytes):
        raise TypeError(f"UR CBOR must be bytes-like, got {type(cbor).__name__}")
    if not cbor:
        raise ValueError("invalid PSBT magic")
    if cbor.startswith(PSBT_MAGIC):
        return cbor
    if _depth > 3:
        raise ValueError("invalid PSBT magic")

    major = cbor[0] & Tag_Major_mask
    decoder = CBORDecoder(cbor)

    if major == Tag_Major_semantic:
        _tag, value, _n = decoder.decodeTagAndValue(Flag_None)
        if value not in (CRYPTO_PSBT_TAG, Tag_Minor_cborEncodedData):
            raise ValueError("invalid PSBT magic")
        inner, _ = decoder.decodeBytes()
        return unwrap_psbt_cbor(inner, _depth + 1)

    if major == Tag_Major_byteString:
        inner, _ = decoder.decodeBytes()
        if inner.startswith(PSBT_MAGIC):
            return inner
        if inner and (inner[0] & Tag_Major_mask) in (
            Tag_Major_byteString,
            Tag_Major_semantic,
        ):
            try:
                return unwrap_psbt_cbor(inner, _depth + 1)
            except Exception:
                return inner
        return inner

    raise ValueError("invalid PSBT magic")
