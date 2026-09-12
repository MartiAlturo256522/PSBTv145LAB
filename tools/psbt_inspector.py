#!/usr/bin/env python3
"""Independent PSBT hex dump. No ctlab imports — BIP-174 / Paytaca map walker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "audits" / "paytaca"))

from paytaca_codec import (  # noqa: E402
    MAGIC,
    decode_compact_size,
    is_paytaca_type_sorted,
    key_type_order,
    parse_psbt,
    type_hex,
)


def compact_size(buf: bytes, pos: int) -> tuple[int, int, bytes]:
    start = pos
    n, pos = decode_compact_size(buf, pos)
    return n, pos, buf[start:pos]


def walk_map(buf: bytes, pos: int, name: str) -> tuple[list[dict], int]:
    recs = []
    while pos < len(buf):
        start = pos
        klen, pos, _kraw = compact_size(buf, pos)
        if klen == 0:
            recs.append(
                {
                    "offset": start,
                    "kind": "separator",
                    "key_length": 0,
                    "key_bytes": "",
                    "value_length": 0,
                    "value_bytes": "",
                    "map": name,
                }
            )
            return recs, pos
        if pos + klen > len(buf):
            raise ValueError(f"truncated key at {start}")
        key = buf[pos : pos + klen]
        pos += klen
        vlen, pos, _vraw = compact_size(buf, pos)
        if pos + vlen > len(buf):
            raise ValueError(f"truncated value at {start}")
        val = buf[pos : pos + vlen]
        pos += vlen
        recs.append(
            {
                "offset": start,
                "kind": "keypair",
                "map": name,
                "key_length": klen,
                "key_bytes": key.hex(),
                "key_type": type_hex(key),
                "value_length": vlen,
                "value_bytes": val.hex(),
            }
        )
    raise ValueError(f"map {name} missing separator")


def inspect(buf: bytes) -> dict:
    if buf[:5] != MAGIC:
        raise ValueError("bad magic")
    parsed = parse_psbt(buf, extra_input_separator=None)
    recs: list[dict] = []
    pos = 5
    global_recs, pos = walk_map(buf, pos, "global")
    recs.extend(global_recs)
    for i in range(parsed["n_in"]):
        m, pos = walk_map(buf, pos, f"input[{i}]")
        recs.extend(m)
    extra_off = None
    if parsed["extra_input_separator"]:
        extra_off = pos
        recs.append(
            {
                "offset": pos,
                "kind": "extra_separator",
                "map": "after_inputs",
                "key_length": 0,
                "key_bytes": "",
                "value_length": 0,
                "value_bytes": "",
                "note": "Paytaca InputMap.serialize extra 0x00 (psbt.js L1261)",
            }
        )
        pos += 1
    for i in range(parsed["n_out"]):
        m, pos = walk_map(buf, pos, f"output[{i}]")
        recs.extend(m)

    input_orders = [key_type_order(p) for p in parsed["inputs"]]
    output_orders = [key_type_order(p) for p in parsed["outputs"]]
    has_36 = any(any(k[:1] == b"\x36" for k, _ in o) for o in parsed["outputs"])
    val_36 = []
    for o in parsed["outputs"]:
        for k, v in o:
            if k[:1] == b"\x36":
                val_36.append(v.hex())
    script_04 = []
    for o in parsed["outputs"]:
        for k, v in o:
            if k[:1] == b"\x04":
                script_04.append(v.hex())

    return {
        "magic": buf[:5].hex(),
        "version_guess": parsed["version"],
        "input_count": parsed["n_in"],
        "output_count": parsed["n_out"],
        "parse_dialect": parsed["dialect"],
        "extra_input_separator": extra_off,
        "trailing_bytes": parsed["trailing"].hex(),
        "ok": parsed["ok"] and not parsed["trailing"],
        "global_key_order": key_type_order(parsed["global"]),
        "global_type_sorted": is_paytaca_type_sorted(parsed["global"]),
        "input_key_orders": input_orders,
        "inputs_type_sorted": all(is_paytaca_type_sorted(p) for p in parsed["inputs"]),
        "output_key_orders": output_orders,
        "outputs_type_sorted": all(is_paytaca_type_sorted(p) for p in parsed["outputs"]),
        "has_psbt_out_cashtoken": has_36,
        "cashtoken_0x36_values": val_36,
        "cashtoken_0x36_starts_with_ef": all(v.startswith("ef") for v in val_36) if val_36 else None,
        "out_script_0x04_starts_with_ef": [s.startswith("ef") for s in script_04],
        "records": recs,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: psbt_inspector.py <hex|file>", file=sys.stderr)
        return 2
    arg = argv[1]
    try:
        raw = bytes.fromhex(arg.strip())
    except ValueError:
        raw = open(arg, "rb").read()
        if raw[:5] != MAGIC:
            text = raw.decode("ascii", "ignore").strip()
            import base64

            raw = base64.b64decode(text)
    print(json.dumps(inspect(raw), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
