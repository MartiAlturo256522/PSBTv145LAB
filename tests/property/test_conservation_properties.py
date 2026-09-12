"""P3–P8 on catalog vectors. Uses the lab consensus module — not an oracle."""

from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_vector


def test_p3_p4_tokens_do_not_appear_or_vanish_except_valid_burn_or_genesis():
    catalog = [s for s in build_catalog() if s["expected_consensus"] == "valid" and s["id"].startswith(("GEN-", "POST-", "XGEN-"))]
    for sc in catalog:
        v = generate_vector(sc, dialect=(sc.get("dialects") or ["bip174-v0"])[0], sign_state="unsigned")
        assert v["consensus_match"] is True, sc["id"]
        assert v["actual_consensus"] == "valid", (sc["id"], v.get("actual_consensus_reason"))


def test_p6_mutable_never_creates_minting_negative():
    sc = next(s for s in build_catalog() if s["id"] == "NEG-03")
    v = generate_vector(sc)
    assert v["actual_consensus"] == "invalid"
