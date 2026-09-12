"""UI must not mutate engine output. Adapter is a pass-through."""

from desktop.adapter.engine_adapter import generate_psbt, inspect_psbt
from desktop.application.builder_model import BuilderState, InputUI, OutputUI, TokenUI
from desktop.application.psbt_service import validate_and_generate
from ctlab.engine import generate


def test_adapter_matches_engine_catalog():
    a = generate_psbt("GEN-04", dialect="paytaca-145", sign="unsigned")
    b = generate("GEN-04", dialect="paytaca-145", sign="unsigned")
    assert a["psbt_hex"] == b["psbt_hex"]
    assert a["psbt_base64"] == b["psbt_base64"]


def test_builder_genesis_ft_goes_through_engine():
    st = BuilderState()
    st.inputs = [InputUI(key="A", kind="genesis_parent", sats=100000)]
    st.outputs = [
        OutputUI(
            sats=98000,
            genesis_from=0,
            token=TokenUI(kind="ft", ft_amount=9, category_mode="auto"),
        )
    ]
    vec = validate_and_generate(st)
    assert vec.get("psbt_hex")
    assert vec["dialect"] == "paytaca-145"
    assert vec["psbt_hex"] == generate(st.to_engine_config(), dialect="paytaca-145")["psbt_hex"]


def test_same_category_group_in_builder():
    st = BuilderState()
    st.inputs = [
        InputUI(
            key="A1",
            kind="token",
            token=TokenUI(kind="ft", ft_amount=40, category_mode="group", category_group="A"),
        ),
        InputUI(
            key="A2",
            kind="token",
            token=TokenUI(
                kind="nft",
                nft="immutable",
                commitment="id",
                category_mode="group",
                category_group="A",
            ),
        ),
    ]
    st.outputs = [
        OutputUI(
            sats=14000,
            token=TokenUI(
                kind="hybrid",
                ft_amount=40,
                nft="immutable",
                commitment="id",
                category_mode="group",
                category_group="A",
            ),
        )
    ]
    cfg = st.to_engine_config()
    assert cfg["existing"][0]["category_group"] == "A"
    vec = validate_and_generate(st)
    assert vec["consensus_match"] is True, vec.get("actual_consensus_reason")


def test_inspect_does_not_change_bytes():
    v = generate_psbt("PSBT-02", dialect="paytaca-145")
    before = v["psbt_hex"]
    inspect_psbt(before)
    assert v["psbt_hex"] == before


def test_monster_preset_identity():
    v = generate_psbt("MONSTER-01", dialect="paytaca-145")
    assert v["consensus_match"] is True
    assert len(v["psbt_hex"]) > 1000
