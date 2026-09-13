"""Capture SeedCash PSBT parse + review model without GUI or hardware.

SeedCash is imported only inside functions. Never import decode_qr, views,
or RPi drivers. Signing is not invoked; the signer hashes unsigned_tx.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SEEDCASH_SRC = Path(r"C:\Users\reque\seedcash\src")

# BitcoinCashSigner.signed_psbt hashes parsed["unsigned_tx"] and splices the
# original input-map tail. Output-map shift does not change signed bytes.
SIGNED_FOLLOWS_UNSIGNED_TX = True


def _ensure_seedcash_path() -> None:
    p = str(SEEDCASH_SRC)
    if p not in sys.path:
        sys.path.insert(0, p)


def _psbt_parser_mod():
    _ensure_seedcash_path()
    from seedcash.models.psbt_parser import PSBTParser, parse_psbt

    return PSBTParser, parse_psbt


def _token_summary(td: Any) -> dict[str, Any] | None:
    if td is None:
        return None
    nft = getattr(td, "nft_data", None)
    return {
        "category": td.category_id,
        "ft": td.ft_amount,
        "nft_cap": None if nft is None else nft.capability,
        "nft_commit": None if nft is None else nft.commitment,
    }


def _map_types(pairs: list[tuple[bytes, bytes]]) -> list[str]:
    return sorted({k[:1].hex() for k, _ in pairs})


def ui_route(parser: Any) -> str:
    """Mirror LoadingPSBTView: NFT inputs, else FT inputs, else BCH."""
    if len(parser.inputs[0].items()) > 0:
        return "NFT_FIRST"
    if len(parser.inputs[1].items()) > 0:
        return "FT_FIRST"
    return "BCH_ONLY"


def shown_address_amounts(parser: Any) -> list[dict[str, Any]]:
    """PSBTAddressDetailsView pairing: dest list index vs output_at_index(i)."""
    dests = parser.destination_addresses
    rows: list[dict[str, Any]] = []
    for i, addr in enumerate(dests):
        out = parser.output_at_index(i)
        spk = b"" if out is None else (out.script_pubkey or b"")
        rows.append(
            {
                "dest_index": i,
                "shown_address": addr,
                "output_at_index_sats": None if out is None else out.value_satoshis,
                "output_at_index_script": None if not spk else spk[:1].hex(),
                "output_at_index_is_op_return": spk.startswith(b"\x6a"),
                "output_at_index_token": None if out is None else _token_summary(out.token),
                "true_output_address": None if out is None else out.address,
                "address_matches_output": out is not None and out.address == addr,
            }
        )
    return rows


def hybrid_outputs(parser: Any) -> list[dict[str, Any]]:
    """Outputs with both nft_data and ft_amount; whether they sit in the FT bucket."""
    rows: list[dict[str, Any]] = []
    for i, out in enumerate(parser.tx.outputs):
        tok = out.token
        if tok is None or tok.nft_data is None or not tok.ft_amount:
            continue
        cat = tok.category_id
        nft_list = parser.outputs[0].get(cat, [])
        ft_list = parser.outputs[1].get(cat, [])
        rows.append(
            {
                "vout": i,
                "category": cat,
                "ft_amount": tok.ft_amount,
                "nft_cap": tok.nft_data.capability,
                "in_nft_bucket": out in nft_list,
                "in_ft_bucket": out in ft_list,
            }
        )
    return rows


def nft_warnings(parser: Any) -> dict[str, str | None]:
    cats = set(parser.nft_categories)
    cats.update(parser.outputs[0].keys())
    return {cat: parser.get_warning(cat) for cat in sorted(cats)}


def parse_psbt_maps(raw: bytes) -> dict[str, Any]:
    """SeedCash parse_psbt maps (does not skip Paytaca extra input-map 0x00)."""
    _PSBTParser, parse_psbt = _psbt_parser_mod()
    parsed = parse_psbt(raw)
    outputs = parsed["outputs"]
    return {
        "psbt_version": parsed["psbt_version"],
        "input_count": parsed["input_count"],
        "output_count": parsed["output_count"],
        "has_unsigned_tx": parsed.get("unsigned_tx") is not None,
        "global_types": _map_types(parsed["global"]),
        "input_types": [_map_types(m) for m in parsed["inputs"]],
        "output_types": [_map_types(m) for m in outputs],
        "output_map_lens": [len(m) for m in outputs],
        "first_output_map_empty": bool(outputs) and len(outputs[0]) == 0,
        "proprietary_count": len(parsed.get("proprietary") or []),
    }


def try_ur_roundtrip(raw: bytes) -> dict[str, Any] | None:
    """CBOR wrap/unwrap via SeedCash helpers/ur2. No decode_qr / hardware."""
    _ensure_seedcash_path()
    try:
        from seedcash.helpers.ur2.crypto_psbt import unwrap_psbt_cbor, wrap_psbt_cbor
    except Exception as e:
        return {"ok": False, "skipped": True, "error": f"{type(e).__name__}: {e}"}
    raw_b = bytes(raw)
    try:
        cbor = wrap_psbt_cbor(raw_b)
        unwrapped = unwrap_psbt_cbor(cbor)
        row: dict[str, Any] = {
            "ok": unwrapped == raw_b,
            "skipped": False,
            "cbor_is_raw_psbt": cbor[:5] == b"psbt\xff",
            "unwrapped_eq": unwrapped == raw_b,
        }
    except Exception as e:
        return {"ok": False, "skipped": False, "error": f"{type(e).__name__}: {e}"}
    try:
        from seedcash.helpers.ur2.ur import UR
        from seedcash.helpers.ur2.ur_decoder import URDecoder
        from seedcash.helpers.ur2.ur_encoder import UREncoder

        encoded = UREncoder.encode(UR("crypto-psbt", cbor))
        decoded = URDecoder.decode(encoded)
        row["ur_single_part"] = unwrap_psbt_cbor(decoded.cbor) == raw_b
        row["ur_type"] = decoded.type
    except Exception as e:
        row["ur_single_part"] = False
        row["ur_error"] = f"{type(e).__name__}: {e}"
    return row


def capture(raw: bytes) -> dict[str, Any]:
    """Full SeedCash-side capture: maps + model + UI route + review traps."""
    raw_b = bytes(raw)
    try:
        maps = parse_psbt_maps(raw_b)
        PSBTParser, _parse_psbt = _psbt_parser_mod()
        parser = PSBTParser(bytearray(raw_b))
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "signed_follows_unsigned_tx": SIGNED_FOLLOWS_UNSIGNED_TX,
        }

    model_ins: list[dict[str, Any]] = []
    for i, inp in enumerate(parser.tx.inputs):
        so = inp.spent_output
        model_ins.append(
            {
                "i": i,
                "prev_index": inp.prev_index,
                "sequence": inp.sequence,
                "sats": None if so is None else so.value_satoshis,
                "script_pubkey": None
                if so is None or not so.script_pubkey
                else so.script_pubkey.hex(),
                "token": None if so is None else _token_summary(so.token),
                "is_token_input": inp.is_token_input,
            }
        )
    model_outs: list[dict[str, Any]] = []
    for i, out in enumerate(parser.tx.outputs):
        spk = out.script_pubkey or b""
        model_outs.append(
            {
                "i": i,
                "sats": out.value_satoshis,
                "address": out.address,
                "script_pubkey": spk.hex(),
                "full_script": (out.full_script or b"").hex(),
                "token": _token_summary(out.token),
                "is_token_output": out.is_token_output,
                "is_op_return": spk.startswith(b"\x6a"),
                "op_return": spk.startswith(b"\x6a"),
            }
        )

    hybrids = hybrid_outputs(parser)
    shown = shown_address_amounts(parser)
    op_ret = parser.op_return_data
    dests = list(parser.destination_addresses)
    hybrid_ft_omitted = any(h["in_nft_bucket"] and not h["in_ft_bucket"] for h in hybrids)
    return {
        "ok": True,
        "maps": maps,
        "psbt_version": maps["psbt_version"],
        "map_output_types": maps["output_types"],
        "map_output_lens": maps["output_map_lens"],
        "first_output_map_empty": maps["first_output_map_empty"],
        "model": {
            "vin": parser.num_inputs,
            "vout": len(parser.tx.outputs),
            "input_sats": parser.input_amount,
            "output_sats": parser.output_amount,
            "fee": parser.fee_amount,
            "destination_addresses": dests,
            "num_destinations": parser.num_destinations,
            "op_return": None if op_ret is None else op_ret.hex(),
            "nft_categories": list(parser.nft_categories),
            "token_categories": list(parser.token_categories),
            "output_nft_categories": sorted(parser.outputs[0].keys()),
            "output_ft_categories": sorted(parser.outputs[1].keys()),
            "inputs": model_ins,
            "outputs": model_outs,
        },
        "vin": parser.num_inputs,
        "vout": len(parser.tx.outputs),
        "input_sats": parser.input_amount,
        "output_sats": parser.output_amount,
        "fee": parser.fee_amount,
        "dest_addrs": dests,
        "destination_addresses": dests,
        "op_return": None if op_ret is None else op_ret.hex(),
        "nft_categories": list(parser.nft_categories),
        "token_categories": list(parser.token_categories),
        "ft_categories": list(parser.token_categories),
        "ui_route": ui_route(parser),
        "shown_address_amounts": shown,
        "wysiwys_index_mismatch": any(not r["address_matches_output"] for r in shown),
        "outputs": model_outs,
        "nft_warnings": nft_warnings(parser),
        "hybrid_outputs": hybrids,
        "hybrid_output_indexes": [h["vout"] for h in hybrids],
        "hybrid_in_ft_bucket": any(h["in_ft_bucket"] for h in hybrids),
        "hybrid_ft_omitted": hybrid_ft_omitted,
        "token_ins": sum(1 for inp in parser.tx.inputs if inp.is_token_input),
        "token_outs": sum(1 for out in parser.tx.outputs if out.is_token_output),
        "nft_in": sum(len(v) for v in parser.inputs[0].values()),
        "nft_out": sum(len(v) for v in parser.outputs[0].values()),
        "nft_in_count": sum(len(v) for v in parser.inputs[0].values()),
        "nft_out_count": sum(len(v) for v in parser.outputs[0].values()),
        "signed_follows_unsigned_tx": SIGNED_FOLLOWS_UNSIGNED_TX,
        "ur": try_ur_roundtrip(raw_b),
    }
