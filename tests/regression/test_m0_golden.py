"""Golden regression for the audited 21 Paytaca PSBT v145 (M0) vectors.

Dialect is paytaca-145. GLOBAL_VERSION is 145. Extra input-map 0x00 must be present.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ctlab.lab.maps import walk_paytaca_v145
from ctlab.psbt.codec import PSBT_GLOBAL_VERSION, decode_psbt
from tools.lab.freeze_m0 import CASES, FROZEN_DIR, generate_m0

INDEX_PATH = FROZEN_DIR / "index.json"
V145_LE = (145).to_bytes(4, "little")


def _load_index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _index_by_id() -> dict[str, dict]:
    return {row["id"]: row for row in _load_index()["vectors"]}


def test_m0_index_covers_all_cases():
    index = _load_index()
    assert index["dialect"] == "paytaca-145"
    assert index["sign_state"] == "unsigned"
    ids = [row["id"] for row in index["vectors"]]
    expected = [c[0] for c in CASES]
    assert ids == expected
    assert len(ids) == 21


@pytest.mark.parametrize("ident,spec,_desc", CASES, ids=[c[0] for c in CASES])
def test_m0_golden_regenerate(ident: str, spec, _desc: str):
    frozen = _index_by_id()[ident]
    vec = generate_m0(spec)
    raw = bytes.fromhex(vec["psbt_hex"])
    unsigned = bytes.fromhex(vec["unsigned_tx_hex"])

    assert hashlib.sha256(raw).hexdigest() == frozen["psbt_sha256"]
    assert hashlib.sha256(unsigned).hexdigest() == frozen["unsigned_tx_sha256"]
    assert len(raw) == frozen["psbt_len"]

    decoded = decode_psbt(raw)
    assert decoded.version == 145
    assert decoded.dialect == "paytaca-145"
    assert any(
        k[:1] == bytes([PSBT_GLOBAL_VERSION]) and v == V145_LE for k, v in decoded.global_pairs
    )

    walked = walk_paytaca_v145(raw)
    assert walked["version"] == 145
    assert walked["extra_input_sep"] is True
    assert walked["n_in"] == frozen["n_in"]
    assert walked["n_out"] == frozen["n_out"]

    disk_hex = (FROZEN_DIR / f"{ident}.psbt.hex").read_text(encoding="ascii").strip()
    assert disk_hex == vec["psbt_hex"]
