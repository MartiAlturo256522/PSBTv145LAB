"""Application service. No PSBT bytes constructed here.

Generate always encodes BCH PSBT v145. A second encoding is produced
only in compare/interop mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from desktop.adapter.engine_adapter import (
    engine_importable,
    engine_version,
    export_fixture,
    generate_psbt,
    inspect_psbt,
    list_catalog,
)
from desktop.application.builder_model import BuilderState
from desktop.application.identity import fixture_identity
from desktop.application.lab_contract import (
    FORMAT_ID,
    FORMAT_LABEL,
    INTEROP_DIALECT,
    INTEROP_FORMAT_LABEL,
    REFERENCE_LABEL,
    WIRE_DIALECT,
)
from desktop.application.presets import RANDOM_POOL, scenario_engine_source


def _attach_lab(vec: dict[str, Any], *, scenario_id: str = "", scenario_label: str = "", mode: str = "generate") -> dict[str, Any]:
    ident = fixture_identity(vec, scenario_id=scenario_id, scenario_label=scenario_label)
    vec["_lab"] = {
        "format": FORMAT_ID,
        "format_label": FORMAT_LABEL,
        "reference": REFERENCE_LABEL,
        "wire_dialect": WIRE_DIALECT,
        "mode": mode,
        "scenario_id": ident.scenario_id,
        "scenario_label": scenario_label,
        "identity": ident.to_dict(),
    }
    return vec


def _force_v145(raw: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(raw)
    cfg["format"] = FORMAT_ID
    cfg["dialect"] = WIRE_DIALECT
    return cfg


def validate_and_generate(
    state: BuilderState | None = None,
    *,
    catalog_id: str | None = None,
    raw_config: dict | None = None,
    seed: int | None = None,
    mode: str = "generate",
    scenario_label: str = "",
) -> dict[str, Any]:
    label = scenario_label
    scenario_id = catalog_id or ""
    if catalog_id:
        src = scenario_engine_source(catalog_id)
        if isinstance(src, dict):
            vec = generate_psbt(src, seed=seed, dialect=WIRE_DIALECT, sign=src.get("sign_state") or "unsigned")
        else:
            vec = generate_psbt(src, seed=seed, dialect=WIRE_DIALECT, sign="unsigned")
        scenario_id = catalog_id
    elif raw_config is not None:
        cfg = raw_config if mode == "compare" else _force_v145(raw_config)
        dialect = cfg.get("dialect") if mode == "compare" else WIRE_DIALECT
        vec = generate_psbt(cfg, seed=seed, dialect=dialect or WIRE_DIALECT, sign="unsigned")
        scenario_id = str(cfg.get("id") or "")
        label = label or str(cfg.get("title") or "")
    else:
        assert state is not None
        cfg = _force_v145(state.to_engine_config())
        vec = generate_psbt(cfg, seed=seed or state.seed, dialect=WIRE_DIALECT, sign=state.sign)
        scenario_id = state.scenario_id
        label = label or state.scenario_label
    if vec.get("dialect") != WIRE_DIALECT and mode != "compare":
        raise RuntimeError(
            f"lab invariant violated: expected {WIRE_DIALECT}, got {vec.get('dialect')}"
        )
    return _attach_lab(vec, scenario_id=scenario_id, scenario_label=label, mode=mode)


def compare_encodings(
    state: BuilderState | None = None,
    *,
    catalog_id: str | None = None,
    raw_config: dict | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Same semantic transaction: v145 (product) vs BIP-174 (interop only)."""
    primary = validate_and_generate(
        state, catalog_id=catalog_id, raw_config=raw_config, seed=seed, mode="generate"
    )
    if catalog_id:
        src = scenario_engine_source(catalog_id)
        other = generate_psbt(src, seed=seed, dialect=INTEROP_DIALECT, sign="unsigned")
    elif raw_config is not None:
        other = generate_psbt(raw_config, seed=seed, dialect=INTEROP_DIALECT, sign="unsigned")
    else:
        assert state is not None
        cfg = dict(state.to_engine_config())
        cfg["dialect"] = INTEROP_DIALECT
        other = generate_psbt(cfg, seed=seed or state.seed, dialect=INTEROP_DIALECT, sign=state.sign)
    primary["_compare"] = {
        "primary_format": FORMAT_LABEL,
        "other_format": INTEROP_FORMAT_LABEL,
        "other_dialect": INTEROP_DIALECT,
        "unsigned_tx_equal": primary.get("unsigned_tx_hex") == other.get("unsigned_tx_hex"),
        "psbt_equal": primary.get("psbt_hex") == other.get("psbt_hex"),
        "other_psbt_hex": other.get("psbt_hex"),
        "other_psbt_len": len(bytes.fromhex(other.get("psbt_hex") or "")),
        "primary_psbt_len": len(bytes.fromhex(primary.get("psbt_hex") or "")),
        "other_id": other.get("id"),
    }
    primary["_lab"]["mode"] = "compare"
    return primary


def random_case(complexity: str, seed: int) -> dict[str, Any]:
    pool = RANDOM_POOL.get(complexity) or RANDOM_POOL["Simple"]
    ident = pool[seed % len(pool)]
    return validate_and_generate(catalog_id=ident, seed=seed, mode="generate")


def status_line() -> dict[str, str]:
    ok, tests = engine_importable()
    return {
        "engine": "FROZEN",
        "version": engine_version(),
        "tests": tests if ok else tests,
        "format": FORMAT_LABEL,
        "reference": REFERENCE_LABEL,
        "network": "BCH",
        "mode": "Synthetic",
        "dialect": FORMAT_LABEL,
    }


def save_fixture(vector: dict[str, Any], dest: Path) -> Path:
    return export_fixture(vector, dest)


def inspect(vector: dict[str, Any]) -> dict[str, Any]:
    hx = vector.get("psbt_hex")
    if not hx:
        return {"error": "no psbt"}
    info = inspect_psbt(hx)
    info["lab_format"] = FORMAT_LABEL
    info["lab_identity"] = (vector.get("_lab") or {}).get("identity")
    return info


def catalog() -> list[dict[str, Any]]:
    return list_catalog()
