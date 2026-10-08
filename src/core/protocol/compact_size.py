"""Bitcoin Cash CompactSize (canonical / minimally encoded).

Token prefixes MUST use minimally-encoded CompactSize values
(CHIP-2022-02-CashTokens v2.2.2).
"""

from __future__ import annotations


class CompactSizeError(ValueError):
    pass


def encode_compact_size(n: int) -> bytes:
    if n < 0:
        raise CompactSizeError(f"CompactSize cannot encode negative {n}")
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    if n <= 0xFFFFFFFFFFFFFFFF:
        return b"\xff" + n.to_bytes(8, "little")
    raise CompactSizeError(f"CompactSize overflow: {n}")


def is_minimal_compact_size(raw: bytes, n: int) -> bool:
    return raw == encode_compact_size(n)


def decode_compact_size(buf: bytes, pos: int = 0) -> tuple[int, int, bytes]:
    """Return (value, new_pos, raw_bytes). Rejects truncated input.

    Does NOT reject non-minimal encodings; callers that need consensus
    minimality must check ``is_minimal_compact_size``.
    """
    if pos >= len(buf):
        raise CompactSizeError("truncated CompactSize")
    first = buf[pos]
    if first < 0xFD:
        return first, pos + 1, buf[pos : pos + 1]
    if first == 0xFD:
        end = pos + 3
        if end > len(buf):
            raise CompactSizeError("truncated CompactSize 0xfd")
        n = int.from_bytes(buf[pos + 1 : end], "little")
        return n, end, buf[pos:end]
    if first == 0xFE:
        end = pos + 5
        if end > len(buf):
            raise CompactSizeError("truncated CompactSize 0xfe")
        n = int.from_bytes(buf[pos + 1 : end], "little")
        return n, end, buf[pos:end]
    end = pos + 9
    if end > len(buf):
        raise CompactSizeError("truncated CompactSize 0xff")
    n = int.from_bytes(buf[pos + 1 : end], "little")
    return n, end, buf[pos:end]
