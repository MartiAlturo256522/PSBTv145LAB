"""Regression for the five freeze warnings."""

import json
from pathlib import Path

from ctlab.engine import generate
from ctlab.psbt.codec import decode_psbt
from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_vector

ROOT = Path(__file__).resolve().parents[2]


def test_baton_burn_semantics():
    v = generate("POST-04", dialect="bip174-v0", sign="unsigned")
    baton = [b for b in v["semantics"]["burns"] if b.get("kind") == "baton"]
    assert baton, v["semantics"]["burns"]
    assert baton[0]["capability"] == "minting"
    mint = v["semantics"]["mint"]
    assert mint and mint[0]["baton"] == "burned"


def test_same_category_tokens_public_api():
    v = generate(
        {
            "id": "CUSTOM-SAMECAT",
            "existing": [
                {"key": "A1", "owner": "alice", "sats": 8000, "token": {"nft": None, "amount": 40}, "category_group": "A"},
                {
                    "key": "A2",
                    "owner": "alice",
                    "sats": 8000,
                    "token": {"nft": {"capability": "none", "commitment": "id"}, "amount": 0},
                    "category_group": "A",
                },
            ],
            "inputs": [
                {"kind": "token", "key": "A1", "owner": "alice"},
                {"kind": "token", "key": "A2", "owner": "alice"},
            ],
            "outputs": [
                {
                    "owner": "bob",
                    "sats": 14000,
                    "token": {"category_from_existing": "A1", "amount": 40, "nft": {"capability": "none", "commitment": "id"}},
                }
            ],
        }
    )
    assert v["consensus_match"] is True, v.get("actual_consensus_reason")
    cats = v["semantics"]["categories"]
    assert len(cats) == 1


def test_catalog_fixture_expected_psbt_integrity():
    catalog = {s["id"]: s for s in build_catalog()}
    both = []
    for sc in catalog.values():
        ident = sc["id"]
        hits = []
        for folder in ("valid", "invalid", "complex"):
            p = ROOT / "vectors" / folder / ident / "vector.json"
            if p.exists():
                hits.append(folder)
                data = json.loads(p.read_text(encoding="utf-8"))
                assert data["expected_psbt"] == sc["expected_psbt"], ident
                assert data["expected_consensus"] == sc["expected_consensus"], ident
        if len(hits) > 1:
            both.append((ident, hits))
    assert not both, f"duplicate fixture dirs: {both}"
    sig = generate_vector(catalog["SIG-06"])
    assert sig["expected_psbt"] == catalog["SIG-06"]["expected_psbt"] == "valid"


def test_catalog_configuration_coverage():
    known_top = {
        "id", "group", "title", "description", "expected_consensus", "expected_psbt",
        "invalid_code", "existing", "inputs", "outputs", "script_type", "sighash",
        "dialects", "sign_states", "justification",
        "truncate", "bad_magic", "duplicate_unsigned", "omit_utxo", "tamper_0x36_amount",
        "force_sighash", "token_bearing_vout0", "seedcash_expected", "assert_genesis_empty",
        "record_endianness", "bcmr_metadata_only", "inject",
        "_same_category_clone", "_seed",
    }
    unknown = []
    for sc in build_catalog():
        for k in sc:
            if k not in known_top:
                unknown.append((sc["id"], k))
    assert not unknown, f"undocumented catalog keys: {unknown}"
    enc = generate("ENC-04")
    assert enc["category_endianness"] and enc["category_endianness"]["category_ui"] != enc["category_endianness"]["category_wire"]
    bcmr = generate("BCMR-01")
    assert bcmr["bcmr_metadata_only"] is True


def test_p2sh_redeem_script_behavior():
    v = generate("SCR-02", dialect="bip174-v0", sign="unsigned")
    raw = bytes.fromhex(v["psbt_hex"])
    decoded = decode_psbt(raw)
    found = any(k[:1] == b"\x00" for o in decoded.outputs for k, _ in o)
    assert found, "P2SH20 output must carry PSBT_OUT_REDEEM_SCRIPT"
    v32 = generate("SCR-03", dialect="bip174-v0", sign="unsigned")
    d32 = decode_psbt(bytes.fromhex(v32["psbt_hex"]))
    assert any(k[:1] == b"\x00" for o in d32.outputs for k, _ in o)
