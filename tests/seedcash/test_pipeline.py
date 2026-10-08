"""PSBTLAB → current GitHub SeedCash emulator. Semantic match required."""

from pathlib import Path
import pytest



from support.lab.pipeline import (
    BASIC_SET,
    M0_IDS,
    PERMUTE_SET,
    TOKEN_SET,
    pin,
    run_vector,
    run_set,
)
from core.receiver import psbt_parser
from core.psbt.codec import MAGIC


def test_receiver_is_local():
    assert pin()["implementation"] == "local-python-receiver"
    assert Path(psbt_parser.__file__).is_relative_to(Path(__file__).resolve().parents[2] / "src")


def test_crypto_psbt_helper_is_local():
    from helpers.ur2.crypto_psbt import wrap_psbt_cbor, unwrap_psbt_cbor
    raw = MAGIC + b"\x00"
    assert unwrap_psbt_cbor(wrap_psbt_cbor(raw)) == raw


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
