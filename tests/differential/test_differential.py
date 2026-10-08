from core.validators.differential import differential_report
from core.vectors.catalog import build_catalog
from core.vectors.generator import generate_vector


def test_differential_gen01():
    sc = next(s for s in build_catalog() if s["id"] == "GEN-01")
    v = generate_vector(sc)
    r = differential_report(v)
    # SKIPPED is required when external BCHN/SeedCash did not run.
    # A PASS here without an independent oracle would be contamination.
    assert r["status"] in ("PASS", "FAIL", "SKIPPED", "ERROR")
    assert r["our_parser"] in ("valid", "invalid")
    if r["bchn"] == "SKIPPED" and r["seedcash"] == "SKIPPED":
        assert r["status"] != "PASS"


def test_python_wire_reference_reports_its_own_result():
    from core.engine import generate

    report = differential_report(generate("GEN-04", dialect="paytaca-145"))
    assert report["python_reference"] == "PASS"
    assert report["python_reference_detail"]["source"] == "python-wire-reference"
    if report["seedcash"] == "SKIPPED":
        assert report["status"] == "SKIPPED"
