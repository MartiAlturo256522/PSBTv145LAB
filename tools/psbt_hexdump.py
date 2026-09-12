#!/usr/bin/env python3
"""Print offset / key length / key / value length / value for every PSBT field."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from psbt_inspector import inspect, MAGIC  # noqa: E402


def load(arg: str) -> bytes:
    try:
        return bytes.fromhex(arg.strip())
    except ValueError:
        raw = open(arg, "rb").read()
        if raw[:5] != MAGIC:
            import base64

            raw = base64.b64decode(raw.decode("ascii", "ignore").strip())
        return raw


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: psbt_hexdump.py <hex|file>", file=sys.stderr)
        return 2
    info = inspect(load(argv[1]))
    print(
        f"# dialect={info['parse_dialect']} version={info['version_guess']} "
        f"in={info['input_count']} out={info['output_count']} "
        f"extra_sep={info['extra_input_separator']} trailing={info['trailing_bytes']!r}"
    )
    print(f"{'offset':>8}  {'kind':<16}  {'map':<16}  klen  key  vlen  value")
    for r in info["records"]:
        print(
            f"{r['offset']:8d}  {r['kind']:<16}  {r.get('map',''):<16}  "
            f"{r['key_length']:4d}  {r['key_bytes'] or '-':<20}  "
            f"{r['value_length']:4d}  {r['value_bytes'][:64]}{'…' if len(r['value_bytes'])>64 else ''}"
        )
    return 0 if info["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
