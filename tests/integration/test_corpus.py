from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_corpus


def test_catalog_covers_required_groups():
    ids = {s["id"] for s in build_catalog()}
    for required in [
        "GEN-01", "GEN-04", "GEN-05", "GEN-08",
        "XGEN-01", "XGEN-07",
        "POST-01", "POST-08", "POST-10",
        "NEG-01", "NEG-04", "NEG-07",
        "PSBT-02", "PSBT-05",
        "SIG-01", "SIG-05",
        "SCR-01",
    ]:
        assert required in ids, required


def test_corpus_generates_and_reports_matches():
    corpus = generate_corpus()
    assert len(corpus) >= 80
    mismatches = [v for v in corpus if v.get("error")]
    # Hard errors in the generator itself are failures.
    assert mismatches == [], mismatches[:5]
    # Consensus expected vs actual: allow listing for investigation
    cons_fail = [v["id"] for v in corpus if v.get("consensus_match") is False]
    psbt_fail = [v["id"] for v in corpus if v.get("psbt_match") is False]
    # These must be empty for the laboratory to be self-consistent.
    assert cons_fail == [], cons_fail
    assert psbt_fail == [], psbt_fail
