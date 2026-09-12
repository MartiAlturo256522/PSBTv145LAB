#!/usr/bin/env python3
"""Paytaca-faithful PSBT map serializer.

THIS IS A PYTHON TRANSLATION of paytaca-app/src/lib/multisig/psbt.js
pinned to commit 9c338d2ce07ee33cda2cec33bb340657c6fc1990
(blob still identical at HEAD 6e8954511b1e0871cf1632f770665323d424f2a2).

It is NOT live Paytaca JavaScript. It MUST NOT be cited as the Paytaca
oracle. It exists so byte-level discrepancies versus Paytaca serialize()
are reproducible on a host without Node.

Behaviors cloned from psbt.js (line numbers at that commit):

* sortObjectKeys on hex *key type* strings, insertion order within type
  (GlobalMap.serialize ~L619, PsbtInput.serialize ~L941, libauth
  sortObjectKeys = Object.keys.sort localeCompare 'en')
* InputMap.serialize appends an extra 0x00 after every input map (L1261)
* InputMap.deserialize skips one extra byte after the last input (L1273)
* Each map itself already ends with a 0x00 separator
* OutputMap does not add an extra trailing separator

No imports from ctlab.
"""

from __future__ import annotations

from typing import Iterable

MAGIC = b"psbt\xff"


def encode_compact_size(n: int) -> bytes:
    if n < 0:
        raise ValueError(f"CompactSize negative {n}")
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    if n <= 0xFFFFFFFFFFFFFFFF:
        return b"\xff" + n.to_bytes(8, "little")
    raise ValueError(f"CompactSize overflow {n}")


def decode_compact_size(buf: bytes, pos: int) -> tuple[int, int]:
    if pos >= len(buf):
        raise ValueError(f"truncated CompactSize at {pos}")
    b = buf[pos]
    if b < 0xFD:
        return b, pos + 1
    if b == 0xFD:
        if pos + 3 > len(buf):
            raise ValueError(f"truncated 0xfd at {pos}")
        return int.from_bytes(buf[pos + 1 : pos + 3], "little"), pos + 3
    if b == 0xFE:
        if pos + 5 > len(buf):
            raise ValueError(f"truncated 0xfe at {pos}")
        return int.from_bytes(buf[pos + 1 : pos + 5], "little"), pos + 5
    if pos + 9 > len(buf):
        raise ValueError(f"truncated 0xff at {pos}")
    return int.from_bytes(buf[pos + 1 : pos + 9], "little"), pos + 9


def _kv(key: bytes, value: bytes) -> bytes:
    return encode_compact_size(len(key)) + key + encode_compact_size(len(value)) + value


def type_hex(key: bytes) -> str:
    """Paytaca object key: first byte as lowercase hex (e.g. '0e', 'fb')."""
    if not key:
        return ""
    return f"{key[0]:02x}"


def is_js_array_index_key(s: str) -> bool:
    """CanonicalNumericIndexString: ``\"10\"`` yes, ``\"00\"`` no."""
    if not s or not s.isdigit() or (len(s) > 1 and s[0] == "0"):
        return False
    n = int(s)
    return 0 <= n <= 0xFFFFFFFF and str(n) == s


def js_object_keys_after_sort(type_hexes: list[str]) -> list[str]:
    """localeCompare then Object.keys after sortObjectKeys object rebuild."""
    loc = sorted(type_hexes)
    idx = sorted((t for t in loc if is_js_array_index_key(t)), key=int)
    rest = [t for t in loc if not is_js_array_index_key(t)]
    return idx + rest


