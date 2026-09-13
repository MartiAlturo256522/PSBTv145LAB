"""Preset load, UR roundtrip, smoke. Does not touch src/ctlab."""

from desktop.adapter.engine_adapter import generate_psbt
from desktop.application.presets import CATALOG_PRESETS, builder_from_catalog
from desktop.application.psbt_service import random_case, validate_and_generate
from desktop.application.ur_service import decode_ur_parts, encode_ur
from ctlab.engine import generate


def test_preset_loads():
    st = builder_from_catalog("MONSTER-01")
    assert len(st.inputs) >= 4
    assert len(st.outputs) >= 4


def test_preset_updates_builder():
    st = builder_from_catalog("GEN-04")
    assert st.inputs[0].kind == "genesis_parent"
    assert st.outputs[0].token.kind in ("ft", "hybrid")


def test_generate_button_matches_engine():
    st = builder_from_catalog("GEN-04")
    via_ui = validate_and_generate(catalog_id="GEN-04")
    via_engine = generate("GEN-04", dialect="paytaca-145", sign="unsigned")
    assert via_ui["psbt_hex"] == via_engine["psbt_hex"]
    cfg = st.to_engine_config()
    assert cfg["inputs"]


def test_all_catalog_presets_generate():
    failed = []
    for label, cid in CATALOG_PRESETS:
        try:
            v = validate_and_generate(catalog_id=cid)
            if not v.get("psbt_hex"):
                failed.append((label, cid, "no hex"))
            elif v.get("dialect") != "paytaca-145":
                failed.append((label, cid, v.get("dialect")))
        except Exception as e:
            failed.append((label, cid, str(e)))
    assert not failed, failed


def test_json_apply():
    st = builder_from_catalog("GEN-01")
    cfg = st.to_engine_config()
    v = validate_and_generate(raw_config=cfg)
    assert v.get("psbt_hex")


def test_random_seed():
    a = random_case("Simple", 7)
    b = random_case("Simple", 7)
    assert a["psbt_hex"] == b["psbt_hex"]
    c = random_case("Simple", 8)
    assert a["id"] == b["id"]


def test_ur_multipart_and_roundtrip():
    v = generate_psbt("GEN-04", dialect="paytaca-145")
    ur = encode_ur(v["psbt_hex"], "High")
    assert ur["type"] == "crypto-psbt"
    assert ur["roundtrip"] is True
    assert ur["fragmentsLength"] >= 1
    hx = decode_ur_parts(ur["parts"])
    assert hx == v["psbt_hex"]


def test_ur_density_changes_fragments():
    v = generate_psbt("MONSTER-01", dialect="paytaca-145")
    low = encode_ur(v["psbt_hex"], "Low")
    high = encode_ur(v["psbt_hex"], "Maximum")
    assert low["maxFragment"] < high["maxFragment"]
    assert low["roundtrip"] and high["roundtrip"]


def test_qr_frame_generation():
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    from desktop.ui.ur_widget import _qr_pixmap

    pix = _qr_pixmap("ur:crypto-psbt/test")
    assert not pix.isNull()
    assert app is not None


def test_speed_control_values():
    from desktop.application.ur_service import SPEED_MS

    assert SPEED_MS["Slow"] > SPEED_MS["Fast"]
