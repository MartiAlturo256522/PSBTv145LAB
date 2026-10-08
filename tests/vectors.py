"""Load vector definitions and generate or extract PSBT fixtures for tests.

Import this module from tests; it deliberately has no command line interface.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from core.vectors.generator import generate_vector
from core.vectors.exporter import export_corpus

MANIFEST = Path(__file__).with_suffix(".json")


def load_vectors(path: Path = MANIFEST) -> list[dict[str, Any]]:
    definitions = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(definitions, list):
        raise ValueError("vector manifest must be a list")
    ids: set[str] = set()
    for definition in definitions:
        if not isinstance(definition, dict) or not isinstance(definition.get("id"), str):
            raise ValueError("each vector requires a string id")
        if definition["id"] in ids:
            raise ValueError(f"duplicate vector id: {definition['id']}")
        ids.add(definition["id"])
    return definitions


def generate_vectors(ids: Iterable[str] | None = None, *, seed: int | None = None) -> list[dict[str, Any]]:
    definitions = load_vectors()
    if ids is not None:
        requested = set(ids)
        unknown = requested - {d["id"] for d in definitions}
        if unknown:
            raise ValueError(f"unknown vector ids: {', '.join(sorted(unknown))}")
        definitions = [d for d in definitions if d["id"] in requested]
    if seed is not None:
        definitions = [dict(d, _seed=seed) for d in definitions]
    return [generate_vector(d, dialect="paytaca-145", sign_state="unsigned") for d in definitions]


def extract_vectors(destination: Path, ids: Iterable[str] | None = None, *, seed: int | None = None) -> Path:
    """Export selected manifest cases using the engine's standard fixture layout."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    export_corpus(generate_vectors(ids, seed=seed), destination)
    return destination