def sort_pairs_paytaca(pairs: Iterable[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """Clone Paytaca serialize key order (JS Object.keys after sortObjectKeys).

    Same-type keys keep insertion order (Paytaca stores them in an array).
    """
    groups: dict[str, list[tuple[bytes, bytes]]] = {}
    for key, value in pairs:
        t = type_hex(key)
        groups.setdefault(t, []).append((key, value))
    out: list[tuple[bytes, bytes]] = []
    for t in js_object_keys_after_sort(list(groups.keys())):
        out.extend(groups[t])
    return out


def serialize_map(pairs: Iterable[tuple[bytes, bytes]]) -> bytes:
    parts = [_kv(k, v) for k, v in sort_pairs_paytaca(pairs)]
    parts.append(b"\x00")
    return b"".join(parts)


def serialize_paytaca(
    global_pairs: list[tuple[bytes, bytes]],
    inputs: list[list[tuple[bytes, bytes]]],
    outputs: list[list[tuple[bytes, bytes]]],
) -> bytes:
    """Bytes Paytaca Psbt.serialize() would emit for these maps."""
    parts = [MAGIC, serialize_map(global_pairs)]
    for imap in inputs:
        parts.append(serialize_map(imap))
    parts.append(b"\x00")  # InputMap extra separator (psbt.js L1261)
    for omap in outputs:
        parts.append(serialize_map(omap))
    return b"".join(parts)


def serialize_bip174(
    global_pairs: list[tuple[bytes, bytes]],
    inputs: list[list[tuple[bytes, bytes]]],
    outputs: list[list[tuple[bytes, bytes]]],
) -> bytes:
    """BIP-174 shaped maps in given pair order (no type-sort, no extra 00)."""
    parts = [MAGIC]
    for k, v in global_pairs:
        parts.append(_kv(k, v))
    parts.append(b"\x00")
    for imap in inputs:
        for k, v in imap:
            parts.append(_kv(k, v))
        parts.append(b"\x00")
    for omap in outputs:
        for k, v in omap:
            parts.append(_kv(k, v))
        parts.append(b"\x00")
    return b"".join(parts)


def parse_map(buf: bytes, pos: int) -> tuple[list[tuple[bytes, bytes]], int]:
    pairs: list[tuple[bytes, bytes]] = []
    seen: set[bytes] = set()
    while pos < len(buf):
        klen, pos = decode_compact_size(buf, pos)
        if klen == 0:
            return pairs, pos
        if pos + klen > len(buf):
            raise ValueError("truncated key")
        key = buf[pos : pos + klen]
        pos += klen
        vlen, pos = decode_compact_size(buf, pos)
        if pos + vlen > len(buf):
            raise ValueError("truncated value")
        value = buf[pos : pos + vlen]
        pos += vlen
        if key in seen:
            raise ValueError(f"duplicate key {key.hex()}")
        seen.add(key)
        pairs.append((key, value))
    raise ValueError("map missing separator")


def _counts_from_global(pairs: list[tuple[bytes, bytes]]) -> tuple[int, int, int | None]:
    n_in = n_out = None
    version = None
    unsigned = None
    for key, value in pairs:
        if not key:
            continue
        t = key[0]
        if t == 0x04:
            n_in, _ = decode_compact_size(value, 0)
        elif t == 0x05:
            n_out, _ = decode_compact_size(value, 0)
        elif t == 0xFB and len(value) == 4:
            version = int.from_bytes(value, "little")
        elif t == 0x00:
            unsigned = value
    if unsigned is not None:
        p = 4
        vin, p = decode_compact_size(unsigned, p)
        if n_in is None:
            n_in = vin
        for _ in range(vin):
            p += 32 + 4
            sl, p = decode_compact_size(unsigned, p)
            p += sl + 4
        vout, p = decode_compact_size(unsigned, p)
        if n_out is None:
            n_out = vout
    if n_in is None or n_out is None:
        raise ValueError("cannot determine input/output counts")
    return n_in, n_out, version


def parse_psbt(buf: bytes, extra_input_separator: bool | None = None) -> dict:
    """Parse a PSBT.

    extra_input_separator:
      True  — require Paytaca extra 0x00 after inputs
      False — BIP-174, no extra byte
      None  — try BIP-174 first, then Paytaca
    """
    if buf[:5] != MAGIC:
        raise ValueError("bad magic")
    pos = 5
    global_pairs, pos = parse_map(buf, pos)
    n_in, n_out, version = _counts_from_global(global_pairs)

    def read_io(start: int, skip_extra: bool) -> tuple[list, list, int, bool]:
        p = start
        inputs = []
        for _ in range(n_in):
            pairs, p = parse_map(buf, p)
            inputs.append(pairs)
        had_extra = False
        if skip_extra:
            if p >= len(buf) or buf[p] != 0x00:
                raise ValueError("missing Paytaca extra input separator")
            had_extra = True
            p += 1
        outputs = []
        for _ in range(n_out):
            pairs, p = parse_map(buf, p)
            outputs.append(pairs)
        return inputs, outputs, p, had_extra

    attempts: list[bool]
    if extra_input_separator is None:
        attempts = [False, True]
    else:
        attempts = [bool(extra_input_separator)]

    last_err: Exception | None = None
    for skip in attempts:
        try:
            inputs, outputs, end, had_extra = read_io(pos, skip)
        except Exception as e:
            last_err = e
            continue
        trailing = buf[end:]
        ok = end == len(buf)
        if ok or extra_input_separator is not None:
            return {
                "global": global_pairs,
                "inputs": inputs,
                "outputs": outputs,
                "version": version,
                "n_in": n_in,
                "n_out": n_out,
                "extra_input_separator": had_extra,
                "trailing": trailing,
                "ok": ok,
                "dialect": "paytaca" if had_extra else "bip174",
            }
    if last_err:
        raise last_err
    raise ValueError("unable to parse PSBT maps")


def byte_diff(a: bytes, b: bytes) -> dict:
    n = min(len(a), len(b))
    first = None
    for i in range(n):
        if a[i] != b[i]:
            first = i
            break
    if first is None and len(a) != len(b):
        first = n
    return {
        "equal": a == b,
        "len_a": len(a),
        "len_b": len(b),
        "first_diff": first,
        "a_at": a[first : first + 16].hex() if first is not None else "",
        "b_at": b[first : first + 16].hex() if first is not None else "",
    }


def key_type_order(pairs: list[tuple[bytes, bytes]]) -> list[str]:
    return [type_hex(k) for k, _ in pairs]


def is_paytaca_type_sorted(pairs: list[tuple[bytes, bytes]]) -> bool:
    order = key_type_order(pairs)
    types: list[str] = []
    for t in order:
        if not types or types[-1] != t:
            types.append(t)
    return types == js_object_keys_after_sort(types)
