"""Run PSBTLAB → current SeedCash GitHub emulator differential pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from ctlab.lab.pipeline import (
        BASIC_SET,
        M0_IDS,
        MIXED_SET,
        PERMUTE_SET,
        TOKEN_SET,
        pin,
        run_set,
        run_vector,
        write_dashboard,
    )

    p = argparse.ArgumentParser(description="PSBTLAB × SeedCash pipeline oracle")
    p.add_argument("--set", choices=["basic", "tokens", "mixed", "m0", "permute", "all"], default="basic")
    p.add_argument("--id", help="single catalog id or BASIC label")
    args = p.parse_args(argv)

    print("PIN", json.dumps(pin(), indent=2))
    rows = []
    if args.id:
        rows = [run_vector(args.id)]
    elif args.set == "basic":
        rows = run_set(BASIC_SET)
    elif args.set == "tokens":
        rows = run_set(TOKEN_SET)
    elif args.set == "mixed":
        rows = run_set(MIXED_SET)
    elif args.set == "m0":
        rows = [run_vector(i) | {"label": i} for i in M0_IDS]
    elif args.set == "permute":
        rows = run_set(PERMUTE_SET)
    else:
        rows = run_set(BASIC_SET) + run_set(TOKEN_SET) + run_set(MIXED_SET) + run_set(PERMUTE_SET)
        rows += [run_vector(i) | {"label": i} for i in M0_IDS]

    path = write_dashboard(rows)
    fails = [r for r in rows if r.get("status") != "PASS"]
    for r in rows:
        mark = "PASS" if r.get("status") == "PASS" else r.get("status")
        print(f"{mark:22} {r.get('label') or r.get('vector_id')}  diffs={len(r.get('differences') or [])}")
        for d in (r.get("differences") or [])[:6]:
            print(f"    {d['path']}: expected={d['expected']!r} actual={d['actual']!r}")
    print(f"dashboard {path}  {len(rows) - len(fails)}/{len(rows)} PASS")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
