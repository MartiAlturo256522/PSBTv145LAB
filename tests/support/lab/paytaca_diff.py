"""Lab vs independent Python wire reference, plus v145 semantic walk.

The reference is a Python specification translation. A byte mismatch is
not a semantic mismatch: Paytaca GLOBAL_VERSION 145 is not BIP-174 and not
BIP-44 coin type 145'.
"""

from __future__ import annotations

from typing import Any

from support.lab.maps import maps_vs_unsigned, walk_paytaca_v145


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
        "lab_bytes": lab_bytes,
        "byte_identical": False,
        "semantic_identical": semantic_identical,
        "differences": differences,
        "version": extra["walk"]["version"],
        "extra_input_sep": extra["walk"]["extra_input_sep"],
    }
    # Independent Python implementation; this is not live Paytaca verification.
    from core.validators.paytaca_reference import parse_psbt, serialize_paytaca

    parsed = parse_psbt(lab_bytes, extra_input_separator=True)
    if not parsed["ok"]:
        raise ValueError("trailing bytes after v145 maps")
    reference_bytes = serialize_paytaca(parsed["global"], parsed["inputs"], parsed["outputs"])
    out["reference"] = "python-wire-reference"
    out["reference_bytes"] = reference_bytes
    out["byte_identical"] = lab_bytes == reference_bytes
    if not out["byte_identical"]:
        differences.append(_first_diff(lab_bytes, reference_bytes))
    return out
