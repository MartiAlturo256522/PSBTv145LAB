"""Laboratory CLI. Capabilities: generate, compare, fuzz, coverage, regression, inspect."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from ctlab.lab import LAB_CAMPAIGN_VERSION, PAYTACA_PSBT_JS


def _sha(hex_or_bytes: str | bytes) -> str:
    raw = bytes.fromhex(hex_or_bytes) if isinstance(hex_or_bytes, str) else hex_or_bytes
    return hashlib.sha256(raw).hexdigest()


def _materialize(intent) -> dict[str, Any]:
    from ctlab.engine import generate
    from ctlab.lab.maps import maps_vs_unsigned, walk_paytaca_v145

    vec = generate(intent.to_engine_config(), dialect="paytaca-145", sign="unsigned")
    raw = bytes.fromhex(vec.get("psbt_hex") or "")
    walk = walk_paytaca_v145(raw) if raw else {}
    cons = maps_vs_unsigned(raw) if raw else {}
    return {
        "id": intent.id,
        "seed": intent.seed,
        "generator_version": vec.get("generator_version"),
        "lab_campaign_version": LAB_CAMPAIGN_VERSION,
        "reference_version": PAYTACA_PSBT_JS,
        "transaction_intent": intent.to_json(),
        "psbt_hex": vec.get("psbt_hex"),
        "psbt_bytes_sha256": _sha(raw) if raw else None,
        "unsigned_tx_sha256": _sha(walk["unsigned"]) if walk.get("unsigned") else None,
        "txid": vec.get("txid"),
        "maps": cons,
        "paytaca_walk": {
            "version": walk.get("version"),
            "n_in": walk.get("n_in"),
            "n_out": walk.get("n_out"),
            "extra_input_sep": walk.get("extra_input_sep"),
            "output_types": walk.get("output_types"),
        },
        "semantics": vec.get("semantics"),
        "error": vec.get("error"),
        "mutations": list(intent.mutations),
    }


def cmd_generate(args: argparse.Namespace) -> int:
    from ctlab.lab.generate import campaign_intents, m1_intents, m2_token_intents, materialize

    mode = args.mode or ("CASH_TOKENS" if args.tokens else "NORMAL")
    if args.adversarial:
        mode = "ADVERSARIAL"
    if args.monster:
        mode = "MONSTER"
    if args.m1:
        intents = m1_intents(args.seed)
    elif args.m2:
        intents = m2_token_intents(args.seed)
    else:
        intents = campaign_intents(args.count, args.seed, mode)
    out_dir = Path(args.export) if args.export else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    records = []
    for intent in intents:
        rec = materialize(intent)
        sha = rec.get("psbt_sha256") or rec.get("psbt_bytes_sha256") or ""
        records.append({"id": rec.get("id"), "sha256": sha, "maps_ok": (rec.get("maps") or {}).get("ok")})
        n_ok += 1 if rec.get("psbt_hex") else 0
        if out_dir and rec.get("psbt_hex"):
            (out_dir / f"{intent.id}.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
            (out_dir / f"{intent.id}.psbt.hex").write_text(rec["psbt_hex"], encoding="ascii")
        if args.verbose:
            print(f"{intent.id} n={intent.n_in}/{intent.n_out} sha={str(sha)[:16]}")
    print(json.dumps({"mode": mode, "seed": args.seed, "count": len(intents), "ok": n_ok, "version": LAB_CAMPAIGN_VERSION, "ids": [r["id"] for r in records[:50]]}, indent=2))
    return 0 if n_ok == len(intents) else 1


def cmd_compare_paytaca(args: argparse.Namespace) -> int:
    from ctlab.engine import generate
    from ctlab.lab.paytaca_diff import compare_vector

    ids = args.ids or ["GEN-04", "SCR-05", "POST-01", "MONSTER-01"]
    rows = []
    for ident in ids:
        vec = generate(ident, dialect="paytaca-145", sign="unsigned")
        rows.append(compare_vector(vec["psbt_hex"], ident=ident))
    print(json.dumps(rows, indent=2, default=str))
    fails = [r for r in rows if r.get("byte_identical") is False]
    return 0 if not fails else 1


def cmd_compare_seedcash(args: argparse.Namespace) -> int:
    from ctlab.engine import generate
    from ctlab.lab.intent import TransactionIntent
    from ctlab.lab.oracle import evaluate
    from ctlab.lab.generate import m1_intents, m2_token_intents

    intents = m1_intents(args.seed) + m2_token_intents(args.seed)
    if args.count:
        intents = intents[: args.count]
    findings = []
    for intent in intents:
        vec = generate(intent.to_engine_config(), dialect="paytaca-145", sign="unsigned")
        findings.append(evaluate(intent, vec))
    sev = {}
    for f in findings:
        s = f.get("severity") or "INFO"
        sev[s] = sev.get(s, 0) + 1
    print(json.dumps({"n": len(findings), "severity": sev, "findings": findings}, indent=2, default=str))
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    from ctlab.lab.coverage import CoverageTracker
    from ctlab.lab.generate import campaign_intents, m1_intents, m2_token_intents

    tr = CoverageTracker()
    for it in m1_intents(0) + m2_token_intents(0) + campaign_intents(args.count or 200, args.seed, "NORMAL"):
        tr.observe(it)
    print(json.dumps(tr.report(), indent=2))
    return 0


def cmd_regression(args: argparse.Namespace) -> int:
    import pytest
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    return pytest.main([str(root / "tests" / "regression"), str(root / "tests" / "lab"), "-q"])


def cmd_inspect(args: argparse.Namespace) -> int:
    from ctlab.lab.maps import maps_vs_unsigned, walk_paytaca_v145

    raw = Path(args.psbt).read_bytes()
    if all(c in b"0123456789abcdefABCDEF\n\r " for c in raw[:80]):
        raw = bytes.fromhex(raw.decode().strip())
    walk = walk_paytaca_v145(raw)
    cons = maps_vs_unsigned(raw)
    print(json.dumps({"walk": {k: walk[k] for k in walk if k not in ("unsigned", "global", "inputs", "outputs")}, "consistency": cons}, indent=2, default=str))
    return 0


def cmd_mutate(args: argparse.Namespace) -> int:
    from ctlab.engine import generate
    from ctlab.lab.mutate import mutate_psbt

    vec = generate(args.id or "GEN-04", dialect="paytaca-145", sign="unsigned")
    mutants = mutate_psbt(vec["psbt_hex"])
    print(json.dumps([{"name": m["name"], "class": m.get("expected_class"), "len": len(m.get("psbt_hex") or "")} for m in mutants], indent=2))
    return 0


def cmd_fuzz(args: argparse.Namespace) -> int:
    from ctlab.lab.generate import campaign_intents
    from ctlab.lab.mutate import mutate_psbt

    n = 0
    fails = 0
    for intent in campaign_intents(args.count, args.seed, "ADVERSARIAL" if args.adversarial else "NORMAL"):
        rec = _materialize(intent)
        n += 1
        if not rec.get("psbt_hex"):
            fails += 1
            continue
        for m in mutate_psbt(rec["psbt_hex"])[: args.mutations]:
            n += 1
            if not m.get("psbt_hex"):
                fails += 1
    print(json.dumps({"generated": n, "fails": fails, "seed": args.seed, "version": LAB_CAMPAIGN_VERSION}))
    return 0 if fails == 0 else 1


def cmd_extra00(args: argparse.Namespace) -> int:
    from ctlab.lab.extra00 import extra00_family

    fam = extra00_family(args.seed)
    print(json.dumps(fam, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ctlab lab", description="Synthetic BCH PSBT v145 laboratory")
    sub = p.add_subparsers(dest="labcmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--count", type=int, default=64)
    g.add_argument("--seed", type=int, default=20260913)
    g.add_argument("--mode", default=None)
    g.add_argument("--tokens", action="store_true")
    g.add_argument("--adversarial", action="store_true")
    g.add_argument("--monster", action="store_true")
    g.add_argument("--m1", action="store_true")
    g.add_argument("--m2", action="store_true")
    g.add_argument("--export")
    g.add_argument("--verbose", action="store_true")
    g.add_argument("--inputs", type=int)
    g.add_argument("--outputs", type=int)
    cp = sub.add_parser("compare-paytaca")
    cp.add_argument("--ids", nargs="*")
    cs = sub.add_parser("compare-seedcash")
    cs.add_argument("--seed", type=int, default=0)
    cs.add_argument("--count", type=int, default=0)
    cov = sub.add_parser("coverage")
    cov.add_argument("--count", type=int, default=200)
    cov.add_argument("--seed", type=int, default=0)
    sub.add_parser("regression")
    ins = sub.add_parser("inspect")
    ins.add_argument("psbt")
    mu = sub.add_parser("mutate")
    mu.add_argument("--id", default="GEN-04")
    fz = sub.add_parser("fuzz")
    fz.add_argument("--count", type=int, default=100)
    fz.add_argument("--seed", type=int, default=20260913)
    fz.add_argument("--mutations", type=int, default=8)
    fz.add_argument("--adversarial", action="store_true")
    e0 = sub.add_parser("extra00")
    e0.add_argument("--seed", type=int, default=0)
    sub.add_parser("export")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = args.labcmd.replace("-", "_")
    fn = {
        "generate": cmd_generate,
        "compare_paytaca": cmd_compare_paytaca,
        "compare_seedcash": cmd_compare_seedcash,
        "coverage": cmd_coverage,
        "regression": cmd_regression,
        "inspect": cmd_inspect,
        "mutate": cmd_mutate,
        "fuzz": cmd_fuzz,
        "extra00": cmd_extra00,
        "export": cmd_generate,
    }.get(cmd)
    if not fn:
        return 2
    return fn(args)
