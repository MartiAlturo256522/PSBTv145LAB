"""PSBTLAB → current GitHub SeedCash emulator. Semantic match required."""

from pathlib import Path

from ctlab.lab.pipeline import (
    BASIC_SET,
    M0_IDS,
    PERMUTE_SET,
    TOKEN_SET,
    pin,
    run_vector,
    run_set,
)
from ctlab.lab.seedcash_adapter import SEEDCASH_SRC
from ctlab.psbt.codec import MAGIC


def test_pin_is_current_github_head():
    p = pin()
    assert p["seedcash_commit"].startswith("4e10166")
    assert p["emulator_commit"].startswith("9d789cd")
    assert (Path(SEEDCASH_SRC) / "seedcash" / "models" / "psbt_parser.py").is_file()


def test_crypto_psbt_helper_present_on_emulator_tree():
    assert (Path(SEEDCASH_SRC) / "seedcash" / "helpers" / "ur2" / "crypto_psbt.py").is_file()


def test_basic_acceptance_set():
    rows = run_set(BASIC_SET)
    failed = [(r.get("label"), r.get("status"), r.get("differences")[:4]) for r in rows if r["status"] != "PASS"]
    assert not failed, failed


def test_parser_input_magic_on_simple_transfer():
    row = run_vector({"id": "IO-1-1", "dialect": "paytaca-145", "sign_state": "unsigned",
                      "inputs": [{"kind": "bch", "key": "A", "owner": "alice", "sats": 50000}],
                      "outputs": [{"owner": "bob", "sats": 48000}]})
    assert row["layers"]["parser_input_magic"] is True
    assert row["layers"]["raw_magic_hex"] == MAGIC.hex()
    assert row["status"] == "PASS"


def test_token_acceptance_set():
    rows = run_set(TOKEN_SET)
    failed = [(r.get("label"), r.get("status"), r.get("differences")[:4]) for r in rows if r["status"] != "PASS"]
    assert not failed, failed


def test_output_order_permutations():
    rows = run_set(PERMUTE_SET)
    failed = [(r.get("label"), r.get("status"), r.get("differences")[:4]) for r in rows if r["status"] != "PASS"]
    assert not failed, failed


def test_m0_regression_parses():
    """21 frozen vectors must parse; semantic match is required."""
    failed = []
    for ident in M0_IDS:
        row = run_vector(ident)
        if row["status"] != "PASS":
            failed.append((ident, row["status"], (row.get("differences") or [])[:4], row.get("error")))
    assert not failed, failed
