"""Every valid row in the scenario document must become a consensus-valid PSBT and a UR."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.engine import generate_from_config
from core.protocol.hashes import double_sha256
from scenario_compile import apply_overrides, compile_config, schema_for
from document_support import ScenarioFixtures
from helpers.ur_service import encode_ur, decode_ur_parts


DOC = ROOT / "tests" / "fixtures" / "scenarios" / "psbtV145CashTokenScenarios.json"


def _doc():
    return json.loads(DOC.read_text(encoding="utf-8"))


def test_p2sh32_locking_script_is_hash256():
    from core.fixtures.keys import ACTORS
    from core.transactions.serialize import locking_script

    redeem = ACTORS["alice"].p2pkh()
    script = locking_script("p2sh32", double_sha256(redeem))
    assert script == b"\xaa\x20" + double_sha256(redeem) + b"\x87"
    assert len(script) == 35


def test_op_return_is_a_push():
    from core.transactions.serialize import locking_script

    script = locking_script("op_return", b"ctlab")
    assert script == bytes.fromhex("6a0563746c6162")


@pytest.mark.parametrize(
    "scenario",
    [s for s in _doc()["scenarios"] if s["validity"] == "valid-consensus"],
    ids=lambda s: f"{s['id']}-{s['slug']}",
)
def test_valid_document_scenario_generates(scenario):
    schema, params = apply_overrides(schema_for(scenario["slug"]), None)
    cfg, _note = compile_config(scenario, params)
    vec = generate_from_config(cfg)
    assert vec["actual_consensus"] == "valid", (scenario["slug"], vec.get("actual_consensus_reason"))
    assert vec["psbt_hex"]
    assert vec["psbt_hex"].startswith("70736274ff")
    assert vec["actual_psbt"] == "valid", vec.get("actual_psbt_error")
    ins = sum(u["value_sats"] for u in vec["source_utxos"])
    outs = sum(o["value_sats"] for o in vec["outputs"])
    assert outs <= ins


@pytest.mark.parametrize("slug", ["mint-fts-from-minting-nft", "combined-ft-nft-minting"])
def test_ft_mint_from_nft_is_invalid(slug):
    scenario = next(s for s in _doc()["scenarios"] if s["slug"] == slug)
    assert scenario["validity"] == "invalid-consensus"
    _schema, params = apply_overrides(schema_for(scenario["slug"]), None)
    cfg, _note = compile_config(scenario, params)
    vec = generate_from_config(cfg)
    assert vec["actual_consensus"] == "invalid"
    assert vec["actual_consensus_code"] in {"ft_without_genesis", "ft_overspend"}


def test_ur_roundtrip_preserves_psbt():
    scenario = next(s for s in _doc()["scenarios"] if s["id"] == 1)
    _schema, params = apply_overrides(schema_for(scenario["slug"]), None)
    cfg, _note = compile_config(scenario, params)
    vec = generate_from_config(cfg)
    encoded = encode_ur(vec["psbt_hex"], "Maximum")
    assert encoded["parts"][0].startswith("ur:crypto-psbt/")
    decoded = bytes.fromhex(decode_ur_parts(encoded["parts"]))
    assert decoded == bytes.fromhex(vec["psbt_hex"])


def test_document_fixture_and_density_share_the_same_psbt():
    app = ScenarioFixtures(DOC)
    high = app.scenario_view("1", "Máxima")
    low = app.scenario_view("1", "Baja")
    assert high["parts"][0].startswith("ur:crypto-psbt/")
    assert low["psbt_hex"] == high["psbt_hex"]
    assert len(low["parts"]) >= len(high["parts"])


REPO_DOC = ROOT / "tests" / "fixtures" / "scenarios" / "psbtV145CashTokenScenarios.json"
CORPUS = ROOT / "tests" / "fixtures" / "scenarios" / "optnCorpusVectors.json"
UPSTREAM = ROOT / "vectors" / "optn-seedcash-cashtokens.json"


def test_optn_supplied_psbts_match_existing_fixtures_and_are_not_duplicated():
    """M01–M08 in OPTN PR 101 are the fixtures already stored. They stay out of the new list."""
    upstream = json.loads(UPSTREAM.read_text(encoding="utf-8"))
    catalog = json.loads(REPO_DOC.read_text(encoding="utf-8"))
    fixtures = {fix["id"]: fix["psbtHex"].lower() for fix in catalog["materializedFixtures"]}
    supplied = [case for case in upstream["cases"] if case["id"].startswith("supplied-")]
    assert [case["id"] for case in supplied] == [f"supplied-M0{n}" for n in range(1, 9)]
    for case in supplied:
        fixture_id = case["id"].removeprefix("supplied-")
        assert case["psbt_hex"].lower() == fixtures[fixture_id]
    app = ScenarioFixtures(REPO_DOC)
    listed = {row["id"] for row in app.rows}
    assert not any(case["id"] in listed for case in supplied)


def test_optn_corpus_vectors_keep_their_psbt_and_encode_ur():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    vectors = corpus["vectors"]
    assert len(vectors) == 64
    assert corpus["source"]["vectorCount"] == 64
    app = ScenarioFixtures(REPO_DOC)
    listed = [row for row in app.rows if row["group"] == "vector"]
    assert [row["id"] for row in listed] == [item["id"] for item in vectors]
    assert len(app.rows) == 69 + 64
    by_id = {item["id"]: item for item in vectors}
    sample_ids = [
        vectors[0]["id"],
        next(item["id"] for item in vectors if item["validity"] == "invalid-consensus"),
        max(vectors, key=lambda item: len(item["psbtHex"]))["id"],
    ]
    for sid in sample_ids:
        view = app.scenario_view(sid, "Alta")
        assert view["psbt_hex"] == by_id[sid]["psbtHex"]
        assert view["psbt_hex"].startswith("70736274ff")
        assert view["parts"] and view["parts"][0].startswith("ur:crypto-psbt")
        assert view["scenario"]["group"] == "vector"
        assert view["scenario"]["label"] == by_id[sid]["label"]
        assert view["flow"].get("inputs")
    reject = next(item for item in vectors if item["id"] == "reject-ft-inflation")
    assert reject["validity"] == "invalid-consensus"
    assert app.scenario_view("1", "Alta")["psbt_hex"] != by_id["bch-control"]["psbtHex"]
