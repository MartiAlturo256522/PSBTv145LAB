"""SeedCash UR:CRYPTO-PSBT.

The payload is the raw PSBT. SeedCash does not unwrap a BCR-2020 CBOR byte
string. Its decoder always drops the last 4 bytewords as the checksum, so the
CRC is fixed-width even though the vendored encoder sometimes is not.
"""

from __future__ import annotations

import sys
import zlib
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
_VENDOR = LAB / "vendor" / "seedcash" / "src"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

from seedcash.helpers.ur2.bytewords import get_minimal_word  # noqa: E402
from seedcash.helpers.ur2.fountain_encoder import FountainEncoder  # noqa: E402


def crc32_fixed(buf: bytes) -> bytes:
    return (zlib.crc32(buf) & 0xFFFFFFFF).to_bytes(4, "big")


def bytewords_minimal(buf: bytes) -> str:
    return "".join(get_minimal_word(b) for b in buf)


def _body(payload: bytes) -> str:
    return bytewords_minimal(payload + crc32_fixed(payload))


def encode_crypto_psbt(psbt: bytes, max_fragment_len: int = 300) -> dict:
    if not psbt:
        raise ValueError("PSBT vacío")
    max_fragment_len = max(10, int(max_fragment_len))
    fountain = FountainEncoder(psbt, max_fragment_len, 0, 10)
    if fountain.is_single_part():
        part = f"ur:crypto-psbt/{_body(psbt)}"
        return {"single": True, "parts": [part], "type": "crypto-psbt"}
    parts = []
    # One full set of fragments is enough to reassemble.
    for _ in range(fountain.seq_len()):
        part = fountain.next_part()
        seq = f"{part.seq_num}-{part.seq_len}"
        parts.append(f"ur:crypto-psbt/{seq}/{_body(part.cbor())}")
    return {"single": False, "parts": parts, "type": "crypto-psbt", "seq_len": fountain.seq_len()}
