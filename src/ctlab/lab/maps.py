"""Independent Paytaca-v145 map walker.

Does not import SeedCash. Skips the extra input-map 0x00 (psbt.js L1261/L1273).
Used to compare:
  semantic_tx_from_unsigned_tx  vs  semantic_tx_from_psbt_maps
"""

from __future__ import annotations

from typing import Any

from ctlab.cashtokens.prefix import TokenPrefixError, decode_token_prefix
from ctlab.protocol.compact_size import decode_compact_size
from ctlab.psbt.codec import MAGIC
from ctlab.transactions.serialize import decode_transaction

PSBT_OUT_AMOUNT = 0x03
PSBT_OUT_SCRIPT = 0x04
PSBT_OUT_CASHTOKEN = 0x36


def _parse_map(buf: bytes, pos: int) -> tuple[list[tuple[bytes, bytes]], int]:
    pairs: list[tuple[bytes, bytes]] = []
    while pos < len(buf):
        klen, pos, _ = decode_compact_size(buf, pos)
        if klen == 0:
            return pairs, pos
        key = buf[pos : pos + klen]
        pos += klen
        vlen, pos, _ = decode_compact_size(buf, pos)
        value = buf[pos : pos + vlen]
        pos += vlen
        pairs.append((key, value))
    raise ValueError("truncated psbt map")


def field(pairs: list[tuple[bytes, bytes]], type_byte: int) -> bytes | None:
    for k, v in pairs:
        if k[:1] == bytes([type_byte]):
            return v
    return None


def types_of(pairs: list[tuple[bytes, bytes]]) -> list[str]:
    return sorted({k[:1].hex() for k, _ in pairs})


def walk_paytaca_v145(buf: bytes) -> dict[str, Any]:
    if buf[:5] != MAGIC:
        raise ValueError("invalid PSBT magic")
    pos = 5
    global_pairs, pos = _parse_map(buf, pos)
    n_in = n_out = version = 0
    unsigned = None
    for key, value in global_pairs:
        t = key[0]
        if t == 0x00:
            unsigned = value
        elif t == 0x04:
            n_in, _, _ = decode_compact_size(value, 0)
        elif t == 0x05:
            n_out, _, _ = decode_compact_size(value, 0)
        elif t == 0xFB and len(value) >= 4:
            version = int.from_bytes(value[:4], "little")
    inputs = []
    for _ in range(n_in):
        pairs, pos = _parse_map(buf, pos)
        inputs.append(pairs)
    extra_sep = False
    if pos < len(buf) and buf[pos] == 0x00:
        extra_sep = True
        pos += 1
    outputs = []
    for _ in range(n_out):
        pairs, pos = _parse_map(buf, pos)
        outputs.append(pairs)
    return {
        "version": version,
        "n_in": n_in,
        "n_out": n_out,
        "unsigned": unsigned,
        "global": global_pairs,
        "inputs": inputs,
        "outputs": outputs,
        "extra_input_sep": extra_sep,
        "leftover": len(buf) - pos,
        "global_types": types_of(global_pairs),
        "input_types": [types_of(m) for m in inputs],
        "output_types": [types_of(m) for m in outputs],
    }


def walk_naive_no_skip(buf: bytes) -> dict[str, Any]:
    """BIP-174-style walk: do NOT skip Paytaca extra 0x00. SeedCash does this."""
    if buf[:5] != MAGIC:
        raise ValueError("invalid PSBT magic")
    pos = 5
    global_pairs, pos = _parse_map(buf, pos)
    n_in = n_out = 0
    unsigned = None
    version = 0
    for key, value in global_pairs:
        t = key[0]
        if t == 0x00:
            unsigned = value
        elif t == 0x04:
            n_in, _, _ = decode_compact_size(value, 0)
        elif t == 0x05:
            n_out, _, _ = decode_compact_size(value, 0)
        elif t == 0xFB and len(value) >= 4:
            version = int.from_bytes(value[:4], "little")
    if unsigned is not None:
        tx = decode_transaction(unsigned)
        if n_in == 0:
            n_in = len(tx.inputs)
        if n_out == 0:
            n_out = len(tx.outputs)
    inputs = []
    for _ in range(n_in):
        pairs, pos = _parse_map(buf, pos)
        inputs.append(pairs)
    outputs = []
    for _ in range(n_out):
        pairs, pos = _parse_map(buf, pos)
        outputs.append(pairs)
    return {
        "version": version,
        "n_in": n_in,
        "n_out": n_out,
        "unsigned": unsigned,
        "inputs": inputs,
        "outputs": outputs,
        "leftover": len(buf) - pos,
        "output_types": [types_of(m) for m in outputs],
        "output_map_lens": [len(m) for m in outputs],
        "first_map_empty": bool(outputs) and len(outputs[0]) == 0,
    }


