from ctlab.lab.generate import m1_intents, materialize
from ctlab.lab.maps import walk_paytaca_v145
from ctlab.psbt.codec import decode_psbt

M1_CARDS = {(1, 1), (1, 2), (2, 1), (2, 2), (2, 3), (3, 2), (6, 6)}


def test_m1_seven_cardinalities():
    intents = m1_intents(seed=0)
    assert {(i.n_in, i.n_out) for i in intents} == M1_CARDS


def test_materialize_m1_1_1_p2pkh():
    intent = next(i for i in m1_intents(seed=0) if i.id == "M1-1-1-p2pkh")
    vec = materialize(intent)
    raw = bytes.fromhex(vec["psbt_hex"])
    assert raw[:5] == bytes.fromhex("70736274ff")
    walked = walk_paytaca_v145(raw)
    assert walked["version"] == 145
    assert decode_psbt(raw).serialize() == raw


def test_opreturn_first_role():
    intents = [i for i in m1_intents(seed=0) if i.outputs and i.outputs[0].role == "op_return"]
    assert intents
    for intent in intents:
        assert intent.expected_review()["roles"][0] == "op_return"
