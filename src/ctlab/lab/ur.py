"""BCR-2020-006 crypto-psbt CBOR wrap and Paytaca UR roundtrip.

UR payload is a CBOR major-type-2 bstr of the PSBT. Tag 310 is the registry
tag (omitted in UR because the type is in the path). Not BIP-174.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ctlab.psbt.codec import MAGIC

LAB = Path(__file__).resolve().parents[3]
CRYPTO_PSBT_TAG = 310
_TAG_CBOR_ENCODED = 24
_MAJOR_BSTR = 2
_MAJOR_TAG = 6
_MAJOR_MASK = 0xE0
_MINOR_MASK = 0x1F


def _as_bytes(value: bytes | bytearray | memoryview, name: str) -> bytes:
    if isinstance(value, (bytearray, memoryview)):
        value = bytes(value)
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes-like, got {type(value).__name__}")
    return value


def _cbor_uint_head(major: int, n: int) -> bytes:
    ai = major << 5
    if n < 24:
        return bytes([ai | n])
    if n < 256:
        return bytes([ai | 24, n])
    if n < 65536:
        return bytes([ai | 25]) + n.to_bytes(2, "big")
    if n < 2**32:
        return bytes([ai | 26]) + n.to_bytes(4, "big")
    if n < 2**64:
        return bytes([ai | 27]) + n.to_bytes(8, "big")
    raise ValueError("CBOR length overflow")


def wrap_psbt_cbor(psbt: bytes) -> bytes:
    """CBOR-encode PSBT bytes as a bstr (Paytaca / Keystone / SeedSigner)."""
    psbt = _as_bytes(psbt, "PSBT")
    return _cbor_uint_head(_MAJOR_BSTR, len(psbt)) + psbt


def _read_cbor_uint(buf: bytes, pos: int, additional: int) -> tuple[int, int]:
    if additional < 24:
        return additional, pos
    nbytes = {24: 1, 25: 2, 26: 4, 27: 8}.get(additional)
    if nbytes is None:
        raise ValueError("indefinite CBOR not supported")
    end = pos + nbytes
    if end > len(buf):
        raise ValueError("truncated CBOR")
    return int.from_bytes(buf[pos:end], "big"), end


def unwrap_psbt_cbor(cbor: bytes, _depth: int = 0) -> bytes:
    """Return raw PSBT bytes from a crypto-psbt UR CBOR payload.

    Accepts raw PSBT, CBOR bstr, and optional tag 310 or tag 24 around a bstr.
    """
    cbor = _as_bytes(cbor, "UR CBOR")
    if not cbor:
        raise ValueError("invalid PSBT magic")
    if cbor.startswith(MAGIC):
        return cbor
    if _depth > 3:
        raise ValueError("invalid PSBT magic")
    major = (cbor[0] & _MAJOR_MASK) >> 5
    additional = cbor[0] & _MINOR_MASK
    pos = 1
    if major == _MAJOR_TAG:
        tag, pos = _read_cbor_uint(cbor, pos, additional)
        if tag not in (CRYPTO_PSBT_TAG, _TAG_CBOR_ENCODED):
            raise ValueError("invalid PSBT magic")
        inner_n, pos = _decode_bstr_at(cbor, pos)
        return unwrap_psbt_cbor(inner_n, _depth + 1)
    if major == _MAJOR_BSTR:
        inner, _end = _decode_bstr_at(cbor, 0)
        if inner.startswith(MAGIC):
            return inner
        if inner and ((inner[0] & _MAJOR_MASK) >> 5) in (_MAJOR_BSTR, _MAJOR_TAG):
            try:
                return unwrap_psbt_cbor(inner, _depth + 1)
            except Exception:
                return inner
        return inner
    raise ValueError("invalid PSBT magic")


def _decode_bstr_at(buf: bytes, pos: int) -> tuple[bytes, int]:
    if pos >= len(buf):
        raise ValueError("truncated CBOR")
    major = (buf[pos] & _MAJOR_MASK) >> 5
    additional = buf[pos] & _MINOR_MASK
    if major != _MAJOR_BSTR:
        raise ValueError("invalid PSBT magic")
    n, pos = _read_cbor_uint(buf, pos + 1, additional)
    end = pos + n
    if end > len(buf):
        raise ValueError("truncated CBOR bstr")
    return buf[pos:end], end


def ur_node_modules_present() -> bool:
    nm = LAB / "desktop" / "ur" / "node_modules" / "@ngraveio" / "bc-ur"
    return nm.is_dir()


def roundtrip_ur(psbt_hex: str) -> dict[str, Any]:
    """Encode/decode via desktop ur_service.encode_ur. SKIPPED without node_modules."""
    if not ur_node_modules_present():
        return {"ok": False, "live": "SKIPPED"}
    try:
        desktop = str(LAB / "desktop")
        if desktop not in sys.path:
            sys.path.insert(0, desktop)
        from application.ur_service import decode_ur_parts, encode_ur

        raw = bytes.fromhex(psbt_hex.strip())
        ur = encode_ur(psbt_hex.strip(), "High")
        decoded = ur.get("decodedHex")
        if not decoded and ur.get("parts"):
            decoded = decode_ur_parts(ur["parts"])
        decoded = (decoded or "").strip().lower()
        want = raw.hex()
        unwrapped = unwrap_psbt_cbor(wrap_psbt_cbor(raw))
        preserved = decoded == want and unwrapped == raw and bool(ur.get("roundtrip", True))
        return {
            "ok": preserved,
            "live": True,
            "preserved": preserved,
            "decoded_hex": decoded,
            "fragments": ur.get("fragmentsLength"),
            "ur_roundtrip": ur.get("roundtrip"),
        }
    except Exception as e:
        return {"ok": False, "live": False, "error": f"{type(e).__name__}: {e}"}
