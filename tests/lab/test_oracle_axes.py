"""Oracle axes stay separate: GEN-04 genesis-blind vs 1/2 BCH payment+change."""

from ctlab.engine import generate
from ctlab.lab.intent import InputIntent, OutputIntent, TokenIntent, TransactionIntent
from ctlab.lab.oracle import evaluate


AXES = (
    "transaction_correctness",
    "psbt_semantic_correctness",
    "review_correctness",
)


def _gen04() -> TransactionIntent:
    return TransactionIntent(
        id="GEN-04",
        description="FT genesis",
        inputs=[InputIntent(kind="genesis_parent", key="A", owner="alice", sats=100_000)],
        outputs=[
            OutputIntent(
                owner="bob",
                sats=98_000,
                role="genesis",
                token=TokenIntent(amount=1_000_000, genesis=True),
                genesis_from=0,
            )
        ],
    )


def _io12() -> TransactionIntent:
    return TransactionIntent(
        id="IO-1-2",
        description="1in/2out payment+change",
        inputs=[InputIntent(kind="bch", key="A", owner="alice", sats=50_000)],
        outputs=[
            OutputIntent(owner="bob", sats=24_000, role="payment"),
            OutputIntent(owner="alice", sats=24_000, role="change"),
        ],
    )


def test_gen04_review_fail_bch_only_tx_ok():
    intent = _gen04()
    assert intent.expected_review()["ui_route"] == "TOKEN_GENESIS"
    vec = generate("GEN-04", dialect="paytaca-145", sign="unsigned")
    finding = evaluate(intent, vector=vec)
    assert set(AXES) <= set(finding)
    assert "ok" not in finding
    a = finding["transaction_correctness"]
    b = finding["psbt_semantic_correctness"]
    c = finding["review_correctness"]
    assert a["ok"] is True
    assert a["vin_match"] and a["vout_match"] and a["sats_match"]
    assert a["tokens_match"] and a["model_matches_unsigned"]
    assert c["ok"] is False
    assert c["ui_route_actual"] == "BCH_ONLY"
    assert c["ui_route_expected"] == "TOKEN_GENESIS"
    assert c["genesis_blind"] is True
    assert c["address_amount_mismatch"] is False
    assert finding["severity"] == "HIGH"
    assert finding["class"] == "SECURITY-SENSITIVE"
    assert finding["false_positive_defense"]["signed_would_match"] is True
    assert finding["false_positive_defense"]["unsigned_agrees"] is True
    assert finding["false_positive_defense"]["only_unsupported"] is False
    assert b["naive_shift"] is True
    assert b["signed_semantics_unchanged"] is True
    assert b["tag"] == "INTEROP"


def test_gen04_from_intent_config():
    intent = _gen04()
    finding = evaluate(intent)
    assert finding["transaction_correctness"]["ok"] is True
    assert finding["review_correctness"]["genesis_blind"] is True
    assert finding["review_correctness"]["ui_route_actual"] == "BCH_ONLY"


def test_bch_1in_2out_payment_change():
    intent = _io12()
    finding = evaluate(intent)
    assert finding["transaction_correctness"]["ok"] is True
    assert finding["transaction_correctness"]["vin_match"] is True
    assert finding["transaction_correctness"]["vout_match"] is True
    assert finding["psbt_semantic_correctness"]["naive_shift"] is True
    assert finding["psbt_semantic_correctness"]["naive_last_map_dropped"] is True
    assert finding["psbt_semantic_correctness"]["signed_semantics_unchanged"] is True
    assert finding["review_correctness"]["change_listed_as_payment"] is True
    assert finding["review_correctness"]["ui_route_actual"] == "BCH_ONLY"
    assert finding["review_correctness"]["genesis_blind"] is False
    assert finding["severity"] != "CRITICAL"
    assert finding["class"] != "SECURITY-SENSITIVE"
    assert finding["class"] in ("AMBIGUOUS", "VALID", "UNSUPPORTED")
    assert "ok" not in finding
