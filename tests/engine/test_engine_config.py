from ctlab.engine import generate_from_config


def test_custom_ft_genesis_paytaca_145():
    v = generate_from_config(
        {
            "id": "CUSTOM-FT",
            "dialect": "paytaca-145",
            "sign_state": "unsigned",
            "inputs": [{"kind": "genesis_parent", "key": "A", "owner": "alice", "sats": 100000}],
            "outputs": [
                {"owner": "bob", "sats": 98000, "genesis_from": 0, "token": {"nft": None, "amount": 9}}
            ],
        }
    )
    assert v["dialect"] == "paytaca-145"
    assert v["psbt_hex"]
    assert v["unsigned_tx_hex"]
    assert v["psbt_base64"]
    raw = bytes.fromhex(v["psbt_hex"])
    assert raw[:5] == b"psbt\xff"
    assert v["consensus_match"] is True
