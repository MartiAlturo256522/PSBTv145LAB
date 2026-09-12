"""Independent Paytaca v145 PSBT *map* serializer.

Built from Paytaca ``psbt.js`` @ ``9c338d2ce07ee33cda2cec33bb340657c6fc1990``
and libauth ``sortObjectKeys`` (``format/log.js``). Not a copy of
``src/ctlab/psbt/codec.py`` or ``audits/paytaca/paytaca_codec.py``.
No ``ctlab`` imports.

Evidence
--------
Magic: ``psbt.js`` ``PSBT_MAGIC = '70736274ff'`` / ``Magic.serialize``.

Each map pair (``Key.serialize`` + ``Value.serialize``)::

    CompactSize(keylen) || key || CompactSize(valuelen) || value

Map terminator: CompactSize 0 (``0x00``).

``InputMap.serialize`` (psbt.js ~L1256–L1261) concatenates every input
map, then appends one **extra** ``0x00``. ``OutputMap.serialize`` does
not. ``Psbt.serialize`` is magic || global || inputMap || outputMap.

Key grouping: Paytaca object keys are ``binToHex(keyType)`` of the first
byte (``Key.deserialize`` ``slice(0, 1)``). Duplicate types become
arrays; ``forEach`` keeps insertion order.

Serialize loop (GlobalMap / PsbtInput / PsbtOutput)::

    const sorted = sortObjectKeys(...)
    for (const keyType of Object.keys(sorted)) { ... }

libauth ``sortObjectKeys`` (``log.js``)::

    Object.keys(obj).sort((a, b) => a.localeCompare(b, 'en'))
    keys.reduce((all, key) => ({ ...all, [key]: val }), {})

That rebuild is not the final wire order. ECMAScript
``OrdinaryOwnPropertyKeys`` then makes ``Object.keys`` emit:

1. *array index* keys first, ascending numeric order
2. remaining string keys in creation order (localeCompare order among
   the non-index keys, because that is the reduce insertion order)

An array index is a CanonicalNumericIndexString whose canonical form is
``ToString(ToUint32(s)) === s``: decimal digits, no leading zeros except
``"0"``, value in ``0 .. 2**32-1``. Two-char hex types that qualify are
``"10"``..``"99"`` (``"10"``, ``"11"``, ``"12"``, …, ``"36"``, …).
``"00"``–``"09"`` fail (leading zero). ``"0e"``, ``"0f"``, ``"fb"``,
``"fc"`` fail (not canonical decimal). Node confirms ``localeCompare('en')``
equals code-point order for every two-char lowercase hex ``00``..``ff``.
"""

from __future__ import annotations

from typing import Iterable, Sequence

PSBT_MAGIC = b"psbt\xff"

__all__ = [
    "is_js_array_index_key",
    "js_object_keys_after_sort",
    "serialize_paytaca_v145",
]


def _compact_size(n: int) -> bytes:
    """Bitcoin CompactSize / libauth ``bigIntToCompactUint``."""
    if n < 0:
        raise ValueError(f"CompactSize negative: {n}")
    if n < 0xFD:
        return bytes((n,))
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    if n <= 0xFFFFFFFFFFFFFFFF:
        return b"\xff" + n.to_bytes(8, "little")
    raise ValueError(f"CompactSize overflow: {n}")


def _encode_pair(key: bytes, value: bytes) -> bytes:
    return _compact_size(len(key)) + key + _compact_size(len(value)) + value


def _type_hex(key: bytes) -> str:
    """Paytaca ``binToHex(keyType)`` — first byte, lowercase two-char hex."""
    if not key:
        return ""
    return f"{key[0]:02x}"


def is_js_array_index_key(s: str) -> bool:
    """True iff ``ToString(ToUint32(s)) === s`` (CanonicalNumericIndexString).

    ECMAScript treats such strings as integer-index property names.
    ``OrdinaryOwnPropertyKeys`` lists them before other string keys.
    ``"10"`` qualifies; ``"00"`` does not (canonical form is ``"0"``).
    """
    if not isinstance(s, str) or not s or not s.isdigit():
        return False
    if len(s) > 1 and s[0] == "0":
        return False
    n = int(s)
    return 0 <= n <= 0xFFFFFFFF and str(n) == s


def js_object_keys_after_sort(type_hex_list: Iterable[str]) -> list[str]:
    """``Object.keys(sortObjectKeys({[t]: 1, ...}))`` for unique type hexes.

    1. ``localeCompare('en')`` on the type strings (code-point order for
       two-char lowercase hex, verified in Node).
    2. Rebuild ``{[key]: val}`` in that order.
    3. ``Object.keys``: canonical array-index keys first (numeric), then
       the remaining keys in the rebuild insertion / localeCompare order.
    """
    seen: set[str] = set()
    unique: list[str] = []
    for raw in type_hex_list:
        t = raw if isinstance(raw, str) else str(raw)
        if t not in seen:
            seen.add(t)
            unique.append(t)
    locale_ordered = sorted(unique)
    index_keys = sorted(
        (t for t in locale_ordered if is_js_array_index_key(t)),
        key=int,
    )
    rest = [t for t in locale_ordered if not is_js_array_index_key(t)]
    return index_keys + rest


def _serialize_map(pairs: Iterable[tuple[bytes, bytes]]) -> bytes:
    groups: dict[str, list[tuple[bytes, bytes]]] = {}
    for key, value in pairs:
        key_b = bytes(key)
        value_b = bytes(value)
        groups.setdefault(_type_hex(key_b), []).append((key_b, value_b))
    out = bytearray()
    for t in js_object_keys_after_sort(groups.keys()):
        for key, value in groups[t]:
            out += _encode_pair(key, value)
    out += b"\x00"
    return bytes(out)


def serialize_paytaca_v145(
    global_pairs: Sequence[tuple[bytes, bytes]],
    inputs: Sequence[Sequence[tuple[bytes, bytes]]],
    outputs: Sequence[Sequence[tuple[bytes, bytes]]],
) -> bytes:
    """Bytes Paytaca ``Psbt.serialize()`` emits for these already-built maps.

    Pair lists are ``(key, value)`` with the full PSBT key (type byte plus
    any keydata). Same-type keys keep caller insertion order (Paytaca
    arrays). After every input map, one extra ``0x00`` is written
    (``InputMap.serialize`` L1261), including when there are zero inputs.
    """
    blob = bytearray(PSBT_MAGIC)
    blob += _serialize_map(global_pairs)
    for imap in inputs:
        blob += _serialize_map(imap)
    blob += b"\x00"
    for omap in outputs:
        blob += _serialize_map(omap)
    return bytes(blob)
