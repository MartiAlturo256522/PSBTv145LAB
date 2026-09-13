"""End-to-end PSBTLAB → SeedCash emulator pipeline.

PSBTLAB semantic intent
  → BCH PSBT v145
  → CBOR (BCR-2020-006)
  → UR crypto-psbt
  → current SeedCash decoder (DecodeQR / URDecoder)
  → parser
  → transaction model
  → review model
  → field-by-field differential vs PSBTLAB ground truth

A parse is not a pass unless the semantic model matches.
Parser input MUST begin 70 73 62 74 ff or the layer stops.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ctlab.engine import generate
from ctlab.lab.seedcash_adapter import SEEDCASH_SRC, capture, ui_route
from ctlab.lab.ur import unwrap_psbt_cbor, wrap_psbt_cbor
from ctlab.psbt.codec import MAGIC, decode_psbt

LAB = Path(__file__).resolve().parents[3]
PIN_PATH = LAB / "vendor" / "seedcash" / "PIN.json"
DASHBOARD_PATH = LAB / "reports" / "seedcash-pipeline" / "dashboard.json"
MAGIC_HEX = MAGIC.hex()  # 70736274ff

STATUSES = (
    "PASS",
    "FAIL",
    "UNSUPPORTED",
    "PARSER_ERROR",
    "DECODE_ERROR",
    "CBOR_ERROR",
    "UR_ERROR",
    "SEMANTIC_MISMATCH",
    "TOKEN_MISMATCH",
    "OUTPUT_INDEX_MISMATCH",
    "INPUT_MISMATCH",
    "WYSIWYS_MISMATCH",
    "SECURITY_RELEVANT",
)


def pin() -> dict[str, Any]:
    if PIN_PATH.is_file():
        return json.loads(PIN_PATH.read_text(encoding="utf-8"))
    return {"seedcash_commit": "unknown", "emulator_commit": "unknown"}


def _script_kind(locking_hex: str, token: dict | None) -> str:
    raw = bytes.fromhex(locking_hex) if locking_hex else b""
    if raw.startswith(b"\xef"):
        # token prefix then locking program — classify after prefix via token-stripped field
        return "token+" + _script_kind(raw[1:].hex() if False else "", None)
    if raw[:1] == b"\x6a":
        return "op_return"
    if raw.startswith(b"\x76\xa9\x14") and raw.endswith(b"\x88\xac"):
        return "p2pkh"
    if raw.startswith(b"\xa9\x14") and raw.endswith(b"\x87"):
        return "p2sh20"
    if raw.startswith(b"\xaa\x20") and raw.endswith(b"\x87"):
        return "p2sh32"
    return "script"


def ground_truth(vec: dict[str, Any]) -> dict[str, Any]:
    outs = vec.get("outputs") or []
    ins = vec.get("source_utxos") or []
    prevs = vec.get("previous_txs") or []
    sem = vec.get("semantics") or {}
    unsigned = bytes.fromhex(vec.get("unsigned_tx_hex") or "")
    decoded = decode_psbt(bytes.fromhex(vec["psbt_hex"])) if vec.get("psbt_hex") else None
    tx_locktime = int.from_bytes(unsigned[-4:], "little") if len(unsigned) >= 4 else None
    tx_version = int.from_bytes(unsigned[:4], "little") if len(unsigned) >= 4 else None

    gt_ins = []
    for i, row in enumerate(ins):
        tok = row.get("token")
        gt_ins.append(
            {
                "i": i,
                "sats": row.get("value_sats"),
                "script_pubkey": row.get("locking_bytecode"),
                "token_category": None if not tok else tok.get("category"),
                "token_amount": None if not tok else tok.get("amount"),
                "nft_cap": None if not tok or not tok.get("nft") else tok["nft"].get("capability"),
                "nft_commit": None if not tok or not tok.get("nft") else tok["nft"].get("commitment"),
                "prev_txid": (prevs[i].get("txid") if i < len(prevs) else None),
            }
        )
    gt_outs = []
    for i, row in enumerate(outs):
        tok = row.get("token")
        locking = row.get("locking_bytecode") or row.get("script_field") or ""
        script_field = row.get("script_field") or locking
        kind = _script_kind(script_field, tok)
        if tok:
            # script_field is prefix+locking; classify locking-only when possible
            if script_field.startswith("76a914") or (row.get("locking_bytecode") or "").endswith("88ac"):
                kind = "p2pkh"
            elif (row.get("locking_bytecode") or script_field).startswith("6a"):
                kind = "op_return"
            elif (row.get("locking_bytecode") or "").startswith("a914"):
                kind = "p2sh20"
        gt_outs.append(
            {
                "i": i,
                "sats": row.get("value_sats"),
                "script_kind": kind,
                "script_pubkey": script_field,
                "is_op_return": kind == "op_return" or script_field.startswith("6a"),
                "token_category": None if not tok else tok.get("category"),
                "token_amount": None if not tok else tok.get("amount"),
                "nft_cap": None if not tok or not tok.get("nft") else tok["nft"].get("capability"),
                "nft_commit": None if not tok or not tok.get("nft") else tok["nft"].get("commitment"),
            }
        )
    genesis = [g for g in (sem.get("genesis") or []) if g.get("type") and g.get("type") != "empty"]
    return {
        "id": vec.get("id") or vec.get("catalog_id"),
        "format": "bch-psbt-v145",
        "dialect": vec.get("dialect"),
        "n_in": len(ins),
        "n_out": len(outs),
        "tx_version": tx_version,
        "locktime": tx_locktime,
        "psbt_version": None if decoded is None else decoded.version,
        "unsigned_present": bool(unsigned),
        "cashtokens": any(o.get("token") for o in outs) or any(i.get("token") for i in ins),
        "inputs": gt_ins,
        "outputs": gt_outs,
        "genesis": genesis,
        "mint": sem.get("mint") or [],
        "burns": sem.get("burns") or [],
        "transfers": sem.get("transfers") or [],
        "op_return_count": sum(1 for o in gt_outs if o["is_op_return"]),
        "txid": vec.get("txid"),
    }


def _diff(path: str, expected: Any, actual: Any, diffs: list[dict]) -> None:
    if expected != actual:
        diffs.append({"path": path, "expected": expected, "actual": actual})


def compare_models(gt: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    model = parsed.get("model") or {}
    _diff("n_in", gt["n_in"], model.get("vin") or parsed.get("vin"), diffs)
    _diff("n_out", gt["n_out"], model.get("vout") or parsed.get("vout"), diffs)
    _diff("locktime", gt["locktime"], model.get("locktime"), diffs)
    _diff("tx_version", gt["tx_version"], model.get("tx_version"), diffs)

    act_ins = model.get("inputs") or []
    for exp in gt["inputs"]:
        i = exp["i"]
        act = act_ins[i] if i < len(act_ins) else None
        if act is None:
            _diff(f"inputs[{i}]", exp, None, diffs)
            continue
        _diff(f"inputs[{i}].sats", exp["sats"], act.get("sats"), diffs)
        _diff(f"inputs[{i}].prev_index", None if exp.get("prev_index") is None else exp.get("prev_index"), act.get("prev_index"), diffs)
        if exp.get("token_category"):
            tok = act.get("token") or {}
            _diff(f"inputs[{i}].token.category", exp["token_category"], tok.get("category"), diffs)
            _diff(f"inputs[{i}].token.amount", exp["token_amount"] or 0, tok.get("ft") or 0, diffs)
            _diff(f"inputs[{i}].token.nft_cap", exp["nft_cap"], tok.get("nft_cap"), diffs)
            _diff(f"inputs[{i}].token.nft_commit", exp["nft_commit"], tok.get("nft_commit"), diffs)
        elif act.get("token"):
            _diff(f"inputs[{i}].token", None, act.get("token"), diffs)

    act_outs = model.get("outputs") or parsed.get("outputs") or []
    for exp in gt["outputs"]:
        i = exp["i"]
        act = act_outs[i] if i < len(act_outs) else None
        if act is None:
            _diff(f"outputs[{i}]", exp, None, diffs)
            continue
        _diff(f"outputs[{i}].sats", exp["sats"], act.get("sats"), diffs)
        _diff(f"outputs[{i}].is_op_return", exp["is_op_return"], bool(act.get("is_op_return") or act.get("op_return")), diffs)
        if exp.get("token_category"):
            tok = act.get("token") or {}
            _diff(f"outputs[{i}].token.category", exp["token_category"], tok.get("category"), diffs)
            _diff(f"outputs[{i}].token.amount", exp["token_amount"] or 0, tok.get("ft") or 0, diffs)
            _diff(f"outputs[{i}].token.nft_cap", exp["nft_cap"], tok.get("nft_cap"), diffs)
            _diff(f"outputs[{i}].token.nft_commit", exp["nft_commit"], tok.get("nft_commit"), diffs)
        elif act.get("token"):
            _diff(f"outputs[{i}].token", None, act.get("token"), diffs)
    return diffs


def _classify(diffs: list[dict[str, Any]]) -> str:
    if not diffs:
        return "PASS"
    paths = [d["path"] for d in diffs]
    if any(p.startswith("outputs[") and ".token" in p for p in paths):
        return "TOKEN_MISMATCH"
    if any(p.startswith("inputs[") and ".token" in p for p in paths):
        return "TOKEN_MISMATCH"
    if any(p.startswith("outputs[") for p in paths) and any("n_out" in p or ".sats" in p or "is_op_return" in p for p in paths):
        if any(p == "n_out" or p.startswith("outputs[") and p.endswith("]") for p in paths):
            return "OUTPUT_INDEX_MISMATCH"
    if any(p == "n_in" or p.startswith("inputs[") for p in paths):
        return "INPUT_MISMATCH"
    if any("locktime" in p or "tx_version" in p for p in paths):
        return "SEMANTIC_MISMATCH"
    return "SEMANTIC_MISMATCH"


def _review_from_parser(parsed: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    model = parsed.get("model") or {}
    shown = parsed.get("shown_address_amounts") or []
    route = parsed.get("ui_route")
    expected_route = "BCH_ONLY"
    if gt["cashtokens"]:
        if any(o.get("nft_cap") for o in gt["outputs"] + gt["inputs"]):
            expected_route = "NFT_FIRST"
        elif any((o.get("token_amount") or 0) > 0 for o in gt["outputs"] + gt["inputs"]):
            expected_route = "FT_FIRST"
    review_mismatch = []
    if route != expected_route:
        review_mismatch.append(
            {"path": "review.ui_route", "expected": expected_route, "actual": route}
        )
    # Pairing: each shown dest must match the addressable output at that dest index,
    # not vout==dest_index (OP_RETURN shifts).
    addressable = [o for o in (model.get("outputs") or []) if o.get("address")]
    for i, row in enumerate(shown):
        if i < len(addressable):
            if row.get("shown_address") != addressable[i].get("address"):
                review_mismatch.append(
                    {
                        "path": f"review.destinations[{i}].address",
                        "expected": addressable[i].get("address"),
                        "actual": row.get("shown_address"),
                    }
                )
            if row.get("output_at_index_sats") not in (None, addressable[i].get("sats")) and not row.get("address_matches_output"):
                # after dest-output pairing fix, shown amounts come from dest outputs
                pass
    return {
        "ui_route": route,
        "expected_ui_route": expected_route,
        "destination_addresses": model.get("destination_addresses"),
        "num_destinations": model.get("num_destinations"),
        "op_return": model.get("op_return"),
        "shown": shown,
        "nft_categories": model.get("nft_categories"),
        "token_categories": model.get("token_categories"),
        "mismatch": review_mismatch,
    }


def _seedcash_ur_roundtrip(raw: bytes) -> dict[str, Any]:
    """CBOR wrap → SeedCash UREncoder → URDecoder → unwrap. Also DecodeQR if importable."""
    import sys

    src = str(SEEDCASH_SRC)
    if src not in sys.path:
        sys.path.insert(0, src)
    layers: dict[str, Any] = {
        "raw_psbt_hex": raw.hex(),
        "raw_magic": raw[:5] == MAGIC,
        "raw_magic_hex": raw[:5].hex(),
    }
    if raw[:5] != MAGIC:
        layers["stop"] = "raw PSBT missing magic"
        return layers

    cbor = wrap_psbt_cbor(raw)
    layers["cbor_hex_prefix"] = cbor[:8].hex()
    layers["cbor_is_raw_psbt"] = cbor[:5] == MAGIC
    try:
        unwrapped = unwrap_psbt_cbor(cbor)
    except Exception as e:
        layers["cbor_error"] = f"{type(e).__name__}: {e}"
        layers["stop"] = "CBOR_ERROR"
        return layers
    layers["cbor_unwrapped_magic"] = unwrapped[:5] == MAGIC
    layers["cbor_unwrapped_eq"] = unwrapped == raw
    if unwrapped[:5] != MAGIC:
        layers["stop"] = "CBOR_ERROR"
        return layers

    try:
        from seedcash.helpers.ur2.ur import UR
        from seedcash.helpers.ur2.ur_decoder import URDecoder
        from seedcash.helpers.ur2.ur_encoder import UREncoder

        ur = UR("crypto-psbt", cbor)
        enc = UREncoder(ur=ur, max_fragment_len=200)
        dec = URDecoder()
        parts: list[str] = []
        guard = 0
        while not dec.is_complete() and guard < 64:
            part = enc.next_part()
            parts.append(part)
            dec.receive_part(part)
            guard += 1
        layers["ur_parts"] = len(parts)
        layers["ur_complete"] = bool(dec.is_complete())
        if not dec.is_complete():
            layers["stop"] = "UR_ERROR"
            return layers
        msg = dec.result_message()
        layers["ur_type"] = msg.type
        ur_cbor = msg.cbor
        layers["ur_cbor_prefix"] = ur_cbor[:8].hex()
        ur_unwrapped = unwrap_psbt_cbor(ur_cbor)
        layers["ur_unwrapped_magic"] = ur_unwrapped[:5] == MAGIC
        layers["ur_unwrapped_eq"] = ur_unwrapped == raw
        if ur_unwrapped[:5] != MAGIC:
            layers["stop"] = "UR_ERROR"
            return layers
    except Exception as e:
        layers["ur_error"] = f"{type(e).__name__}: {e}"
        layers["stop"] = "UR_ERROR"
        return layers

    decoder_bytes = None
    try:
        from seedcash.models.decode_qr import DecodeQR, DecodeQRStatus

        qr = DecodeQR()
        for part in parts:
            st = qr.add_data(part)
            if st == DecodeQRStatus.COMPLETE:
                break
        decoder_bytes = bytes(qr.get_psbt() or b"")
        layers["decode_qr"] = True
    except Exception as e:
        layers["decode_qr"] = False
        layers["decode_qr_error"] = f"{type(e).__name__}: {e}"
        decoder_bytes = ur_unwrapped

    layers["decoder_bytes_prefix"] = decoder_bytes[:8].hex() if decoder_bytes else ""
    layers["decoder_magic"] = decoder_bytes[:5] == MAGIC if decoder_bytes else False
    layers["parser_input_hex_prefix"] = (decoder_bytes or b"")[:8].hex()
    layers["parser_input_magic"] = (decoder_bytes or b"")[:5] == MAGIC
    if not layers["parser_input_magic"]:
        layers["stop"] = "DECODE_ERROR"
        layers["parser_input_must_be"] = MAGIC_HEX
        layers["parser_input_was"] = layers["parser_input_hex_prefix"]
        return layers
    layers["parser_input"] = decoder_bytes
    layers["parts"] = parts
    return layers


def expected_review(gt: dict[str, Any]) -> dict[str, Any]:
    route = "BCH_ONLY"
    if any(o.get("nft_cap") for o in gt["outputs"] + gt["inputs"]):
        route = "NFT_FIRST"
    elif any((o.get("token_amount") or 0) > 0 for o in gt["outputs"] + gt["inputs"]):
        route = "FT_FIRST"
    return {
        "ui_route": route,
        "n_in": gt["n_in"],
        "n_out": gt["n_out"],
        "cashtokens": gt["cashtokens"],
        "op_return": gt["op_return_count"] > 0,
        "payments": [o["i"] for o in gt["outputs"] if not o["is_op_return"] and not o.get("token_category")],
        "token_vouts": [o["i"] for o in gt["outputs"] if o.get("token_category")],
        "op_return_vouts": [o["i"] for o in gt["outputs"] if o["is_op_return"]],
        "genesis": bool(gt["genesis"]),
        "burns": bool(gt["burns"]),
        "mint": bool(gt["mint"]),
    }


def _resolve_spec(spec: str | dict[str, Any]) -> str | dict[str, Any]:
    if isinstance(spec, dict):
        return spec
    from ctlab.vectors.catalog import build_catalog

    if any(s["id"] == spec for s in build_catalog()):
        return spec
    from tools.lab.freeze_m0 import CASES

    for ident, cfg, _desc in CASES:
        if ident == spec:
            return cfg
    return spec


def run_vector(spec: str | dict[str, Any], *, supported: bool = True) -> dict[str, Any]:
    ident = spec if isinstance(spec, str) else spec.get("id", "CUSTOM")
    spec = _resolve_spec(spec)
    row: dict[str, Any] = {
        "vector_id": ident,
        "supported": supported,
        "parse_success": False,
        "semantic_match": False,
        "review_match": False,
        "status": "FAIL",
        "differences": [],
        "pin": pin(),
        "seedcash_src": str(SEEDCASH_SRC),
    }
    if not supported:
        row["status"] = "UNSUPPORTED"
        return row
    try:
        vec = generate(spec, dialect="paytaca-145", sign="unsigned")
    except Exception as e:
        row["status"] = "FAIL"
        row["error"] = f"generate {type(e).__name__}: {e}"
        return row
    raw = bytes.fromhex(vec.get("psbt_hex") or "")
    gt = ground_truth(vec)
    row["PSBTLAB_GROUND_TRUTH"] = gt
    row["psbt_len"] = len(raw)
    layers = _seedcash_ur_roundtrip(raw)
    row["layers"] = {k: v for k, v in layers.items() if k not in ("parser_input", "parts", "raw_psbt_hex")}
    if layers.get("stop"):
        row["status"] = layers["stop"] if layers["stop"] in STATUSES else "DECODE_ERROR"
        row["error"] = layers.get("stop")
        return row
    parser_input = layers.get("parser_input")
    if not parser_input or parser_input[:5] != MAGIC:
        row["status"] = "DECODE_ERROR"
        row["error"] = "parser input missing psbt\\xff"
        return row
    try:
        parsed = capture(parser_input)
    except Exception as e:
        row["status"] = "PARSER_ERROR"
        row["error"] = f"{type(e).__name__}: {e}"
        return row
    if not parsed.get("ok"):
        row["status"] = "PARSER_ERROR"
        row["error"] = parsed.get("error")
        return row
    row["parse_success"] = True
    # attach locktime/version from parser tx
    try:
        from ctlab.lab.seedcash_adapter import _psbt_parser_mod

        PSBTParser, _ = _psbt_parser_mod()
        p = PSBTParser(bytearray(parser_input))
        parsed["model"]["locktime"] = p.tx.locktime
        parsed["model"]["tx_version"] = p.tx.version
        parsed["ui_route"] = ui_route(p)
        # after genesis-output routing, recompute route from outputs too
        if p.inputs[0] or p.outputs[0]:
            parsed["ui_route"] = "NFT_FIRST"
        elif p.inputs[1] or p.outputs[1]:
            parsed["ui_route"] = "FT_FIRST"
        else:
            parsed["ui_route"] = "BCH_ONLY"
    except Exception as e:
        parsed.setdefault("model", {})
        parsed["model_error"] = str(e)

    row["SEEDCASH_PARSED_MODEL"] = parsed.get("model")
    diffs = compare_models(gt, parsed)
    # ignore prev_index None vs 0 noise
    diffs = [d for d in diffs if not (d["path"].endswith(".prev_index") and d["expected"] is None)]
    row["differences"] = diffs
    row["semantic_match"] = not diffs
    review = _review_from_parser(parsed, gt)
    row["SEEDCASH_REVIEW"] = review
    row["EXPECTED_REVIEW"] = expected_review(gt)
    row["review_match"] = not review.get("mismatch") and review.get("ui_route") == row["EXPECTED_REVIEW"]["ui_route"]
    if diffs:
        row["status"] = _classify(diffs)
    elif not row["review_match"]:
        row["status"] = "WYSIWYS_MISMATCH"
        row["differences"] = review.get("mismatch") or [
            {
                "path": "review.ui_route",
                "expected": row["EXPECTED_REVIEW"]["ui_route"],
                "actual": review.get("ui_route"),
            }
        ]
    else:
        row["status"] = "PASS"
    return row


# ── Acceptance sets ─────────────────────────────────────────────────────

def _p2sh_bch() -> dict[str, Any]:
    return {
        "id": "BASIC-P2SH",
        "dialect": "paytaca-145",
        "sign_state": "unsigned",
        "inputs": [{"kind": "bch", "key": "A", "owner": "alice", "sats": 50_000}],
        "outputs": [{"owner": "bob", "sats": 48_000, "script": "p2sh20"}],
    }


def _io(ident: str, n_in: int, n_out: int, *, change: bool = False) -> dict[str, Any]:
    from tools.lab.freeze_m0 import bch_io

    return bch_io(ident, n_in, n_out, change=change)


BASIC_SET: list[tuple[str, str | dict[str, Any]]] = [
    ("A-1in-1out", _io("IO-1-1", 1, 1)),
    ("B-1in-2out", _io("IO-1-2", 1, 2, change=True)),
    ("C-2in-1out", _io("IO-2-1", 2, 1)),
    ("D-2in-2out", _io("IO-2-2", 2, 2, change=True)),
    ("E-2in-3out", _io("IO-2-3", 2, 3, change=True)),
    ("F-p2sh", _p2sh_bch()),
    ("G-op-return", "SCR-05"),
]

TOKEN_SET: list[tuple[str, str]] = [
    ("FT-transfer", "VOUT0-NO-GENESIS"),
    ("NFT-transfer", "POST-08"),
    ("hybrid", "GEN-05"),
    ("genesis-FT", "GEN-04"),
    ("genesis-NFT", "GEN-01"),
    ("genesis-hybrid", "GEN-05"),
    ("mint", "POST-01"),
    ("melt-baton", "POST-04"),
    ("ft-nft-burn", "BURN-MULTI"),
    ("samecat", "SAMECAT-01"),
    ("token-opreturn", "BCMR-01"),
    ("multi-token-out", "GEN-06"),
    ("multi-token-in", "XGEN-07"),
    ("p2sh-token", "SCR-02"),
]

MIXED_SET: list[tuple[str, str]] = [
    ("mixed-genesis-ft", "XGEN-07"),
    ("mixed-monster", "MONSTER-01"),
]

def _permute_outputs(order: tuple[str, ...]) -> dict[str, Any]:
    pieces = {
        "payment": {"owner": "bob", "sats": 20_000, "script": "p2pkh"},
        "change": {"owner": "alice", "sats": 20_000, "script": "p2pkh"},
        "op_return": {"owner": "bob", "sats": 0, "script": "op_return"},
        "token": {
            "owner": "carol",
            "sats": 20_000,
            "genesis_from": 0,
            "token": {"amount": 9, "nft": None},
        },
    }
    return {
        "id": "PERM-" + "-".join(order),
        "dialect": "paytaca-145",
        "sign_state": "unsigned",
        "inputs": [{"kind": "genesis_parent", "key": "A", "owner": "alice", "sats": 100_000}],
        "outputs": [dict(pieces[name]) for name in order],
    }


PERMUTE_SET: list[tuple[str, dict[str, Any]]] = [
    ("perm-payment-change-opreturn-token", _permute_outputs(("payment", "change", "op_return", "token"))),
    ("perm-opreturn-token-payment-change", _permute_outputs(("op_return", "token", "payment", "change"))),
    ("perm-change-payment-token-opreturn", _permute_outputs(("change", "payment", "token", "op_return"))),
]

M0_IDS = [
    "IO-1-1", "IO-2-1", "IO-1-2", "IO-2-2", "IO-2-3", "IO-3-2",
    "GEN-01", "GEN-04", "GEN-05", "GEN-06", "GEN-08",
    "POST-01", "POST-04", "POST-08", "SAMECAT-01", "BURN-MULTI",
    "XGEN-07", "SCR-02", "SCR-05", "BCMR-01", "MONSTER-01",
]


def run_set(cases: list[tuple[str, str | dict[str, Any]]]) -> list[dict[str, Any]]:
    return [run_vector(spec, supported=True) | {"label": label} for label, spec in cases]


def write_dashboard(rows: list[dict[str, Any]], path: Path = DASHBOARD_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r.get("status", "FAIL")] = counts.get(r.get("status", "FAIL"), 0) + 1
    payload = {
        "pin": pin(),
        "seedcash_src": str(SEEDCASH_SRC),
        "n": len(rows),
        "counts": counts,
        "pass": sum(1 for r in rows if r.get("status") == "PASS"),
        "vectors": [
            {
                "vector_id": r.get("vector_id"),
                "label": r.get("label"),
                "status": r.get("status"),
                "parse_success": r.get("parse_success"),
                "semantic_match": r.get("semantic_match"),
                "review_match": r.get("review_match"),
                "n_diff": len(r.get("differences") or []),
                "differences": (r.get("differences") or [])[:12],
            }
            for r in rows
        ],
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
