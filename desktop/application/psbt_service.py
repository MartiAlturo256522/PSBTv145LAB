"""Application service. No PSBT bytes constructed here."""

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
from desktop.application.presets import RANDOM_POOL


def validate_and_generate(
    state: BuilderState | None = None,
    *,
    catalog_id: str | None = None,
    raw_config: dict | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    dialect = "paytaca-145"
    sign = "unsigned"
    if catalog_id:
        vec = generate_psbt(catalog_id, seed=seed, dialect=dialect, sign=sign)
    elif raw_config is not None:
        vec = generate_psbt(raw_config, seed=seed, dialect=raw_config.get("dialect") or dialect, sign=sign)
    else:
        assert state is not None
        cfg = state.to_engine_config()
        vec = generate_psbt(cfg, seed=seed or state.seed, dialect=state.dialect, sign=state.sign)
    vec["_engine_version"] = engine_version()
    return vec


def random_case(complexity: str, seed: int) -> dict[str, Any]:
    pool = RANDOM_POOL.get(complexity) or RANDOM_POOL["Simple"]
    ident = pool[seed % len(pool)]
    return generate_psbt(ident, seed=seed, dialect="paytaca-145", sign="unsigned")


def status_line() -> dict[str, str]:
    ok, tests = engine_importable()
    return {
        "engine": "FROZEN",
        "version": engine_version(),
        "tests": tests if ok else tests,
        "dialect": "Paytaca v145",
        "network": "BCH",
        "mode": "Synthetic",
    }


def save_fixture(vector: dict[str, Any], dest: Path) -> Path:
    return export_fixture(vector, dest)


def inspect(vector: dict[str, Any]) -> dict[str, Any]:
    hx = vector.get("psbt_hex")
    if not hx:
        return {"error": "no psbt"}
    return inspect_psbt(hx)


def catalog() -> list[dict[str, Any]]:
    return list_catalog()
