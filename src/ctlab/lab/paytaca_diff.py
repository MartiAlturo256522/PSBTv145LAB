"""Lab vs live Paytaca JS byte compare, plus independent v145 semantic walk.

Byte identity is live ``Psbt.deserialize+serialize`` only. A byte mismatch is
not a semantic mismatch: Paytaca GLOBAL_VERSION 145 is not BIP-174 and not
BIP-44 coin type 145'.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ctlab.lab.maps import maps_vs_unsigned, walk_paytaca_v145

LAB = Path(__file__).resolve().parents[3]


def _first_diff(a: bytes, b: bytes) -> dict[str, Any]:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return {
                "kind": "byte",
                "offset": i,
                "lab": a[max(0, i - 4) : i + 16].hex(),
                "paytaca": b[max(0, i - 4) : i + 16].hex(),
            }
    if len(a) != len(b):
        return {
            "kind": "byte",
            "offset": n,
            "lab": "",
            "paytaca": "",
            "len_mismatch": True,
            "lab_len": len(a),
            "paytaca_len": len(b),
        }
    return {}


def live_oracle_available() -> bool:
    try:
        if str(LAB) not in sys.path:
            sys.path.insert(0, str(LAB))
        from tools.oracles.compare_paytaca_real import NODE, RUNNER

        return Path(NODE).is_file() and Path(RUNNER).is_file()
    except Exception:
        return False


def _paytaca_roundtrip(hex_in: str) -> dict[str, Any]:
    if str(LAB) not in sys.path:
        sys.path.insert(0, str(LAB))
    from tools.oracles.compare_paytaca_real import paytaca_roundtrip

    return paytaca_roundtrip(hex_in)


def _semantic(lab_bytes: bytes) -> tuple[bool, list[dict[str, Any]], dict[str, Any]]:
    walk = walk_paytaca_v145(lab_bytes)
    diffs: list[dict[str, Any]] = []
    if walk["version"] != 145:
        diffs.append(
            {
                "kind": "semantic",
                "detail": f"version=={walk['version']} (want 145)",
            }
        )
    if not walk["extra_input_sep"]:
        diffs.append({"kind": "semantic", "detail": "missing extra_input_sep"})
    if walk["unsigned"] is None:
        diffs.append({"kind": "semantic", "detail": "unsigned tx missing"})
    vs = maps_vs_unsigned(lab_bytes)
    # maps_vs_unsigned.ok ignores naive-parser shift; that is not semantic.
    for d in vs.get("diffs") or []:
        if "naive" in d:
            continue
        if d.startswith("vout") or d.startswith("vin") or d == "no_unsigned_tx":
            diffs.append({"kind": "semantic", "detail": d})
    return not diffs, diffs, {"walk": walk, "maps_vs_unsigned": vs}


def compare_vector(psbt_hex: str) -> dict[str, Any]:
    lab_bytes = bytes.fromhex(psbt_hex.strip())
    semantic_identical, semantic_diffs, extra = _semantic(lab_bytes)
    differences: list[dict[str, Any]] = list(semantic_diffs)
    out: dict[str, Any] = {
        "vector": psbt_hex.strip(),
        "paytaca_bytes": None,
        "lab_bytes": lab_bytes,
        "byte_identical": False,
        "semantic_identical": semantic_identical,
        "differences": differences,
        "live": "SKIPPED",
        "version": extra["walk"]["version"],
        "extra_input_sep": extra["walk"]["extra_input_sep"],
    }
    if not live_oracle_available():
        return out
    try:
        r = _paytaca_roundtrip(psbt_hex.strip())
    except Exception as e:
        out["live"] = False
        differences.append({"kind": "byte", "detail": f"{type(e).__name__}: {e}"})
        return out
    if not r.get("ok"):
        out["live"] = False
        differences.append({"kind": "byte", "detail": r.get("error") or "paytaca_roundtrip failed"})
        return out
    paytaca_bytes = bytes.fromhex(r["output_hex"])
    byte_identical = lab_bytes == paytaca_bytes
    out["live"] = True
    out["paytaca_bytes"] = paytaca_bytes
    out["byte_identical"] = byte_identical
    if not byte_identical:
        differences.append(_first_diff(lab_bytes, paytaca_bytes))
    return out
