"""Every valid row in the scenario document must become a consensus-valid PSBT and a UR."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor" / "seedcash" / "src"))

from ctlab.engine import generate_from_config
from ctlab.protocol.hashes import double_sha256
from scenario_ur.compile import apply_overrides, compile_config, schema_for
from scenario_ur.serve import App
from scenario_ur.ur_encode import encode_crypto_psbt
from seedcash.helpers.ur2.bytewords import Bytewords, Bytewords_Style_minimal

DOC = Path("/Users/martialturorequena/Desktop/psbtV145CashTokenScenarios.json")


def _doc():
    return json.loads(DOC.read_text(encoding="utf-8"))


def test_p2sh32_locking_script_is_hash256():
    from ctlab.fixtures.keys import ACTORS
    from ctlab.transactions.serialize import locking_script

    redeem = ACTORS["alice"].p2pkh()
    script = locking_script("p2sh32", double_sha256(redeem))
    assert script == b"\xaa\x20" + double_sha256(redeem) + b"\x87"
    assert len(script) == 35


def test_op_return_is_a_push():
    from ctlab.transactions.serialize import locking_script

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


def test_minting_split_is_invalid():
    scenario = next(s for s in _doc()["scenarios"] if s["slug"] == "minting-capability-splitting")
    _schema, params = apply_overrides(schema_for(scenario["slug"]), None)
    cfg, _note = compile_config(scenario, params)
    vec = generate_from_config(cfg)
    assert vec["actual_consensus"] == "invalid"


def test_ur_roundtrip_matches_seedcash_decoder():
    scenario = next(s for s in _doc()["scenarios"] if s["id"] == 1)
    _schema, params = apply_overrides(schema_for(scenario["slug"]), None)
    cfg, _note = compile_config(scenario, params)
    vec = generate_from_config(cfg)
    encoded = encode_crypto_psbt(bytes.fromhex(vec["psbt_hex"]), 4000)
    assert encoded["single"]
    body = encoded["parts"][0].split("/", 1)[1]
    assert encoded["parts"][0].startswith("ur:crypto-psbt/")
    decoded = bytes(Bytewords.decode(Bytewords_Style_minimal, body))
    assert decoded == bytes.fromhex(vec["psbt_hex"])


def test_document_fixture_is_served_until_regenerated():
    app = App(DOC)
    view = app.scenario_view("1", {}, None)
    assert view["ur"].startswith("ur:crypto-psbt/")
    assert view["note"].startswith("PSBT materializado")
    view2 = app.scenario_view("1", {"source": "generador", "input_sats": 80000, "fee_sats": 1000}, None)
    assert view2["consensus"] == "valid"
    assert view2["ur"].startswith("ur:crypto-psbt/")