def token_from_36(value: bytes | None) -> dict[str, Any] | None:
    if not value:
        return None
    raw = value if value[:1] == b"\xef" else b"\xef" + value
    try:
        tok, _pref, _lock = decode_token_prefix(raw)
    except TokenPrefixError:
        return {"raw": value.hex(), "error": "TokenPrefixError"}
    if tok is None:
        return None
    return {
        "category": tok.category,
        "amount": tok.amount,
        "nft_cap": tok.nft.capability if tok.nft else None,
        "nft_commit": tok.nft.commitment.hex() if tok.nft else None,
    }


def maps_vs_unsigned(buf: bytes) -> dict[str, Any]:
    pay = walk_paytaca_v145(buf)
    naive = walk_naive_no_skip(buf)
    unsigned = pay["unsigned"]
    tx = decode_transaction(unsigned) if unsigned else None
    diffs: list[str] = []
    if tx is None:
        diffs.append("no_unsigned_tx")
        return {"ok": False, "diffs": diffs, "paytaca": pay, "naive": naive}
    if pay["n_in"] != len(tx.inputs):
        diffs.append(f"vin maps={pay['n_in']} tx={len(tx.inputs)}")
    if pay["n_out"] != len(tx.outputs):
        diffs.append(f"vout maps={pay['n_out']} tx={len(tx.outputs)}")
    map_tokens = [token_from_36(field(m, PSBT_OUT_CASHTOKEN)) for m in pay["outputs"]]
    tx_tokens = []
    for out in tx.outputs:
        try:
            tok, _p, _l = decode_token_prefix(out.script_field())
        except TokenPrefixError:
            tok = out.token
        if tok is None:
            tx_tokens.append(None)
        else:
            tx_tokens.append(
                {
                    "category": tok.category,
                    "amount": tok.amount,
                    "nft_cap": tok.nft.capability if tok.nft else None,
                    "nft_commit": tok.nft.commitment.hex() if tok.nft else None,
                }
            )
    for i, (a, b) in enumerate(zip(map_tokens, tx_tokens)):
        if a != b:
            # OP_RETURN / no-token both None is ok
            if a is None and b is None:
                continue
            diffs.append(f"vout{i} 0x36!=unsigned_tx")
    for i, m in enumerate(pay["outputs"]):
        amt = field(m, PSBT_OUT_AMOUNT)
        if amt is not None and tx is not None and i < len(tx.outputs):
            sats = int.from_bytes(amt[:8], "little")
            if sats != tx.outputs[i].value_sats:
                diffs.append(f"vout{i} amount map={sats} tx={tx.outputs[i].value_sats}")
    shift = naive.get("first_map_empty") and pay["n_out"] >= 1
    last_lost = shift and pay["n_out"] >= 1 and len(naive.get("outputs") or []) == pay["n_out"]
    if shift:
        diffs.append("naive_parser_empty_first_output_map")
    return {
        "ok": not any(d.startswith("vout") or d.startswith("vin") for d in diffs if "naive" not in d),
        "version": pay["version"],
        "extra_input_sep": pay["extra_input_sep"],
        "naive_shift": bool(shift),
        "naive_last_map_dropped": bool(shift) and pay["n_out"] > 1,
        "diffs": diffs,
        "paytaca_output_types": pay["output_types"],
        "naive_output_types": naive.get("output_types"),
        "map_tokens": map_tokens,
        "tx_tokens": tx_tokens,
        "n_in": pay["n_in"],
        "n_out": pay["n_out"],
    }
