"""Paytaca PSBT v145 → SeedCash pipeline audit.

v145 here is Paytaca's BCH PSBT v2 extension (GLOBAL_VERSION=145, CashTokens
0x36, hybrid v0+v2 maps). Not BIP-44 coin type, not BIP-174 v0.

Does not import ctlab.psbt.codec for the SeedCash side.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

LAB = Path(__file__).resolve().parents[2]
SEEDCASH_SRC = Path(r"C:\Users\reque\seedcash\src")
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(SEEDCASH_SRC))
sys.path.insert(0, str(LAB / "desktop"))

from ctlab.engine import generate  # noqa: E402
from seedcash.helpers.ur2.crypto_psbt import unwrap_psbt_cbor  # noqa: E402
from seedcash.helpers.ur2.ur_decoder import URDecoder  # noqa: E402
from seedcash.models.psbt_parser import (  # noqa: E402
    PSBTParser,
    parse_keypairs,
    parse_psbt,
    parse_token_script,
    read_varint,
)

OUT_DIR = Path(__file__).resolve().parent
MAGIC = b"psbt\xff"


# ── Paytaca-aligned walker (skips extra input-map 0x00) ─────────────────

def walk_paytaca_v145(buf: bytes) -> dict[str, Any]:
    if buf[:5] != MAGIC:
        raise ValueError("not psbt magic")
    pos = 5
    global_pairs, pos = parse_keypairs(buf, pos)
    n_in = n_out = version = 0
    unsigned = None
    for key, value in global_pairs:
        t = key[0]
        if t == 0x00:
            unsigned = value
        elif t == 0x04:
            n_in, _ = read_varint(value, 0)
        elif t == 0x05:
            n_out, _ = read_varint(value, 0)
        elif t == 0xFB and len(value) >= 4:
            version = int.from_bytes(value[:4], "little")
    inputs = []
    for _ in range(n_in):
        pairs, pos = parse_keypairs(buf, pos)
        inputs.append(pairs)
    extra_sep = False
    if pos < len(buf) and buf[pos] == 0x00:
        extra_sep = True
        pos += 1
    outputs = []
    for _ in range(n_out):
        pairs, pos = parse_keypairs(buf, pos)
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
        "global_types": sorted({k[:1].hex() for k, _ in global_pairs}),
        "input_types": [sorted({k[:1].hex() for k, _ in m}) for m in inputs],
        "output_types": [sorted({k[:1].hex() for k, _ in m}) for m in outputs],
    }


def map_field(pairs, type_byte: int):
    for k, v in pairs:
        if k[0] == type_byte:
            return v
    return None


def token_from_36(value: bytes | None) -> dict | None:
    if not value:
        return None
    parsed = parse_token_script(value if value[:1] == b"\xef" else b"\xef" + value)
    if not parsed:
        return None
    td = parsed["data"]
    return {
        "category": td.category_id,
        "ft": td.ft_amount,
        "nft_cap": td.nft_data.capability if td.nft_data else None,
        "nft_commit": td.nft_data.commitment if td.nft_data else None,
        "prefix_hex": parsed["prefix"].hex(),
    }


def token_summary(td) -> dict | None:
    if td is None:
        return None
    return {
        "category": td.category_id,
        "ft": td.ft_amount,
        "nft_cap": td.nft_data.capability if td.nft_data else None,
        "nft_commit": td.nft_data.commitment if td.nft_data else None,
    }


def ui_route(parser: PSBTParser) -> str:
    if len(parser.inputs[0].items()) > 0:
        return "NFT_FIRST"
    if len(parser.inputs[1].items()) > 0:
        return "FT_FIRST"
    return "BCH_ONLY"


def shown_address_amounts(parser: PSBTParser) -> list[dict]:
    """Replicate PSBTAddressDetailsView pairing: dest list vs output_at_index."""
    dests = parser.destination_addresses
    rows = []
    for i, addr in enumerate(dests):
        out = parser.output_at_index(i)
        rows.append(
            {
                "dest_index": i,
                "shown_address": addr,
                "output_at_index_sats": None if out is None else out.value_satoshis,
                "output_at_index_script": None if out is None else out.script_pubkey[:1].hex(),
                "output_at_index_token": None if out is None else token_summary(out.token),
                "true_output_address": None if out is None else out.address,
                "address_matches_output": (out is not None and out.address == addr),
            }
        )
    return rows


# ── Cases ───────────────────────────────────────────────────────────────

def bch_io(ident: str, n_in: int, n_out: int, *, change: bool = False) -> dict:
    inputs = [
        {"kind": "bch", "key": chr(ord("A") + i), "owner": "alice", "sats": 50_000}
        for i in range(n_in)
    ]
    outputs = []
    owners = ["bob", "carol", "dave", "alice"]
    remaining = 50_000 * n_in - 2000
    for i in range(n_out):
        owner = "alice" if (change and i == n_out - 1) else owners[i % 3]
        sat = remaining // (n_out - i) if i < n_out - 1 else remaining
        remaining -= sat
        outputs.append({"owner": owner, "sats": max(sat, 546)})
    return {
        "id": ident,
        "dialect": "paytaca-145",
        "sign_state": "unsigned",
        "inputs": inputs,
        "outputs": outputs,
    }


CASES: list[tuple[str, str | dict, str]] = [
    ("IO-1-1", bch_io("IO-1-1", 1, 1), "1in/1out BCH"),
    ("IO-2-1", bch_io("IO-2-1", 2, 1), "2in/1out BCH"),
    ("IO-1-2", bch_io("IO-1-2", 1, 2, change=True), "1in/2out payment+change"),
    ("IO-2-2", bch_io("IO-2-2", 2, 2, change=True), "2in/2out payment+change"),
    ("IO-2-3", bch_io("IO-2-3", 2, 3, change=True), "2in/3out"),
    ("IO-3-2", bch_io("IO-3-2", 3, 2, change=True), "3in/2out"),
    ("GEN-01", "GEN-01", "NFT immutable genesis"),
    ("GEN-04", "GEN-04", "FT genesis"),
    ("GEN-05", "GEN-05", "hybrid NFT+FT genesis"),
    ("GEN-06", "GEN-06", "multi NFT genesis outputs"),
    ("GEN-08", "GEN-08", "two genesis categories"),
    ("POST-01", "POST-01", "mint NFT preserve baton"),
    ("POST-04", "POST-04", "mint + burn baton"),
    ("POST-08", "POST-08", "immutable NFT transfer"),
    ("SAMECAT-01", "SAMECAT-01", "same-category FT+NFT separate outs"),
    ("BURN-MULTI", "BURN-MULTI", "FT+NFT burn"),
    ("XGEN-07", "XGEN-07", "genesis + FT + NFT"),
    ("SCR-02", "SCR-02", "P2SH20 token output"),
    ("SCR-05", "SCR-05", "OP_RETURN before payment (WYSIWYS trap)"),
    ("BCMR-01", "BCMR-01", "OP_RETURN + hybrid genesis"),
    ("MONSTER-01", "MONSTER-01", "complex multi"),
]


def live_paytaca(hex_in: str) -> dict:
    try:
        from tools.oracles.compare_paytaca_real import paytaca_roundtrip  # type: ignore

        sys.path.insert(0, str(LAB))
        from tools.oracles.compare_paytaca_real import paytaca_roundtrip as pr

        r = pr(hex_in)
        return r
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ur_roundtrip(psbt_hex: str) -> dict:
    try:
        from application.ur_service import encode_ur

        ur = encode_ur(psbt_hex, "High")
        dec = URDecoder()
        for p in ur["parts"]:
            dec.receive_part(p)
            if dec.is_complete():
                break
        if not dec.is_complete():
            return {"ok": False, "error": "ur incomplete"}
        cbor = dec.result_message().cbor
        raw_cbor_magic = cbor[:5] == MAGIC
        unwrapped = unwrap_psbt_cbor(cbor)
        return {
            "ok": unwrapped.hex() == psbt_hex,
            "fragments": ur.get("fragmentsLength"),
            "cbor_is_raw_psbt": raw_cbor_magic,
            "unwrapped_eq": unwrapped.hex() == psbt_hex,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def run_case(ident: str, spec: str | dict, title: str) -> dict:
    row: dict[str, Any] = {"id": ident, "title": title, "findings": []}
    try:
        if isinstance(spec, str):
            vec = generate(spec, dialect="paytaca-145", sign="unsigned")
        else:
            vec = generate(spec, dialect="paytaca-145", sign="unsigned")
        raw = bytes.fromhex(vec["psbt_hex"])
        row["lab_bytes"] = len(raw)
        row["lab_vin"] = len(vec.get("outputs") and vec.get("source_utxos") or []) or None
        row["txid"] = vec.get("txid")
        sem = vec.get("semantics") or {}
        row["lab_semantics"] = {
            "genesis": sem.get("genesis_categories"),
            "burns": sem.get("burns"),
            "mint": sem.get("mint"),
        }
        pay = walk_paytaca_v145(raw)
        row["paytaca_walk"] = {
            "version": pay["version"],
            "n_in": pay["n_in"],
            "n_out": pay["n_out"],
            "extra_input_sep": pay["extra_input_sep"],
            "global_types": pay["global_types"],
            "output_types": pay["output_types"],
            "leftover": pay["leftover"],
            "has_unsigned_tx": pay["unsigned"] is not None,
            "has_0x36": any("36" in t for t in pay["output_types"]),
            "has_out_amount": any("03" in t for t in pay["output_types"]),
            "has_out_script": any("04" in t for t in pay["output_types"]),
        }
        if pay["version"] != 145:
            row["findings"].append("paytaca_walk.version != 145")
        if not pay["extra_input_sep"]:
            row["findings"].append("missing Paytaca extra input separator")

        # SeedCash map parse (does NOT skip extra 00)
        sc_maps = parse_psbt(raw)
        row["seedcash_maps"] = {
            "psbt_version": sc_maps["psbt_version"],
            "input_count": sc_maps["input_count"],
            "output_count": sc_maps["output_count"],
            "output_map_lens": [len(m) for m in sc_maps["outputs"]],
            "output_types": [sorted({k[:1].hex() for k, _ in m}) for m in sc_maps["outputs"]],
        }
        map_shift = sc_maps["outputs"] and len(sc_maps["outputs"][0]) == 0 and pay["n_out"] >= 1
        row["output_map_shifted"] = bool(map_shift)
        if map_shift:
            row["findings"].append("SeedCash consumed extra 0x00 as empty first output map")

        pay_36 = [token_from_36(map_field(m, 0x36)) for m in pay["outputs"]]
        sc_36 = [token_from_36(map_field(m, 0x36)) for m in sc_maps["outputs"]]
        row["paytaca_0x36"] = pay_36
        row["seedcash_0x36_from_maps"] = sc_36
        if pay_36 != sc_36:
            row["findings"].append("0x36 map contents differ Paytaca-walk vs SeedCash parse_psbt")

        parser = PSBTParser(bytearray(raw))
        model_outs = []
        for i, o in enumerate(parser.tx.outputs):
            model_outs.append(
                {
                    "i": i,
                    "sats": o.value_satoshis,
                    "address": o.address,
                    "script0": o.script_pubkey[:1].hex() if o.script_pubkey else None,
                    "token": token_summary(o.token),
                    "is_op_return": o.script_pubkey.startswith(b"\x6a") if o.script_pubkey else False,
                }
            )
        model_ins = []
        for i, inp in enumerate(parser.tx.inputs):
            so = inp.spent_output
            model_ins.append(
                {
                    "i": i,
                    "prev_index": inp.prev_index,
                    "sats": None if so is None else so.value_satoshis,
                    "token": None if so is None else token_summary(so.token),
                }
            )
        unsigned_tokens = [token_summary(o.token) for o in parser.tx.outputs]
        row["model"] = {
            "vin": parser.num_inputs,
            "vout": len(parser.tx.outputs),
            "input_sats": parser.input_amount,
            "output_sats": parser.output_amount,
            "fee": parser.fee_amount,
            "dest_addrs": parser.destination_addresses,
            "num_destinations": parser.num_destinations,
            "op_return": parser.op_return_data.hex() if parser.op_return_data else None,
            "nft_cats": parser.nft_categories,
            "ft_cats": parser.token_categories,
            "ui_route": ui_route(parser),
            "inputs": model_ins,
            "outputs": model_outs,
        }
        row["wysiwys"] = shown_address_amounts(parser)
        row["wysiwys_mismatch"] = any(not r["address_matches_output"] for r in row["wysiwys"])
        if row["wysiwys_mismatch"]:
            row["findings"].append("UI pairs destination_addresses[i] with output_at_index(i)")

        # Hybrid classification
        hybrids = [
            o
            for o in parser.tx.outputs
            if o.token and o.token.nft_data is not None and o.token.ft_amount
        ]
        row["hybrid_outputs"] = len(hybrids)
        if hybrids:
            for o in hybrids:
                cat = o.token.category_id
                in_nft = cat in parser.outputs[0]
                in_ft = cat in parser.outputs[1]
                row["hybrid_buckets"] = {"nft_bucket": in_nft, "ft_bucket": in_ft}
                if in_nft and not in_ft:
                    row["findings"].append("hybrid output classified NFT-only (FT amount dropped from FT bucket)")

        # Genesis blindness: token outputs, no token inputs
        token_ins = sum(1 for inp in parser.tx.inputs if inp.is_token_input)
        token_outs = sum(1 for o in parser.tx.outputs if o.is_token_output)
        row["token_ins"] = token_ins
        row["token_outs"] = token_outs
        if token_outs and token_ins == 0 and row["model"]["ui_route"] == "BCH_ONLY":
            row["findings"].append("genesis/token-out with no token-in routed to BCH_ONLY UI")

        # NFT warning polarity
        warnings = {}
        for cat in parser.nft_categories:
            warnings[cat] = parser.get_warning(cat)
        row["nft_warnings"] = warnings
        n_nft_in = sum(len(v) for v in parser.inputs[0].values())
        n_nft_out = sum(len(v) for v in parser.outputs[0].values())
        row["nft_in_out_counts"] = {"in": n_nft_in, "out": n_nft_out}
        if n_nft_in < n_nft_out and any(w == "burning" for w in warnings.values()):
            row["findings"].append("get_warning BURNING when NFT outputs > inputs (mint-like)")
        if n_nft_in > n_nft_out and not any(w == "burning" for w in warnings.values()):
            row["findings"].append("get_warning silent when NFT inputs > outputs (actual burn)")

        # 0x36 vs unsigned-tx tokens (Paytaca-aligned maps)
        row["unsigned_vs_0x36"] = []
        for i, o in enumerate(parser.tx.outputs):
            u = unsigned_tokens[i]
            p36 = pay_36[i] if i < len(pay_36) else None
            # prefix compare on category/ft/nft
            match = (u is None and p36 is None) or (
                u is not None
                and p36 is not None
                and u["category"] == p36["category"]
                and u["ft"] == p36["ft"]
                and u["nft_cap"] == p36["nft_cap"]
                and u["nft_commit"] == p36["nft_commit"]
            )
            if not match and not (u is None and p36 is None):
                # OP_RETURN has no 0x36
                if o.script_pubkey.startswith(b"\x6a") and p36 is None:
                    match = True
            row["unsigned_vs_0x36"].append({"i": i, "unsigned": u, "paytaca_0x36": p36, "match": match})
            if not match:
                row["findings"].append(f"vout{i} unsigned-tx token != Paytaca 0x36")

        # Spend shown on BCH overview = total outputs (includes change)
        if row["model"]["ui_route"] == "BCH_ONLY" and len(parser.destination_addresses) > 1:
            row["findings"].append("BCH overview spend_amount is sum of ALL outputs (change included as spend)")

        row["ur"] = ur_roundtrip(vec["psbt_hex"])
        if not row["ur"].get("ok"):
            row["findings"].append(f"UR roundtrip failed: {row['ur']}")
        elif row["ur"].get("cbor_is_raw_psbt"):
            row["findings"].append("UR CBOR was raw PSBT (non-spec); SeedCash legacy path")

        row["ok"] = True
    except Exception as e:
        row["ok"] = False
        row["error"] = f"{type(e).__name__}: {e}"
        row["traceback"] = traceback.format_exc()[-2000:]
        row["findings"].append(f"CRASH {row['error']}")
    return row


def main() -> int:
    results = [run_case(*c) for c in CASES]

    # Live Paytaca JS on a subset
    live = []
    try:
        sys.path.insert(0, str(LAB))
        from tools.oracles.compare_paytaca_real import paytaca_roundtrip

        for ident in ("GEN-04", "IO-2-3", "SCR-05", "POST-01", "MONSTER-01"):
            spec = next(s for s in CASES if s[0] == ident)[1]
            vec = generate(spec, dialect="paytaca-145", sign="unsigned")
            r = paytaca_roundtrip(vec["psbt_hex"])
            eq = r.get("ok") and r.get("output_hex") == vec["psbt_hex"]
            live.append({"id": ident, "ok": r.get("ok"), "byte_eq": eq, "error": r.get("error")})
    except Exception as e:
        live.append({"error": str(e)})

    summary = {
        "n": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "crash": [r["id"] for r in results if not r.get("ok")],
        "map_shift": [r["id"] for r in results if r.get("output_map_shifted")],
        "wysiwys": [r["id"] for r in results if r.get("wysiwys_mismatch")],
        "finding_counts": {},
    }
    for r in results:
        for f in r.get("findings") or []:
            summary["finding_counts"][f] = summary["finding_counts"].get(f, 0) + 1

    blob = {"summary": summary, "live_paytaca_js": live, "cases": results}
    (OUT_DIR / "results.json").write_text(json.dumps(blob, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("live", json.dumps(live, indent=2))
    for r in results:
        mark = "OK" if r.get("ok") else "FAIL"
        print(f"[{mark}] {r['id']:16} findings={len(r.get('findings') or [])} {r.get('findings') or r.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
