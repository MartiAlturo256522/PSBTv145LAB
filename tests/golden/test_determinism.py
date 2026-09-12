from pathlib import Path

from ctlab.vectors.generator import generate_vector
from ctlab.vectors.catalog import build_catalog

GOLDEN = Path(__file__).resolve().parents[2] / "vectors" / "golden"


def test_gen01_deterministic():
    sc = next(s for s in build_catalog() if s["id"] == "GEN-01")
    a = generate_vector(sc, dialect="bip174-v0", sign_state="unsigned")
    b = generate_vector(sc, dialect="bip174-v0", sign_state="unsigned")
    assert a["txid"] == b["txid"]
    assert a["unsigned_tx_hex"] == b["unsigned_tx_hex"]
    assert a["psbt_base64"] == b["psbt_base64"]


def test_signed_deterministic():
    sc = next(s for s in build_catalog() if s["id"] == "GEN-04")
    a = generate_vector(sc, dialect="bip174-v0", sign_state="signed")
    b = generate_vector(sc, dialect="bip174-v0", sign_state="signed")
    assert a["psbt_base64"] == b["psbt_base64"]
    assert a["sighash_info"][0]["signature"] == b["sighash_info"][0]["signature"]


def test_gen01_golden_txid():
    sc = next(s for s in build_catalog() if s["id"] == "GEN-01")
    v = generate_vector(sc, dialect="bip174-v0", sign_state="unsigned")
    expected = (GOLDEN / "GEN-01.txid").read_text(encoding="utf-8").strip()
    assert v["txid"] == expected
