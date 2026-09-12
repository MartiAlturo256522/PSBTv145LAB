"""Thin adapter. The only place the desktop talks to the frozen engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Frozen engine — do not wrap serialization here.
from ctlab import GENERATOR_VERSION
from ctlab.engine import generate
from ctlab.psbt.codec import decode_psbt
from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.exporter import export_corpus


def engine_version() -> str:
    return GENERATOR_VERSION


def engine_importable() -> tuple[bool, str]:
    try:
        v = generate("GEN-04", dialect="paytaca-145", sign="unsigned")
        ok = bool(v.get("psbt_hex") and v.get("consensus_match"))
        return ok, "PASS" if ok else "FAIL"
    except Exception as e:
        return False, f"FAIL ({type(e).__name__})"


def list_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": s["id"],
            "group": s["group"],
            "title": s["title"],
            "description": s.get("description") or s["title"],
            "dialects": s.get("dialects") or ["bip174-v0"],
            "sign_states": s.get("sign_states") or ["unsigned"],
        }
        for s in build_catalog()
    ]


def generate_psbt(
    config: str | dict[str, Any],
    *,
    seed: int | None = None,
    dialect: str = "paytaca-145",
    sign: str = "unsigned",
) -> dict[str, Any]:
    return generate(config, seed=seed, dialect=dialect, sign=sign)


def inspect_psbt(psbt_hex: str) -> dict[str, Any]:
    raw = bytes.fromhex(psbt_hex)
    psbt = decode_psbt(raw)
    return {
        "dialect": psbt.dialect,
        "version": psbt.version,
        "n_in": len(psbt.inputs),
        "n_out": len(psbt.outputs),
        "global_keys": [k.hex() for k, _ in psbt.global_pairs],
        "inputs": [[{"key": k.hex(), "value": v.hex()} for k, v in imap] for imap in psbt.inputs],
        "outputs": [[{"key": k.hex(), "value": v.hex()} for k, v in omap] for omap in psbt.outputs],
    }


def export_fixture(vector: dict[str, Any], dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    export_corpus([vector], dest)
    return dest
