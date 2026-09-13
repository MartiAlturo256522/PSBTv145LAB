from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def cmd_generate(args: argparse.Namespace) -> int:
    from ctlab.vectors.catalog import build_catalog
    from ctlab.vectors.exporter import export_corpus
    from ctlab.vectors.generator import generate_corpus, generate_vector

    catalog = build_catalog()
    (ROOT / "vectors").mkdir(exist_ok=True)
    (ROOT / "vectors" / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    if args.config:
        from ctlab.engine import generate

        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        vec = generate(cfg, seed=args.seed, dialect=args.dialect, sign=args.sign)
        json.dump(vec, sys.stdout, indent=2)
        print()
        return 0 if vec.get("consensus_match") else 1
    if args.id:
        from ctlab.engine import generate

        vec = generate(args.id, seed=args.seed, dialect=args.dialect, sign=args.sign)
        json.dump(vec, sys.stdout, indent=2)
        print()
        return 0 if vec.get("consensus_match") else 1
    corpus = generate_corpus(catalog)
    export_corpus(corpus, ROOT / "vectors")
    n = len(corpus)
    fails = [v for v in corpus if not v.get("consensus_match") or not v.get("psbt_match") or v.get("error")]
    print(f"generated {n} vectors; catalog {len(catalog)}; mismatches {len(fails)}")
    for v in fails[:30]:
        print(f"  FAIL {v.get('id')} cons={v.get('actual_consensus')}/{v.get('expected_consensus')} "
              f"psbt={v.get('actual_psbt')}/{v.get('expected_psbt')} err={v.get('error') or v.get('actual_consensus_reason') or v.get('actual_psbt_error')}")
    return 0 if not fails else 1


def cmd_test(args: argparse.Namespace) -> int:
    import pytest

    return pytest.main([str(ROOT / "tests"), "-q"] + (["-k", args.k] if args.k else []))


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("app.server:app", host=args.host, port=args.port, reload=False)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    from ctlab.validators.differential import differential_report
    from ctlab.vectors.generator import generate_corpus

    corpus = generate_corpus()
    reports = [differential_report(v) for v in corpus]
    out = ROOT / "vectors" / "differential.json"
    out.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    fails = [r for r in reports if r["status"] != "PASS"]
    print(f"differential {len(reports)} reports, {len(fails)} FAIL/ERROR")
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ctlab", description="CashTokens PSBT Test Vector Laboratory")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--id")
    g.add_argument("--config", help="JSON scenario/config file")
    g.add_argument("--dialect")
    g.add_argument("--sign")
    g.add_argument("--seed", type=int, default=None)
    t = sub.add_parser("test")
    t.add_argument("-k")
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    sub.add_parser("diff")
    lab = sub.add_parser("lab", help="synthetic v145 laboratory")
    lab.add_argument("lab_argv", nargs=argparse.REMAINDER)
    args = p.parse_args(argv)
    if args.cmd == "generate":
        return cmd_generate(args)
    if args.cmd == "test":
        return cmd_test(args)
    if args.cmd == "serve":
        return cmd_serve(args)
    if args.cmd == "diff":
        return cmd_diff(args)
    if args.cmd == "lab":
        from ctlab.lab.cli import main as lab_main

        argv = list(args.lab_argv)
        if argv and argv[0] == "--":
            argv = argv[1:]
        return lab_main(argv)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
