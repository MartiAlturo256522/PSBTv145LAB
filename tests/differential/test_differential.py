from ctlab.validators.differential import differential_report
from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_vector


def test_differential_gen01():
    sc = next(s for s in build_catalog() if s["id"] == "GEN-01")
    v = generate_vector(sc)
    r = differential_report(v)
    # SKIPPED is required when libauth/BCHN/SeedCash did not run.
    # A PASS here without an independent oracle would be contamination.
    assert r["status"] in ("PASS", "FAIL", "SKIPPED", "ERROR")
    assert r["our_parser"] in ("valid", "invalid")
    if r["libauth"] == "SKIPPED" and r["bchn"] == "SKIPPED" and r["seedcash"] == "SKIPPED":
        assert r["status"] != "PASS"
