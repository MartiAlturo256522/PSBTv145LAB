"""Byte-level lab vs Paytaca-faithful translation.

The translation is NOT live Paytaca JS. A match is necessary but not
sufficient for VERIFIED.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "audits" / "paytaca"))
sys.path.insert(0, str(ROOT / "tools"))

from paytaca_codec import byte_diff, parse_psbt, serialize_paytaca  # noqa: E402
from psbt_inspector import inspect  # noqa: E402

from ctlab.psbt.codec import decode_psbt
from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_vector


def _psbt02():
    sc = next(s for s in build_catalog() if s["id"] == "PSBT-02")
    return generate_vector(sc, dialect="paytaca-145", sign_state="unsigned")


def test_inspector_sees_paytaca_extra_separator_and_sorted_keys():
    v = _psbt02()
    info = inspect(bytes.fromhex(v["psbt_hex"]))
    assert info["version_guess"] == 145
    assert info["has_psbt_out_cashtoken"] is True
    assert info["cashtoken_0x36_starts_with_ef"] is True
    assert not any(info["out_script_0x04_starts_with_ef"])
    assert info["extra_input_separator"] is not None
    assert info["parse_dialect"] == "paytaca"
    assert info["inputs_type_sorted"] is True
    assert info["outputs_type_sorted"] is True
    assert info["global_type_sorted"] is True


def test_lab_bytes_equal_paytaca_faithful_translation():
    v = _psbt02()
    lab = bytes.fromhex(v["psbt_hex"])
    parsed = parse_psbt(lab, extra_input_separator=True)
    faithful = serialize_paytaca(parsed["global"], parsed["inputs"], parsed["outputs"])
    diff = byte_diff(lab, faithful)
    assert lab == faithful, diff


def test_lab_decoder_roundtrip_paytaca_145():
    v = _psbt02()
    raw = bytes.fromhex(v["psbt_hex"])
    decoded = decode_psbt(raw)
    assert decoded.version == 145
    assert decoded.dialect == "paytaca-145"
    assert decoded.serialize() == raw
