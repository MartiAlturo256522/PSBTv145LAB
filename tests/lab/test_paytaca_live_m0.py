"""Live Paytaca JS M0: GEN-04, IO-2-3, SCR-05, POST-01, MONSTER-01."""

from __future__ import annotations

import pytest

from ctlab.engine import generate
from ctlab.lab.maps import walk_paytaca_v145
from ctlab.lab.paytaca_diff import compare_vector


def bch_io(ident: str, n_in: int, n_out: int, *, change: bool = False) -> dict:
    """Same generator as audits/seedcash-v145/run_audit.py."""
    inputs = [
        {"kind": "bch", "key": chr(ord("A") + i), "owner": "alice", "sats": 50_000}
        for i in range(n_in)
    ]
    outputs = []
    owners = ["bob", "carol", "dave", "alice"]
    remaining = 50_000 * n_in - 2000
    for i in range(n_out):
        owner = "alice" if (change and i == n_out - 1) else owners[i % 3]
        sat = remaining // (n_out - i) if i < n_out - 1 else remaining
        remaining -= sat
        outputs.append({"owner": owner, "sats": max(sat, 546)})
    return {
        "id": ident,
        "dialect": "paytaca-145",
        "sign_state": "unsigned",
        "inputs": inputs,
        "outputs": outputs,
    }


def _generate(ident: str) -> dict:
    if ident == "IO-2-3":
        return generate(bch_io("IO-2-3", 2, 3, change=True), dialect="paytaca-145", sign="unsigned")
    return generate(ident, dialect="paytaca-145", sign="unsigned")


M0_IDS = ("GEN-04", "IO-2-3", "SCR-05", "POST-01", "MONSTER-01")


@pytest.mark.parametrize("ident", M0_IDS)
def test_paytaca_live_m0(ident: str) -> None:
    vec = _generate(ident)
    raw = bytes.fromhex(vec["psbt_hex"])
    walked = walk_paytaca_v145(raw)
    assert walked["version"] == 145
    assert walked["extra_input_sep"] is True
    cmp = compare_vector(vec["psbt_hex"])
    assert cmp["semantic_identical"] is True
    if cmp.get("live") is True:
        assert cmp["byte_identical"] is True
