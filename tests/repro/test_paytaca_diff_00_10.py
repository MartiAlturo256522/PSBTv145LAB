"""Minimal repro: Paytaca emits SEQUENCE 0x10 before NON_WITNESS_UTXO 0x00."""

from ctlab.psbt.codec import _is_js_array_index_key, _paytaca_type_order, decode_psbt
from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_vector


def test_js_array_index_keys():
    assert _is_js_array_index_key("10")
    assert _is_js_array_index_key("36")
    assert not _is_js_array_index_key("00")
    assert not _is_js_array_index_key("0e")
    assert not _is_js_array_index_key("0f")
    assert not _is_js_array_index_key("fb")


def test_input_type_order_matches_object_keys_after_sortobjectkeys():
    # localeCompare: 00,06,0e,0f,10 → Object.keys after rebuild: 10,00,06,0e,0f
    assert _paytaca_type_order(["00", "06", "0e", "0f", "10"]) == ["10", "00", "06", "0e", "0f"]
    assert _paytaca_type_order(["03", "04", "36"]) == ["36", "03", "04"]


def test_psbt02_input_map_starts_with_sequence_type_10():
    sc = next(s for s in build_catalog() if s["id"] == "PSBT-02")
    v = generate_vector(sc, dialect="paytaca-145", sign_state="unsigned")
    decoded = decode_psbt(bytes.fromhex(v["psbt_hex"]))
    types = [f"{k[0]:02x}" for k, _ in decoded.inputs[0]]
    assert types[0] == "10", types
    assert "00" in types
