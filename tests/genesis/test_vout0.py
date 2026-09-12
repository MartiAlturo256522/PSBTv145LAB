from ctlab.engine import generate


def test_vout0_token_spend_is_not_genesis():
    v = generate("VOUT0-NO-GENESIS", dialect="paytaca-145", sign="unsigned")
    assert v["consensus_match"] is True
    assert v["semantics"]["genesis_categories"] == []
    assert v["source_utxos"][0]["token"]
    # spent prev_index is 1 (dummy occupies 0)
    assert v["semantics"]["burns"] == [] or all(b.get("ft_burned", 0) == 0 for b in v["semantics"]["burns"])


def test_genesis_parent_is_genesis():
    v = generate("GEN-01", dialect="bip174-v0", sign="unsigned")
    assert v["semantics"]["genesis_categories"]
    assert v["consensus_match"] is True


def test_mixed_genesis_and_vout1_transfer():
    v = generate("VOUT0-MIXED", dialect="paytaca-145", sign="unsigned")
    assert v["consensus_match"] is True
    gens = v["semantics"]["genesis_categories"]
    assert len(gens) == 1


def test_monster01_valid_and_has_burns():
    v = generate("MONSTER-01", dialect="paytaca-145", sign="unsigned")
    assert v["consensus_match"] is True, v.get("actual_consensus_reason")
    burns = v["semantics"]["burns"]
    assert any(b.get("ft_burned", 0) == 300 for b in burns)
    assert any(b.get("nfts_dropped") for b in burns)
    assert v["semantics"]["genesis_categories"]
    assert v["psbt_hex"]


def test_generate_seed_changes_txid_but_is_deterministic():
    a = generate("GEN-04", seed=1, dialect="paytaca-145", sign="unsigned")
    b = generate("GEN-04", seed=1, dialect="paytaca-145", sign="unsigned")
    c = generate("GEN-04", seed=2, dialect="paytaca-145", sign="unsigned")
    assert a["psbt_hex"] == b["psbt_hex"]
    assert a["txid"] != c["txid"]
