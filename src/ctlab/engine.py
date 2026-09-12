"""Data-driven PSBT v145 generator — the product motor.

Callers (CLI, tests, UI) all use ``generate_from_config``. Catalog
scenarios are one kind of config; custom JSON is another.
"""

from __future__ import annotations

from typing import Any

from ctlab.vectors.generator import generate_vector


def normalize_config(config: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    dialect = (
        config.get("dialect")
        or (config.get("psbt") or {}).get("dialect")
        or (config.get("paytaca") or {}).get("dialect")
        or "paytaca-145"
    )
    sign = config.get("sign_state") or config.get("sign") or "unsigned"
    sc = {
        "id": config.get("id", "CUSTOM"),
        "group": config.get("group", "custom"),
        "title": config.get("title", "custom"),
        "description": config.get("description", "custom"),
        "expected_consensus": config.get("expected_consensus", "valid"),
        "expected_psbt": config.get("expected_psbt", "valid"),
        "invalid_code": config.get("invalid_code"),
        "existing": config.get("existing") or [],
        "inputs": config.get("inputs") or [],
        "outputs": config.get("outputs") or [],
        "script_type": config.get("script_type", "p2pkh"),
        "sighash": config.get("sighash", "ALL|FORKID"),
        "dialects": [dialect],
        "sign_states": [sign],
        "justification": config.get("justification", "user config"),
    }
    extra = config.get("extra")
    if extra:
        sc.update(extra)
    return sc, dialect, sign


def generate_from_config(config: dict[str, Any]) -> dict[str, Any]:
    sc, dialect, sign = normalize_config(config)
    return generate_vector(sc, dialect=dialect, sign_state=sign)


def generate(
    scenario: str | dict[str, Any],
    seed: int | None = None,
    dialect: str | None = None,
    sign: str | None = None,
) -> dict[str, Any]:
    """Public motor: catalog id or declarative dict → vector.

    ``seed`` is recorded and mixed into synthetic parent tags when set so
    two seeds never collide; omit it for golden catalog vectors.
    """
    import copy

    from ctlab.vectors.catalog import build_catalog

    if isinstance(scenario, str):
        sc = copy.deepcopy(next(s for s in build_catalog() if s["id"] == scenario))
        d = dialect or (sc.get("dialects") or ["paytaca-145"])[0]
        s = sign or (sc.get("sign_states") or ["unsigned"])[0]
    else:
        sc, d, s = normalize_config(scenario)
        if dialect:
            d = dialect
        if sign:
            s = sign
    if seed is not None:
        sc["_seed"] = int(seed)
    return generate_vector(sc, dialect=d, sign_state=s)
