"""Desktop preset and geometry regressions, including installed import paths."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QSpinBox
from ui.main_window import MainWindow
from ui.theme import STYLESHEET


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)

    def unexpected_warning(*args):
        pytest.fail(str(args[-1]))

    monkeypatch.setattr(QMessageBox, "warning", unexpected_warning)
    win = MainWindow()
    win.resize(1360, 800)
    win.show()
    app.processEvents()
    yield win
    win.ur_panel.stop()
    win.close()
    win.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("ident,n_in,n_out", [
    ("IO-1-1", 1, 1), ("IO-1-2", 1, 2), ("IO-2-1", 2, 1),
    ("IO-2-2", 2, 2), ("IO-2-3", 2, 3), ("IO-3-2", 3, 2),
])
def test_transfer_preset_generates_from_desktop(window, ident, n_in, n_out):
    window._select_scenario(ident, generate=True)
    window.generate()
    result = window.last_vector
    assert result["actual_consensus"] == "valid"
    assert result["actual_psbt"] == "valid"
    assert len(result["source_utxos"]) == n_in
    assert len(result["outputs"]) == n_out
    assert window.ur_panel.meta["roundtrip"]


def test_builder_edits_are_used_after_selecting_preset(window):
    window._select_scenario("IO-1-1", generate=True)
    row = window.out_host.itemAt(0).widget()
    row.findChild(QSpinBox).setValue(47000)
    assert window.state.builder_dirty
    window.generate()
    assert window.last_vector["outputs"][0]["value_sats"] == 47000


@pytest.mark.parametrize("size", [(1280, 720), (1360, 800), (1440, 860)])
def test_builder_results_and_qr_visible_together(window, size):
    window.resize(*size)
    window._select_scenario("IO-1-2", generate=True)
    QApplication.processEvents()
    assert window.width() / window.height() > 1.5
    for widget in (window.scenario_tree, window.in_box, window.out_box,
                   window.val_panel, window.identity, window.result_tabs, window.ur_panel.qr):
        assert widget.isVisible()
        top_left = widget.mapTo(window, widget.rect().topLeft())
        bottom_right = widget.mapTo(window, widget.rect().bottomRight())
        assert window.rect().contains(top_left)
        assert window.rect().contains(bottom_right)
    for layout in (window.in_host, window.out_host):
        card = layout.itemAt(0).widget()
        assert card.height() >= card.sizeHint().height()
        assert card.findChild(QSpinBox).height() >= 20
    assert window.ur_panel.qr.width() >= 150
    assert window.ur_panel.qr.height() >= 150


def test_transfer_presets_without_repository_tools(tmp_path):
    src = Path(__file__).resolve().parents[2] / "src"
    script = f"""
import json, sys
sys.path.insert(0, {str(src)!r})
from application.psbt_service import validate_and_generate
from application.presets import SCENARIOS
results = [validate_and_generate(catalog_id=s.id) for s in SCENARIOS[:6]]
assert not any(name == 'tools' or name.startswith('tools.') for name in sys.modules)
print(json.dumps([r['actual_psbt'] for r in results]))
"""
    result = subprocess.run([sys.executable, "-I", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["valid"] * 6
