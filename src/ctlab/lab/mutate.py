"""Semantic mutations of Paytaca PSBT v145 vectors and TransactionIntent.

Wire mutants rewrite a generated vector's ``psbt_hex`` (unsigned tx lives in
global 0x00). Intent mutants clone ``TransactionIntent`` and re-run
``engine.generate``. A single mutant never raises: on failure the original
PSBT is returned.

PSBT v145 is a Paytaca BCH extension of PSBT v2, not BIP-174.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from ctlab.cashtokens.prefix import (
    MAX_FT_AMOUNT,
    Token,
    TokenPrefixError,
    decode_token_prefix,
    encode_token_prefix,
)
from ctlab.lab.intent import OutputIntent, TransactionIntent
from ctlab.lab.maps import (
    PSBT_OUT_CASHTOKEN,
    walk_paytaca_v145,
)
from ctlab.protocol.compact_size import encode_compact_size
from ctlab.psbt.codec import MAGIC
from ctlab.transactions.serialize import decode_transaction, encode_transaction

EXPECTED_CLASSES = ("VALID", "MALFORMED", "AMBIGUOUS", "SECURITY-SENSITIVE")

WIRE_MUTATION_NAMES = (
    "swap_outputs_in_unsigned_only",
    "mutate_0x36_amount",
    "drop_last_output_map_bytes",
    "duplicate_global_unsigned",
    "truncate_psbt",
    "bad_magic",
    "remove_extra_00",
    "reorder_output_maps",
    "insert_empty_output_map",
)

INTENT_MUTATION_NAMES = (
    "swap_output_order",
    "insert_op_return_at_0",
    "change_one_output_sats",
)


def _kv(key: bytes, value: bytes) -> bytes:
    return encode_compact_size(len(key)) + key + encode_compact_size(len(value)) + value


def _serialize_map(pairs: list[tuple[bytes, bytes]]) -> bytes:
    return b"".join(_kv(k, v) for k, v in pairs) + b"\x00"


def serialize_walk(
    walk: dict[str, Any],
    *,
    extra_sep: bool | None = None,
    global_pairs: list[tuple[bytes, bytes]] | None = None,
    inputs: list[list[tuple[bytes, bytes]]] | None = None,
    outputs: list[list[tuple[bytes, bytes]]] | None = None,
) -> bytes:
    """Reserialize a ``walk_paytaca_v145`` result. Does not use codec.encode."""
    g = global_pairs if global_pairs is not None else walk["global"]
    ins = inputs if inputs is not None else walk["inputs"]
    outs = outputs if outputs is not None else walk["outputs"]
    sep = walk.get("extra_input_sep", True) if extra_sep is None else extra_sep
    parts = [MAGIC, _serialize_map(g)]
    for imap in ins:
        parts.append(_serialize_map(imap))
    if sep:
        parts.append(b"\x00")
    for omap in outs:
        parts.append(_serialize_map(omap))
    return b"".join(parts)


def _raw(vector_or_hex: dict[str, Any] | str | bytes | bytearray) -> bytes:
    if isinstance(vector_or_hex, dict):
        h = vector_or_hex.get("psbt_hex") or ""
        return bytes.fromhex(h) if h else b""
    if isinstance(vector_or_hex, (bytes, bytearray)):
        return bytes(vector_or_hex)
    if isinstance(vector_or_hex, str):
        return bytes.fromhex(vector_or_hex) if vector_or_hex else b""
    return b""


def _mutant(name: str, psbt_hex: str, description: str, expected_class: str) -> dict[str, Any]:
    return {
        "name": name,
        "psbt_hex": psbt_hex,
        "description": description,
        "expected_class": expected_class,
    }


def _set_global_unsigned(
    pairs: list[tuple[bytes, bytes]], unsigned: bytes
) -> list[tuple[bytes, bytes]]:
    out: list[tuple[bytes, bytes]] = []
    found = False
    for k, v in pairs:
        if k[:1] == b"\x00" and not found:
            out.append((k, unsigned))
            found = True
        else:
            out.append((k, v))
    if not found:
        out.insert(0, (b"\x00", unsigned))
    return out


def _swap_outputs_in_unsigned_only(buf: bytes) -> bytes:
    walk = walk_paytaca_v145(buf)
    unsigned = walk.get("unsigned")
    if not unsigned:
        return buf
    tx = decode_transaction(unsigned)
    if len(tx.outputs) < 2:
        return buf
    tx.outputs[0], tx.outputs[1] = tx.outputs[1], tx.outputs[0]
    new_unsigned = encode_transaction(tx)
    return serialize_walk(walk, global_pairs=_set_global_unsigned(walk["global"], new_unsigned))


def _bump_token_amount(value: bytes) -> bytes:
    if not value:
        return value
    raw = value if value[:1] == b"\xef" else b"\xef" + value
    try:
        tok, _, _ = decode_token_prefix(raw)
    except TokenPrefixError:
        b = bytearray(value)
        b[-1] ^= 0x01
        return bytes(b)
    if tok is None:
        return value
    new_amt = 1 if tok.amount < 1 else tok.amount + 1
    if new_amt > MAX_FT_AMOUNT:
        new_amt = max(1, tok.amount - 1)
    encoded = encode_token_prefix(Token(category=tok.category, amount=new_amt, nft=tok.nft))
    if value[:1] != b"\xef" and encoded[:1] == b"\xef":
        return encoded[1:]
    return encoded


def _mutate_0x36_amount(buf: bytes) -> bytes:
    walk = walk_paytaca_v145(buf)
    new_outs: list[list[tuple[bytes, bytes]]] = []
    changed = False
    for pairs in walk["outputs"]:
        np: list[tuple[bytes, bytes]] = []
        for k, v in pairs:
            if not changed and k[:1] == bytes([PSBT_OUT_CASHTOKEN]):
                nv = _bump_token_amount(v)
                if nv != v:
                    np.append((k, nv))
                    changed = True
                    continue
            np.append((k, v))
        new_outs.append(np)
    if not changed:
        return buf
    return serialize_walk(walk, outputs=new_outs)


def _drop_last_output_map_bytes(buf: bytes) -> bytes:
    walk = walk_paytaca_v145(buf)
    outs = walk.get("outputs") or []
    if not outs:
        return buf
    return serialize_walk(walk, outputs=outs[:-1])


def _duplicate_global_unsigned(buf: bytes) -> bytes:
    walk = walk_paytaca_v145(buf)
    unsigned = walk.get("unsigned") or b""
    g = list(walk["global"]) + [(b"\x00", unsigned)]
    return serialize_walk(walk, global_pairs=g)


def _truncate_psbt(buf: bytes) -> bytes:
    if len(buf) <= 6:
        return buf
    return buf[: max(6, len(buf) // 2)]


def _bad_magic(buf: bytes) -> bytes:
    if len(buf) < 5:
        return b"XXXX\xff"
    return b"XXXX\xff" + buf[5:]


def _remove_extra_00(buf: bytes) -> bytes:
    """BIP-174-like: drop Paytaca InputMap extra 0x00. MALFORMED vs Paytaca."""
    walk = walk_paytaca_v145(buf)
    if not walk.get("extra_input_sep"):
        return buf
    return serialize_walk(walk, extra_sep=False)


def _reorder_output_maps(buf: bytes) -> bytes:
    walk = walk_paytaca_v145(buf)
    outs = list(walk.get("outputs") or [])
    if len(outs) < 2:
        return buf
    rotated = [outs[-1]] + outs[:-1]
    return serialize_walk(walk, outputs=rotated)


def _insert_empty_output_map(buf: bytes) -> bytes:
    """Insert an empty output map immediately after the extra 0x00."""
    walk = walk_paytaca_v145(buf)
    return serialize_walk(walk, extra_sep=True, outputs=[[]] + list(walk.get("outputs") or []))


_WIRE: list[tuple[str, str, str, Callable[[bytes], bytes]]] = [
    (
        "swap_outputs_in_unsigned_only",
        "Swap vout0/vout1 in global unsigned tx; output maps unchanged.",
        "SECURITY-SENSITIVE",
        _swap_outputs_in_unsigned_only,
    ),
    (
        "mutate_0x36_amount",
        "Change PSBT_OUT_CASHTOKEN (0x36) amount; unsigned tx unchanged.",
        "SECURITY-SENSITIVE",
        _mutate_0x36_amount,
    ),
    (
        "drop_last_output_map_bytes",
        "Truncate after n-1 output maps (last output map bytes dropped).",
        "MALFORMED",
        _drop_last_output_map_bytes,
    ),
    (
        "duplicate_global_unsigned",
        "Duplicate global unsigned-tx key 0x00 (Paytaca array vs BIP-174 reject).",
        "AMBIGUOUS",
        _duplicate_global_unsigned,
    ),
    (
        "truncate_psbt",
        "Truncate the PSBT blob at half length.",
        "MALFORMED",
        _truncate_psbt,
    ),
    (
        "bad_magic",
        "Replace magic psbt\\xff with XXXX\\xff.",
        "MALFORMED",
        _bad_magic,
    ),
    (
        "remove_extra_00",
        "Remove Paytaca extra input-map 0x00 (BIP-174-like). MALFORMED relative to Paytaca.",
        "MALFORMED",
        _remove_extra_00,
    ),
    (
        "reorder_output_maps",
        "Rotate output maps; unsigned tx order unchanged.",
        "SECURITY-SENSITIVE",
        _reorder_output_maps,
    ),
    (
        "insert_empty_output_map",
        "Insert empty output map (00) after extra input-map 0x00.",
        "AMBIGUOUS",
        _insert_empty_output_map,
    ),
]


def mutate_psbt(
    vector_or_hex: dict[str, Any] | str | bytes | bytearray,
    intent: TransactionIntent | None = None,
) -> list[dict[str, Any]]:
    """Apply wire-level mutants. Optional ``intent`` appends intent-level mutants.

    Extra 0x00 is already present on Paytaca v145; ``remove_extra_00`` strips it.
    """
    original = _raw(vector_or_hex)
    original_hex = original.hex()
    out: list[dict[str, Any]] = []
    for name, desc, cls, fn in _WIRE:
        try:
            new_buf = fn(original) if original else original
            if not isinstance(new_buf, (bytes, bytearray)):
                new_buf = original
            out.append(_mutant(name, bytes(new_buf).hex(), desc, cls))
        except Exception:
            out.append(_mutant(name, original_hex, desc, cls))
    if intent is not None:
        out.extend(mutate_intent(intent))
    return out


def mutate_vector(vec: dict[str, Any], intent: TransactionIntent | None = None) -> list[dict[str, Any]]:
    return mutate_psbt(vec, intent=intent)


def _generate_hex(intent: TransactionIntent, fallback: str) -> str:
    from ctlab.engine import generate

    try:
        vec = generate(intent.to_engine_config(), dialect="paytaca-145", sign="unsigned")
        return vec.get("psbt_hex") or fallback
    except Exception:
        return fallback


def mutate_intent(intent: TransactionIntent) -> list[dict[str, Any]]:
    """Clone the intent, apply role/order/sats mutations, re-generate via engine."""
    orig_hex = _generate_hex(intent, "")
    out: list[dict[str, Any]] = []

    def emit(name: str, new_intent: TransactionIntent, desc: str, cls: str) -> None:
        try:
            hex_ = _generate_hex(new_intent, orig_hex)
            rec = _mutant(name, hex_, desc, cls)
            rec["intent"] = new_intent.to_json()
            out.append(rec)
        except Exception:
            rec = _mutant(name, orig_hex, desc, cls)
            rec["intent"] = intent.to_json()
            out.append(rec)

    outs = list(intent.outputs)
    if len(outs) >= 2:
        swapped = list(outs)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        emit(
            "swap_output_order",
            intent.clone(
                id=f"{intent.id}-swap-outs",
                outputs=swapped,
                mutations=list(intent.mutations) + ["swap_output_order"],
            ),
            "Swap first two output roles/order; re-generate.",
            "VALID",
        )
    else:
        rec = _mutant(
            "swap_output_order",
            orig_hex,
            "Swap first two output roles/order; re-generate.",
            "VALID",
        )
        rec["intent"] = intent.to_json()
        out.append(rec)

    opreturn = OutputIntent(owner="alice", sats=0, role="op_return", script="op_return")
    emit(
        "insert_op_return_at_0",
        intent.clone(
            id=f"{intent.id}-or0",
            outputs=[opreturn] + list(outs),
            mutations=list(intent.mutations) + ["insert_op_return_at_0"],
        ),
        "Insert OP_RETURN at output index 0; re-generate.",
        "VALID",
    )

    if outs:
        idx = next((i for i, o in enumerate(outs) if o.script != "op_return"), 0)
        changed = list(outs)
        changed[idx] = replace(changed[idx], sats=int(changed[idx].sats) + 1)
        emit(
            "change_one_output_sats",
            intent.clone(
                id=f"{intent.id}-sats",
                outputs=changed,
                mutations=list(intent.mutations) + ["change_one_output_sats"],
            ),
            "Increment one output's satoshis; re-generate.",
            "VALID",
        )
    else:
        rec = _mutant(
            "change_one_output_sats",
            orig_hex,
            "Increment one output's satoshis; re-generate.",
            "VALID",
        )
        rec["intent"] = intent.to_json()
        out.append(rec)

    return out
