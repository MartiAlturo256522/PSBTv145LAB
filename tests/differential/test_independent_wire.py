"""Lab serialize vs independent Paytaca v145 wire (JS Object.keys order)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from core.validators.wire_reference import serialize_paytaca_v145  # noqa: E402
from core.validators.paytaca_reference import parse_psbt  # noqa: E402

from core.vectors.catalog import build_catalog
from core.vectors.generator import generate_vector


def test_independent_matches_lab_psbt02():
    sc = next(s for s in build_catalog() if s["id"] == "PSBT-02")
    v = generate_vector(sc, dialect="paytaca-145", sign_state="unsigned")
    lab = bytes.fromhex(v["psbt_hex"])
    parsed = parse_psbt(lab, extra_input_separator=True)
    indie = serialize_paytaca_v145(parsed["global"], parsed["inputs"], parsed["outputs"])
    assert lab == indie
