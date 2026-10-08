from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def export_corpus(vectors: list[dict[str, Any]], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    valid = root / "valid"
    invalid = root / "invalid"
    seed = root / "seed_signer"
    valid.mkdir(exist_ok=True)
    invalid.mkdir(exist_ok=True)
    seed.mkdir(exist_ok=True)
    (root / "complex").mkdir(exist_ok=True)

    slim = []
    for v in vectors:
        dest = invalid if v.get("expected_consensus") == "invalid" or v.get("expected_psbt") == "invalid" else valid
        if v.get("group") in ("complex", "monster", "defi"):
            dest = root / "complex"
        ident = v.get("id", "unknown")
        for other in (valid, invalid, root / "complex"):
            if other.resolve() != dest.resolve():
                stale = other / ident
                if stale.exists():
                    shutil.rmtree(stale)
        pack = dest / ident
        pack.mkdir(exist_ok=True)
        (pack / "vector.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
        if v.get("unsigned_tx_hex"):
            (pack / "unsigned_tx.hex").write_text(v["unsigned_tx_hex"] + "\n", encoding="utf-8")
        if v.get("psbt_base64"):
            (pack / "psbt.base64").write_text(v["psbt_base64"] + "\n", encoding="utf-8")
        if v.get("psbt_hex"):
            raw = bytes.fromhex(v["psbt_hex"])
            (pack / "psbt.binary").write_bytes(raw)
        prev = pack / "previous"
        prev.mkdir(exist_ok=True)
        for p in v.get("previous_txs") or []:
            if p.get("hex"):
                (prev / f"tx{p['index']}.hex").write_text(p["hex"] + "\n", encoding="utf-8")
        sem = v.get("semantics") or {}
        expected = {
            "consensus": v.get("expected_consensus"),
            "psbt": v.get("expected_psbt"),
            "txid": v.get("txid"),
            "genesis_categories": sem.get("genesis_categories"),
            "genesis": sem.get("genesis"),
            "mint": sem.get("mint"),
            "burns": sem.get("burns"),
            "mutations": sem.get("mutations"),
            "transfers": sem.get("transfers"),
            "semantics": sem,
            "invalid_code": v.get("invalid_code"),
        }
        (pack / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
        decoded = {
            "txid": v.get("txid"),
            "dialect": v.get("dialect"),
            "source_utxos": v.get("source_utxos"),
            "outputs": v.get("outputs"),
            "sighash_info": v.get("sighash_info"),
        }
        (pack / "decoded.json").write_text(json.dumps(decoded, indent=2), encoding="utf-8")

        # SeedSigner/SeedCash drop: BIP-174 v0 unsigned PSBT + prev txs
        if v.get("dialect") == "bip174-v0" and v.get("psbt_base64"):
            sdir = seed / ident
            sdir.mkdir(exist_ok=True)
            (sdir / "psbt.base64").write_text(v["psbt_base64"] + "\n", encoding="utf-8")
            if v.get("psbt_hex"):
                (sdir / "psbt.binary").write_bytes(bytes.fromhex(v["psbt_hex"]))
            (sdir / "expected.json").write_text(
                json.dumps(
                    {
                        "id": ident,
                        "semantics": v.get("semantics"),
                        "seedcash_expected": v.get("seedcash_expected"),
                        "txid": v.get("txid"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        slim.append(
            {
                "id": ident,
                "catalog_id": v.get("catalog_id"),
                "group": v.get("group"),
                "title": v.get("title"),
                "dialect": v.get("dialect"),
                "sign_state": v.get("sign_state"),
                "expected_consensus": v.get("expected_consensus"),
                "actual_consensus": v.get("actual_consensus"),
                "expected_psbt": v.get("expected_psbt"),
                "actual_psbt": v.get("actual_psbt"),
                "consensus_match": v.get("consensus_match"),
                "psbt_match": v.get("psbt_match"),
                "txid": v.get("txid"),
                "error": v.get("error"),
            }
        )

    (root / "all.json").write_text(json.dumps(vectors, indent=2), encoding="utf-8")
    (root / "index.json").write_text(json.dumps(slim, indent=2), encoding="utf-8")
