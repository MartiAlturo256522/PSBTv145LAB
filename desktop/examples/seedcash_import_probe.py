"""Feed lab PSBTs into SeedCash PSBTParser. Does not modify either engine."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
SEEDCASH_SRC = Path(r"C:\Users\reque\Desktop\seed-cash\src")
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(SEEDCASH_SRC))

from ctlab.engine import generate  # noqa: E402
from seedcash.models.psbt_parser import PSBTParser  # noqa: E402
from seedcash.models.bch_signer import parse_psbt, extract_tx_from_psbt, parse_unsigned_tx  # noqa: E402


CASES = [
    ("GEN-01", "bip174-v0", "unsigned"),
    ("GEN-04", "paytaca-145", "unsigned"),
    ("PSBT-02", "paytaca-145", "unsigned"),
    ("VOUT0-NO-GENESIS", "bip174-v0", "unsigned"),
    ("MONSTER-01", "paytaca-145", "unsigned"),
]


def probe(ident: str, dialect: str, sign: str) -> dict:
    vec = generate(ident, dialect=dialect, sign=sign)
    raw = bytes.fromhex(vec["psbt_hex"])
    out = {
        "id": ident,
        "dialect": dialect,
        "lab_txid": vec.get("txid"),
        "lab_bytes": len(raw),
        "lab_outputs": vec.get("outputs"),
        "lab_genesis": (vec.get("semantics") or {}).get("genesis_categories"),
        "parse_ok": False,
        "error": None,
    }
    try:
        maps = parse_psbt(raw)
        out["psbt_input_count_field"] = maps["input_count"]
        out["psbt_output_count_field"] = maps["output_count"]
        out["global_key_types"] = [k[:1].hex() for k, _ in maps["global"]]
        tx = parse_unsigned_tx(extract_tx_from_psbt(maps))
        out["unsigned_vin"] = len(tx["inputs"])
        out["unsigned_vout"] = len(tx["outputs"])
        scripts = []
        for o in tx["outputs"]:
            spk = o["script_pubkey"]
            scripts.append(
                {
                    "value_sats": int.from_bytes(o["value"], "little"),
                    "script_prefix": spk[:8].hex(),
                    "starts_ef": spk[:1] == b"\xef",
                    "looks_p2pkh": spk.startswith(b"\x76\xa9\x14") and spk.endswith(b"\x88\xac"),
                }
            )
        out["unsigned_output_scripts"] = scripts
        parser = PSBTParser(bytearray(raw))
        out["parse_ok"] = True
        out["seedcash"] = {
            "num_inputs": parser.num_inputs,
            "input_amount": parser.input_amount,
            "spend_amount": parser.spend_amount,
            "change_amount": parser.change_amount,
            "fee_amount": parser.fee_amount,
            "destinations": parser.destination_addresses,
            "destination_amounts": parser.destination_amounts,
            "op_return": parser.op_return_data.hex() if parser.op_return_data else None,
        }
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-1500:]
    return out


def main() -> int:
    reports = [probe(*c) for c in CASES]
    dest = LAB / "desktop" / "examples" / "seedcash_import_probe.json"
    dest.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    for r in reports:
        print("=" * 60)
        print(f"{r['id']}  dialect={r['dialect']}  bytes={r['lab_bytes']}")
        if r["error"]:
            print("  PARSE FAIL:", r["error"])
            continue
        sc = r["seedcash"]
        print(f"  maps in/out counts: {r['psbt_input_count_field']}/{r['psbt_output_count_field']}")
        print(f"  unsigned vin/vout:  {r['unsigned_vin']}/{r['unsigned_vout']}")
        print(f"  SeedCash num_inputs={sc['num_inputs']} input_sats={sc['input_amount']}")
        print(f"  spend={sc['spend_amount']} change={sc['change_amount']} fee={sc['fee_amount']}")
        print(f"  destinations={sc['destinations']}")
        print(f"  dest_amounts={sc['destination_amounts']}")
        for i, s in enumerate(r["unsigned_output_scripts"]):
            print(f"  vout{i}: {s['value_sats']} sats  ef={s['starts_ef']} p2pkh={s['looks_p2pkh']} prefix={s['script_prefix']}")
    print("\nWrote", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
