"""Probe official SeedCashOrg/seedcash PSBTParser (not Desktop/seed-cash)."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

LAB = Path(r"C:\Users\reque\Desktop\PSBTLAB")
SC = Path(r"C:\Users\reque\Desktop\SeedCashOrg\seedcash\src")
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(SC))

from ctlab.engine import generate  # noqa: E402
from seedcash.models.psbt_parser import PSBTParser  # noqa: E402

CASES = [
    ("GEN-01", "bip174-v0", "unsigned"),
    ("GEN-04", "paytaca-145", "unsigned"),
    ("PSBT-02", "paytaca-145", "unsigned"),
    ("VOUT0-NO-GENESIS", "bip174-v0", "unsigned"),
    ("MONSTER-01", "paytaca-145", "unsigned"),
]


def summarize(ident, dialect, sign):
    vec = generate(ident, dialect=dialect, sign=sign)
    raw = bytes.fromhex(vec["psbt_hex"])
    r = {
        "id": ident,
        "dialect": dialect,
        "bytes": len(raw),
        "lab_genesis": (vec.get("semantics") or {}).get("genesis_categories"),
        "ok": False,
    }
    try:
        p = PSBTParser(bytearray(raw))
        outs = []
        for i, o in enumerate(p.tx.outputs):
            tok = None
            if o.token:
                tok = {
                    "category": o.token.category_id,
                    "ft": o.token.ft_amount,
                    "nft": None
                    if not o.token.nft_data
                    else {
                        "capability": o.token.nft_data.capability,
                        "commitment": o.token.nft_data.commitment,
                    },
                }
            outs.append(
                {
                    "sats": o.value_satoshis,
                    "address": o.address,
                    "token": tok,
                }
            )
        r.update(
            {
                "ok": True,
                "psbt_version": p.parsed.get("psbt_version"),
                "num_inputs": p.num_inputs,
                "input_sats": p.input_amount,
                "output_sats": p.output_amount,
                "fee": p.fee_amount,
                "ft_categories": p.token_categories,
                "nft_categories": p.nft_categories,
                "destinations": p.destination_addresses,
                "outputs": outs,
            }
        )
    except Exception as e:
        r["error"] = f"{type(e).__name__}: {e}"
        r["traceback"] = traceback.format_exc()[-2000:]
    return r


def main():
    reports = [summarize(*c) for c in CASES]
    dest = LAB / "desktop" / "examples" / "seedcash_org_probe.json"
    dest.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    for r in reports:
        print("=" * 64)
        print(f"{r['id']} {r['dialect']} {r['bytes']}B")
        if not r["ok"]:
            print(" FAIL", r.get("error"))
            continue
        print(f"  ver={r['psbt_version']} ins={r['num_inputs']} in={r['input_sats']} out={r['output_sats']} fee={r['fee']}")
        print(f"  ft_cats={r['ft_categories']}")
        print(f"  nft_cats={r['nft_categories']}")
        print(f"  dest={r['destinations']}")
        for i, o in enumerate(r["outputs"]):
            print(f"  vout{i}: {o['sats']} {o['address']} token={o['token']}")
    print("wrote", dest)


if __name__ == "__main__":
    main()
