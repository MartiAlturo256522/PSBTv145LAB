#!/usr/bin/env python3
"""Compare lab paytaca-145 bytes to REAL Paytaca Psbt.deserialize+serialize."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE = next((ROOT / "tools" / "node").glob("node-v*-win-x64/node.exe"))
RUNNER = ROOT / "tools" / "oracles" / "paytaca_psbt.mjs"

REPRESENTATIVE = [
    ("PSBT-02", "paytaca-145", "unsigned"),  # FT genesis
    ("GEN-01", "paytaca-145", "unsigned"),  # NFT immutable genesis
    ("GEN-02", "paytaca-145", "unsigned"),  # mutable genesis
    ("GEN-03", "paytaca-145", "unsigned"),  # minting genesis
    ("GEN-04", "paytaca-145", "unsigned"),  # FT genesis
    ("GEN-05", "paytaca-145", "unsigned"),  # hybrid
    ("GEN-08", "paytaca-145", "unsigned"),  # multi-category
    ("POST-01", "paytaca-145", "unsigned"),  # minting
    ("POST-08", "paytaca-145", "unsigned"),  # immutable transfer
    ("XGEN-01", "paytaca-145", "unsigned"),  # genesis + FT
    ("XGEN-06", "paytaca-145", "unsigned"),  # burn
    ("GEN-01", "paytaca-145", "signed"),
    ("VOUT0-NO-GENESIS", "paytaca-145", "unsigned"),
    ("VOUT0-MIXED", "paytaca-145", "unsigned"),
    ("SAMECAT-01", "paytaca-145", "unsigned"),
    ("BURN-MULTI", "paytaca-145", "unsigned"),
    ("MONSTER-01", "paytaca-145", "unsigned"),
    ("MONSTER-05", "paytaca-145", "unsigned"),
]


def paytaca_roundtrip(hex_in: str) -> dict:
    tmp = ROOT / "tools" / "oracles" / "_tmp.psbt.hex"
    tmp.write_text(hex_in, encoding="ascii")
    p = subprocess.run(
        [str(NODE), str(RUNNER), str(tmp)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=30,
    )
    if p.returncode != 0 or not p.stdout.strip():
        return {"ok": False, "error": (p.stderr or p.stdout)[-800:]}
    data = json.loads(p.stdout)
    if "hex" not in data:
        return {"ok": False, "error": json.dumps(data)[:400]}
    out_hex = data["hex"]
    return {
        "ok": True,
        "output_hex": out_hex,
        "output_len": len(bytes.fromhex(out_hex)),
        "encode_hex": data.get("encode_hex"),
        "encode_error": data.get("encode_error"),
    }


def first_diff(a: bytes, b: bytes) -> dict:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return {
                "offset": i,
                "lab": a[max(0, i - 4) : i + 16].hex(),
                "paytaca": b[max(0, i - 4) : i + 16].hex(),
            }
    if len(a) != len(b):
        return {"offset": n, "lab": "", "paytaca": "", "len_mismatch": True}
    return {}


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from ctlab.vectors.catalog import build_catalog
    from ctlab.vectors.generator import generate_vector

    catalog = {s["id"]: s for s in build_catalog()}
    rows = []
    for vid, dialect, sign in REPRESENTATIVE:
        sc = catalog[vid]
        v = generate_vector(sc, dialect=dialect, sign_state=sign)
        lab = v["psbt_hex"]
        r1 = paytaca_roundtrip(lab)
        row = {
            "id": f"{vid}-{dialect}-{sign}",
            "lab_len": len(bytes.fromhex(lab)) if lab else 0,
            "paytaca_ok": r1.get("ok"),
            "identity": False,
            "paytaca_stable": None,
        }
        if not r1.get("ok"):
            row["error"] = r1.get("error", "")[:400]
            rows.append(row)
            continue
        pay_hex = r1["output_hex"]
        row["paytaca_len"] = r1["output_len"]
        row["identity"] = lab.lower() == pay_hex.lower()
        row["diff"] = first_diff(bytes.fromhex(lab), bytes.fromhex(pay_hex))
        r2 = paytaca_roundtrip(pay_hex)
        if r2.get("ok"):
            row["paytaca_stable"] = pay_hex.lower() == r2["output_hex"].lower()
            row["stable_len"] = r2["output_len"]
        else:
            row["paytaca_stable"] = False
            row["stable_error"] = r2.get("error", "")[:200]
        rows.append(row)

    n = len(rows)
    ident = sum(1 for r in rows if r.get("identity"))
    stable = sum(1 for r in rows if r.get("paytaca_stable"))
    ok_run = sum(1 for r in rows if r.get("paytaca_ok"))
    summary = {
        "paytaca_js": "audits/paytaca/vendor/psbt.js @ 9c338d2ce07ee33cda2cec33bb340657c6fc1990",
        "vectors": n,
        "ran": ok_run,
        "lab_equals_paytaca_serialize": ident,
        "paytaca_self_roundtrip_stable": stable,
        "rows": rows,
    }
    out = ROOT / "audits" / "paytaca" / "real-js-diff.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    for r in rows:
        mark = "EQ" if r.get("identity") else "NE"
        print(
            f"  {mark} {r['id']} lab={r.get('lab_len')} pay={r.get('paytaca_len')} "
            f"stable={r.get('paytaca_stable')} diff={r.get('diff', {}).get('offset')}"
        )
    return 0 if ident == n and stable == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
