"""Format is a lab invariant. Scenarios are semantic, not dialects."""

from desktop.application.builder_model import BuilderState
from desktop.application.identity import fixture_identity
from desktop.application.lab_contract import (
    DEFAULT_SCENARIO_ID,
    FORMAT_ID,
    FORMAT_VERSION,
    WIRE_DIALECT,
)
from desktop.application.presets import CATALOG_PRESETS, SCENARIOS, builder_from_catalog, get_scenario
from desktop.application.psbt_service import compare_encodings, validate_and_generate
from ctlab.engine import generate
from ctlab.psbt.codec import decode_psbt
from ctlab.vectors.catalog import build_catalog


def test_default_state_is_simple_transfer_v145():
    st = BuilderState()
    assert st.scenario_id == DEFAULT_SCENARIO_ID
    assert st.format_id == FORMAT_ID
    assert st.dialect == WIRE_DIALECT
    cfg = st.to_engine_config()
    assert cfg["dialect"] == WIRE_DIALECT
    assert cfg["format"] == FORMAT_ID
    assert st.inputs[0].kind == "bch"
    assert st.outputs[0].token.kind == "none"


def test_builder_never_inherits_catalog_first_dialect():
    """GEN-01 lists bip174-v0 first in the engine catalog. The lab must still emit v145."""
    cat = next(s for s in build_catalog() if s["id"] == "GEN-01")
    assert cat["dialects"][0] == "bip174-v0"
    st = builder_from_catalog("GEN-01")
    assert st.dialect == WIRE_DIALECT
    assert st.to_engine_config()["dialect"] == WIRE_DIALECT
    vec = validate_and_generate(catalog_id="GEN-01")
    assert vec["dialect"] == WIRE_DIALECT
    assert decode_psbt(bytes.fromhex(vec["psbt_hex"])).version == FORMAT_VERSION


def test_json_dialect_is_forced_to_v145():
    cfg = builder_from_catalog("GEN-04").to_engine_config()
    cfg["dialect"] = "bip174-v0"
    vec = validate_and_generate(raw_config=cfg)
    assert vec["dialect"] == WIRE_DIALECT
    assert vec["_lab"]["format"] == FORMAT_ID


def test_all_scenarios_encode_v145():
    failed = []
    for s in SCENARIOS:
        try:
            v = validate_and_generate(catalog_id=s.id)
            if v.get("dialect") != WIRE_DIALECT:
                failed.append((s.label, s.id, v.get("dialect")))
                continue
            if not v.get("psbt_hex"):
                failed.append((s.label, s.id, "no hex"))
                continue
            psbt = decode_psbt(bytes.fromhex(v["psbt_hex"]))
            if psbt.version != FORMAT_VERSION:
                failed.append((s.label, s.id, f"version {psbt.version}"))
        except Exception as e:
            failed.append((s.label, s.id, str(e)))
    assert not failed, failed


def test_genesis_ft_is_a_scenario_not_a_format():
    scn = get_scenario("GEN-04")
    assert scn.label == "Genesis FT"
    assert scn.group == "Genesis"
    v = validate_and_generate(catalog_id="GEN-04")
    ident = fixture_identity(v, scenario_id=scn.id, scenario_label=scn.label)
    assert ident.format_id == FORMAT_ID
    assert ident.psbt_version == FORMAT_VERSION
    assert ident.cashtokens is True
    assert ident.unsigned_tx_present is True
    assert ident.psbt_valid is True


def test_simple_transfer_matches_m0_vector():
    import hashlib
    from tools.lab.freeze_m0 import generate_m0, bch_io

    via_lab = validate_and_generate(catalog_id="IO-1-1")
    via_m0 = generate_m0(bch_io("IO-1-1", 1, 1))
    assert via_lab["psbt_hex"] == via_m0["psbt_hex"]
    assert hashlib.sha256(bytes.fromhex(via_lab["psbt_hex"])).hexdigest() == (
        "a9279e0a05a3e3d1d1a3ce415f63b34285e021e834a0e835b6128c6e4b7bc41f"
    )


def test_compare_keeps_v145_primary():
    vec = compare_encodings(catalog_id="GEN-04")
    assert vec["dialect"] == WIRE_DIALECT
    cmp = vec["_compare"]
    assert cmp["other_dialect"] == "bip174-v0"
    assert cmp["psbt_equal"] is False
    assert cmp["unsigned_tx_equal"] is True


def test_identity_lists_required_fields():
    v = validate_and_generate(catalog_id="IO-1-1")
    ident = fixture_identity(v)
    lines = "\n".join(ident.detail_lines())
    for key in (
        "PSBT format",
        "unsigned transaction present",
        "CashTokens",
        "input count",
        "output count",
        "scripts",
        "token operations",
        "Paytaca compatibility",
        "SeedCash compatibility",
        "semantic validation",
    ):
        assert key in lines
    assert ident.cashtokens is False
    assert ident.n_in == 1 and ident.n_out == 1


def test_catalog_presets_alias_is_scenarios():
    assert CATALOG_PRESETS[0] == ("Simple transfer", "IO-1-1")
    labels = [l for l, _ in CATALOG_PRESETS]
    assert "Paytaca v145 sample" not in labels
    assert "Genesis FT" in labels
    assert "Reference sample TX" in labels


def test_engine_catalog_generate_still_defaults_elsewhere():
    """Frozen engine is unchanged: omitting dialect still follows catalog order."""
    v = generate("GEN-01")
    assert v["dialect"] == "bip174-v0"
