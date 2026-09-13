"""Freeze the audited 21 Paytaca PSBT v145 vectors as golden regression fixtures.

Dialect is paytaca-145 (hybrid v2 + CashTokens + extra input-map 0x00).
Not BIP-174 v0. GLOBAL_VERSION is 145.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ctlab.engine import generate  # noqa: E402
from ctlab.lab.maps import walk_paytaca_v145  # noqa: E402
from ctlab.psbt.codec import PSBT_GLOBAL_VERSION, decode_psbt  # noqa: E402

FROZEN_DIR = ROOT / "vectors" / "regression" / "seedcash-v145-m0"
DIALECT = "paytaca-145"
SIGN = "unsigned"

# Live Paytaca JS deserialize+serialize byte-eq from audits/seedcash-v145 (5/5).
LIVE_PAYTACA_BYTE_EQ = frozenset(
    {"GEN-04", "IO-2-3", "SCR-05", "POST-01", "MONSTER-01"}
)


def bch_io(ident: str, n_in: int, n_out: int, *, change: bool = False) -> dict[str, Any]:
    """Same engine configs as audits/seedcash-v145/run_audit.py."""
    inputs = [
        {"kind": "bch", "key": chr(ord("A") + i), "owner": "alice", "sats": 50_000}
        for i in range(n_in)
    ]
    outputs: list[dict[str, Any]] = []
    owners = ["bob", "carol", "dave", "alice"]
    remaining = 50_000 * n_in - 2000
    for i in range(n_out):
        owner = "alice" if (change and i == n_out - 1) else owners[i % 3]
        sat = remaining // (n_out - i) if i < n_out - 1 else remaining
        remaining -= sat
        outputs.append({"owner": owner, "sats": max(sat, 546)})
    return {
        "id": ident,
        "dialect": DIALECT,
        "sign_state": SIGN,
        "inputs": inputs,
        "outputs": outputs,
    }


CASES: list[tuple[str, str | dict[str, Any], str]] = [
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


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_m0(spec: str | dict[str, Any]) -> dict[str, Any]:
    return generate(spec, dialect=DIALECT, sign=SIGN)


def _expected_review(vec: dict[str, Any], spec: str | dict[str, Any]) -> dict[str, Any]:
    outs = vec.get("outputs") or []
    ins = vec.get("source_utxos") or []
    sem = vec.get("semantics") or {}
    token_ins = sum(1 for i in ins if i.get("token"))
    token_outs: list[int] = []
    op_return: list[int] = []
    payments: list[int] = []
    change: list[int] = []
    roles: list[str] = []
    hybrid = False
    genesis = bool(sem.get("genesis") or sem.get("genesis_categories"))
    io_change = isinstance(spec, dict) and spec.get("id", "").startswith("IO-") and len(outs) > 1

    for i, o in enumerate(outs):
        tok = o.get("token")
        script = o.get("locking_bytecode") or ""
        is_opret = script.startswith("6a")
        if is_opret:
            op_return.append(i)
            roles.append("op_return")
        elif tok:
            token_outs.append(i)
            if tok.get("amount") and tok.get("nft"):
                hybrid = True
            roles.append("genesis" if genesis and token_ins == 0 else "token_transfer")
        elif io_change and i == len(outs) - 1:
            change.append(i)
            roles.append("change")
        else:
            payments.append(i)
            roles.append("payment")

    if genesis and token_ins == 0:
        ui_route = "TOKEN_GENESIS"
    elif any((o.get("token") or {}).get("nft") for o in outs) or any(
        (i.get("token") or {}).get("nft") for i in ins
    ):
        ui_route = "NFT_FIRST"
    elif any((o.get("token") or {}).get("amount") for o in outs) or any(
        (i.get("token") or {}).get("amount") for i in ins
    ):
        ui_route = "FT_FIRST"
    else:
        ui_route = "BCH_ONLY"

    return {
        "ui_route": ui_route,
        "n_in": len(ins),
        "n_out": len(outs),
        "roles": roles,
        "payments": payments,
        "change": change,
        "op_return": op_return,
        "token_outputs": token_outs,
        "genesis": genesis,
        "hybrid": hybrid,
        "sighash": vec.get("sighash", "ALL|FORKID"),
    }


def freeze_one(ident: str, spec: str | dict[str, Any], description: str) -> dict[str, Any]:
    vec = generate_m0(spec)
    raw = bytes.fromhex(vec["psbt_hex"])
    unsigned = bytes.fromhex(vec["unsigned_tx_hex"])
    decoded = decode_psbt(raw)
    walked = walk_paytaca_v145(raw)
    if decoded.version != 145 or walked["version"] != 145:
        raise RuntimeError(f"{ident}: GLOBAL_VERSION is {decoded.version}, not 145")
    if decoded.dialect != DIALECT:
        raise RuntimeError(f"{ident}: dialect={decoded.dialect}, expected {DIALECT}")
    if not walked["extra_input_sep"]:
        raise RuntimeError(f"{ident}: missing Paytaca extra input separator")
    v145 = (145).to_bytes(4, "little")
    if not any(k[:1] == bytes([PSBT_GLOBAL_VERSION]) and v == v145 for k, v in decoded.global_pairs):
        raise RuntimeError(f"{ident}: missing PSBT_GLOBAL_VERSION 145")

    n_in = walked["n_in"]
    n_out = walked["n_out"]
    row = {
        "id": ident,
        "catalog_or_config": spec if isinstance(spec, str) else spec,
        "n_in": n_in,
        "n_out": n_out,
        "psbt_sha256": sha256_hex(raw),
        "unsigned_tx_sha256": sha256_hex(unsigned),
        "psbt_len": len(raw),
        "live_paytaca_byte_eq": ident in LIVE_PAYTACA_BYTE_EQ,
        "description": description,
    }
    meta = {
        "id": ident,
        "txid": vec.get("txid"),
        "dialect": DIALECT,
        "sign_state": SIGN,
        "n_in": n_in,
        "n_out": n_out,
        "semantics": vec.get("semantics"),
        "expected_review": _expected_review(vec, spec),
    }
    return {"row": row, "psbt_hex": vec["psbt_hex"], "meta": meta}


def freeze(out_dir: Path | None = None) -> dict[str, Any]:
    dest = out_dir or FROZEN_DIR
    dest.mkdir(parents=True, exist_ok=True)
    vectors = []
    for ident, spec, description in CASES:
        frozen = freeze_one(ident, spec, description)
        (dest / f"{ident}.psbt.hex").write_text(frozen["psbt_hex"] + "\n", encoding="ascii")
        (dest / f"{ident}.meta.json").write_text(
            json.dumps(frozen["meta"], indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        vectors.append(frozen["row"])
        print(f"{ident:16} sha256={frozen['row']['psbt_sha256'][:16]} len={frozen['row']['psbt_len']}")
    index = {
        "dialect": DIALECT,
        "sign_state": SIGN,
        "n": len(vectors),
        "vectors": vectors,
    }
    (dest / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index


def main() -> int:
    freeze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
