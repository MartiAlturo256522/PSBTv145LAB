"""Pure Python crypto-psbt UR encoding and decoding for animated QR codes."""
from __future__ import annotations

from typing import Any

from core.psbt.codec import MAGIC
from .ur2.crypto_psbt import unwrap_psbt_cbor, wrap_psbt_cbor
from .ur2.ur import UR
from .ur2.ur_encoder import UREncoder
from .ur2.ur_decoder import URDecoder

# SeedCash SettingsConstants.QR_DENSITY_*; Maximum is a lab-only option.
DENSITY = {"Low": 30, "Medium": 65, "High": 120, "Maximum": 400}
SPEED_MS = {"Slow": 400, "Normal": 180, "Fast": 100, "Very fast": 50}


def decode_ur_parts(parts: list[str]) -> str:
    decoder = URDecoder()
    seen: set[str] = set()
    for part in parts:
        normalized = part.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if not part.lower().startswith("ur:crypto-psbt/"):
            raise ValueError("expected a crypto-psbt UR")
        if not decoder.receive_part(part):
            raise ValueError("invalid or incompatible UR fragment")
        if decoder.is_complete():
            break
    if not decoder.is_complete():
        raise ValueError("incomplete crypto-psbt UR")
    if decoder.is_failure():
        raise ValueError("crypto-psbt UR decoding failed") from decoder.result_error()
    raw = unwrap_psbt_cbor(decoder.result_message().cbor)
    if not raw.startswith(MAGIC):
        raise ValueError("invalid PSBT magic")
    return raw.hex()


def encode_ur(psbt_hex: str, density: str = "High") -> dict[str, Any]:
    raw = bytes.fromhex(psbt_hex.strip())
    if not raw.startswith(MAGIC):
        raise ValueError("invalid PSBT magic")
    max_fragment = DENSITY.get(density, DENSITY["High"])
    # Transport the original PSBT, including its uint32 little-endian version.
    # Receiver parser bugs must not be worked around by rewriting these bytes.
    payload = wrap_psbt_cbor(raw)
    encoder = UREncoder(UR("crypto-psbt", payload), max_fragment, min_fragment_len=min(10, len(payload)))
    count = encoder.fountain_encoder.seq_len()
    parts = [encoder.next_part().lower() for _ in range(1 if count == 1 else count * 2)]
    decoded = decode_ur_parts(parts)
    return {
        "ok": True,
        "type": "crypto-psbt",
        "density": density,
        "maxFragment": max_fragment,
        "fragmentsLength": count,
        "single": count == 1,
        "parts": parts,
        "uniqueParts": len(set(parts)),
        "roundtrip": decoded == raw.hex(),
        "decodedHex": decoded,
        "paytaca_compat": "crypto-psbt",
        "note": "SeedCash density sizes and CBOR crypto-psbt encoding; PSBT bytes preserved. Maximum is a lab-only density. Paytaca string identity is unverified.",
    }
