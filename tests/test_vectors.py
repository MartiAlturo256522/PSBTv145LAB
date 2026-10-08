import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("lab_test_vectors", Path(__file__).with_name("vectors.py"))
vectors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vectors)


@pytest.mark.parametrize("definition", vectors.load_vectors(), ids=lambda d: d["id"])
def test_manifest_vector(definition):
    result = vectors.generate_vectors([definition["id"]])[0]
    assert result.get("error") is None
    assert result["consensus_match"]
    assert result["psbt_match"]


def test_extract_selected_vector(tmp_path):
    vectors.extract_vectors(tmp_path, ["GEN-04"])
    fixtures = list(tmp_path.rglob("vector.json"))
    assert len(fixtures) == 1
    import json
    result = json.loads(fixtures[0].read_text())
    assert result["dialect"] == "paytaca-145"
    assert result["psbt_hex"].startswith("70736274ff")


def test_unknown_vector_is_rejected():
    with pytest.raises(ValueError, match="unknown vector ids"):
        vectors.generate_vectors(["DOES-NOT-EXIST"])
