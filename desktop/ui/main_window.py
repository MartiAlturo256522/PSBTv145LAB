"""SeedCash PSBT Lab main window. UI only — engine via psbt_service."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.application.builder_model import BuilderState, InputUI, OutputUI, TokenUI
from desktop.application.presets import CATALOG_PRESETS, builder_from_catalog, genesis_nft, simple_bch
from desktop.application.psbt_service import (
    catalog,
    inspect,
    random_case,
    save_fixture,
    status_line,
    validate_and_generate,
)
from desktop.ui.theme import STYLESHEET
from desktop.ui.ur_widget import UrPanel

OWNERS = ["alice", "bob", "carol", "dave"]
KINDS_IN = ["genesis_parent", "token", "bch"]
TOKEN_KINDS = ["none", "ft", "nft", "hybrid", "authority"]
NFT_CAPS = ["none", "immutable", "mutable", "minting"]
CAT_MODES = ["auto", "group", "hex"]
SCRIPTS = ["p2pkh", "p2sh20", "p2sh32"]


def _combo(items, current=""):
    w = QComboBox()
    w.addItems(items)
    if current in items:
        w.setCurrentText(current)
    return w


class TokenEditor(QWidget):
    def __init__(self, tok: TokenUI):
        super().__init__()
        self.tok = tok
        f = QFormLayout(self)
        f.setContentsMargins(0, 0, 0, 0)
        f.setSpacing(4)
        self.kind = _combo(TOKEN_KINDS, tok.kind)
        self.cat_mode = _combo(CAT_MODES, tok.category_mode)
        self.group = QLineEdit(tok.category_group)
        self.hex = QLineEdit(tok.category_hex)
        self.hex.setPlaceholderText("64-char category hex (optional)")
        self.ft = QSpinBox()
        self.ft.setRange(0, 2**31 - 1)
        self.ft.setValue(int(tok.ft_amount or 0))
        self.nft = _combo(NFT_CAPS, tok.nft)
        self.commit = QLineEdit(tok.commitment)
        self.sum = QLabel(tok.summary())
        self.sum.setObjectName("muted")
        f.addRow("Token", self.kind)
        f.addRow("Category", self.cat_mode)
        f.addRow("Group", self.group)
        f.addRow("Category hex", self.hex)
        f.addRow("FT amount", self.ft)
        f.addRow("NFT", self.nft)
        f.addRow("Commitment", self.commit)
        f.addRow("", self.sum)
        for w in (self.kind, self.cat_mode, self.nft, self.ft, self.group, self.commit, self.hex):
            if hasattr(w, "currentTextChanged"):
                w.currentTextChanged.connect(self._sync)
            elif hasattr(w, "valueChanged"):
                w.valueChanged.connect(self._sync)
            else:
                w.textChanged.connect(self._sync)

    def _sync(self, *_):
        self.tok.kind = self.kind.currentText()
        self.tok.category_mode = self.cat_mode.currentText()
        self.tok.category_group = self.group.text().strip() or "A"
        self.tok.category_hex = self.hex.text().strip()
        self.tok.ft_amount = int(self.ft.value())
        self.tok.nft = self.nft.currentText()
        self.tok.commitment = self.commit.text()
        self.sum.setText(self.tok.summary())


class IOBox(QGroupBox):
    def __init__(self, title: str):
        super().__init__(title)
        self.body = QVBoxLayout()
        self.setLayout(self.body)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SeedCash PSBT Lab")
        self.resize(1280, 820)
        self.state = BuilderState()
        self.last_vector: dict | None = None
        self._log_lines: list[str] = []
        self._build()
        self._refresh_status()
        self._reload_inputs()
        self._reload_outputs()
        self._load_fixtures()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 8, 12, 8)
        brand = QLabel("SEEDCASH PSBT LAB")
        brand.setObjectName("brand")
        lab = QLabel("SYNTHETIC / LABORATORY  ·  not broadcastable")
        lab.setObjectName("gold")
        self.ready = QLabel("● Ready")
        self.ready.setObjectName("gold")
        hl.addWidget(brand)
        hl.addStretch()
        hl.addWidget(lab)
        hl.addWidget(self.ready)
        outer.addWidget(header)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setMaximumWidth(240)
        sl = QVBoxLayout(side)
        sl.addWidget(QLabel("WORKSPACE"))
        self.nav = QListWidget()
        for name in ("New PSBT", "Presets", "Fixtures", "JSON", "Inspector"):
            self.nav.addItem(name)
        self.nav.setCurrentRow(0)
        self.nav.currentTextChanged.connect(self._nav)
        sl.addWidget(self.nav)
        sl.addWidget(QLabel("PRESETS"))
        self.preset_list = QListWidget()
        for label, _cid in CATALOG_PRESETS:
            self.preset_list.addItem(label)
        self.preset_list.itemClicked.connect(self._apply_preset)
        sl.addWidget(self.preset_list, 1)
        gen = QPushButton("GENERATE PSBT")
        gen.setObjectName("primary")
        gen.clicked.connect(self.generate)
        sl.addWidget(gen)
        copyb = QPushButton("Copy PSBT for SeedCash")
        copyb.clicked.connect(self.copy_seedcash)
        sl.addWidget(copyb)
        copyur = QPushButton("Copy UR for SeedCash")
        copyur.clicked.connect(self.copy_ur_seedcash)
        sl.addWidget(copyur)
        valb = QPushButton("Validate")
        valb.clicked.connect(self.validate_only)
        sl.addWidget(valb)
        newb = QPushButton("Reset / New PSBT")
        newb.clicked.connect(self.new_psbt)
        sl.addWidget(newb)
        openb = QPushButton("Open PSBT…")
        openb.clicked.connect(self.open_psbt)
        sl.addWidget(openb)
        split.addWidget(side)

        right = QSplitter(Qt.Vertical)
        split.addWidget(right)
        split.setStretchFactor(1, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._builder_tab(), "Builder")
        self.tabs.addTab(self._presets_tab(), "Presets")
        self.tabs.addTab(self._fixtures_tab(), "Fixtures")
        self.tabs.addTab(self._json_tab(), "JSON")
        self.tabs.addTab(self._inspect_tab(), "Inspector")
        right.addWidget(self.tabs)

        out = QWidget()
        ol = QVBoxLayout(out)
        ol.setContentsMargins(8, 4, 8, 8)
        row = QHBoxLayout()
        row.addWidget(QLabel("OUTPUT"))
        self.val_lbl = QLabel("Validation: —")
        self.val_lbl.setObjectName("muted")
        row.addStretch()
        row.addWidget(self.val_lbl)
        ol.addLayout(row)
        self.result_tabs = QTabWidget()
        self.out_b64 = QPlainTextEdit()
        self.out_hex = QPlainTextEdit()
        self.out_tx = QPlainTextEdit()
        self.out_json = QPlainTextEdit()
        for w in (self.out_b64, self.out_hex, self.out_tx, self.out_json):
            w.setReadOnly(True)
            w.setFont(QFont("Consolas", 10))
        self.ur_panel = UrPanel(log_fn=self.log)
        self.result_tabs.addTab(self.out_b64, "PSBT BASE64")
        self.result_tabs.addTab(self.out_hex, "PSBT HEX")
        self.result_tabs.addTab(self.out_tx, "UNSIGNED TX")
        self.result_tabs.addTab(self.out_json, "JSON")
        self.result_tabs.addTab(self.ur_panel, "UR / QR")
        ol.addWidget(self.result_tabs)
        btns = QHBoxLayout()
        for text, fn in (
            ("Copy", self.copy_current),
            ("Save…", self.save_current),
            ("Export fixture", self.export_fix),
        ):
            b = QPushButton(text)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch()
        ol.addLayout(btns)
        right.addWidget(out)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)

        self.status = self.statusBar()
        act = QAction("Generate", self)
        act.setShortcut(QKeySequence("Ctrl+Return"))
        act.triggered.connect(self.generate)
        self.addAction(act)
        save = QAction("Save fixture", self)
        save.setShortcut(QKeySequence("Ctrl+S"))
        save.triggered.connect(self.export_fix)
        self.addAction(save)
        dbg = QAction("Debug Log", self)
        dbg.setShortcut(QKeySequence("Ctrl+L"))
        dbg.triggered.connect(self.toggle_log)
        self.addAction(dbg)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_dock = QDockWidget("Debug log", self)
        self.log_dock.setWidget(self.log_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

    def _builder_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        form = QHBoxLayout()
        self.dialect = _combo(["paytaca-145", "bip174-v0"], "paytaca-145")
        self.sign = _combo(["unsigned", "signed"], "unsigned")
        self.seed = QSpinBox()
        self.seed.setRange(0, 2**31 - 1)
        self.seed.setSpecialValueText("none")
        self.synth = QRadioButton("Synthetic UTXOs")
        self.synth.setChecked(True)
        warn = QLabel("Synthetic UTXOs are laboratory fixtures and do not exist on-chain.")
        warn.setObjectName("muted")
        form.addWidget(QLabel("Dialect"))
        form.addWidget(self.dialect)
        form.addWidget(QLabel("Sign"))
        form.addWidget(self.sign)
        form.addWidget(QLabel("Seed"))
        form.addWidget(self.seed)
        form.addWidget(self.synth)
        form.addStretch()
        v.addLayout(form)
        v.addWidget(warn)

        rnd = QHBoxLayout()
        self.complexity = _combo(["Simple", "Medium", "Complex", "Monster"], "Simple")
        rb = QPushButton("Generate random valid case")
        rb.clicked.connect(self.random_valid)
        rnd.addWidget(QLabel("Random"))
        rnd.addWidget(self.complexity)
        rnd.addWidget(rb)
        rnd.addStretch()
        v.addLayout(rnd)

        io = QSplitter(Qt.Horizontal)
        self.in_box = IOBox("INPUTS")
        add_i = QPushButton("+ Add input")
        add_i.clicked.connect(self.add_input)
        self.in_box.body.addWidget(add_i)
        self.in_host = QVBoxLayout()
        wrap_i = QWidget()
        wrap_i.setLayout(self.in_host)
        sc_i = QScrollArea()
        sc_i.setWidgetResizable(True)
        sc_i.setWidget(wrap_i)
        self.in_box.body.addWidget(sc_i)
        self.out_box = IOBox("OUTPUTS")
        add_o = QPushButton("+ Add output")
        add_o.clicked.connect(self.add_output)
        self.out_box.body.addWidget(add_o)
        self.out_host = QVBoxLayout()
        wrap_o = QWidget()
        wrap_o.setLayout(self.out_host)
        sc_o = QScrollArea()
        sc_o.setWidgetResizable(True)
        sc_o.setWidget(wrap_o)
        self.out_box.body.addWidget(sc_o)
        io.addWidget(self.in_box)
        io.addWidget(self.out_box)
        v.addWidget(io, 1)

        self.val_panel = QPlainTextEdit()
        self.val_panel.setReadOnly(True)
        self.val_panel.setMaximumHeight(90)
        self.val_panel.setPlaceholderText("VALIDATION — engine is authoritative")
        v.addWidget(self.val_panel)
        return w

    def _json_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("Exact engine configuration (frozen generate())"))
        self.json_edit = QPlainTextEdit()
        self.json_edit.setFont(QFont("Consolas", 10))
        v.addWidget(self.json_edit)
        row = QHBoxLayout()
        a = QPushButton("Sync from builder")
        a.clicked.connect(self.sync_json)
        b = QPushButton("Validate + Generate from JSON")
        b.setObjectName("primary")
        b.clicked.connect(self.generate_json)
        row.addWidget(a)
        row.addWidget(b)
        row.addStretch()
        v.addLayout(row)
        return w

    def _presets_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("Catalog presets — click to load into builder and generate via frozen engine."))
        self.preset_tree = QListWidget()
        for label, cid in CATALOG_PRESETS:
            self.preset_tree.addItem(f"{label}  →  {cid}")
        self.preset_tree.itemClicked.connect(self._apply_preset_row)
        v.addWidget(self.preset_tree)
        hint = QLabel("Same source as engine catalog. Builder fields update, then engine.generate() runs.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        v.addWidget(hint)
        return w

    def _fixtures_tab(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        self.fix_list = QListWidget()
        self.fix_list.itemClicked.connect(self._open_fixture)
        h.addWidget(self.fix_list, 1)
        hint = QLabel("Double-click to generate via the frozen engine.\nRead-only load of catalog scenarios.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        h.addWidget(hint, 1)
        return w

    def _inspect_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("decode_psbt of last generated blob (frozen decoder)"))
        self.inspect_view = QPlainTextEdit()
        self.inspect_view.setReadOnly(True)
        self.inspect_view.setFont(QFont("Consolas", 10))
        v.addWidget(self.inspect_view)
        return w

    def _nav(self, name: str):
        if name == "New PSBT":
            self.new_psbt()
            self.tabs.setCurrentIndex(0)
            return
        idx = {"Presets": 1, "Fixtures": 2, "JSON": 3, "Inspector": 4}.get(name)
        if idx is not None:
            self.tabs.setCurrentIndex(idx)

    def _sync_state_from_widgets(self):
        self.state.dialect = self.dialect.currentText()
        self.state.sign = self.sign.currentText()
        sv = self.seed.value()
        self.state.seed = None if sv == 0 else sv
        self.state.synthetic = self.synth.isChecked()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _reload_inputs(self):
        self._clear_layout(self.in_host)
        for i, inp in enumerate(self.state.inputs):
            g = QGroupBox(f"INPUT #{i}  {inp.kind}")
            f = QFormLayout(g)
            kind = _combo(KINDS_IN, inp.kind)
            key = QLineEdit(inp.key)
            owner = _combo(OWNERS, inp.owner)
            vout = QSpinBox()
            vout.setRange(0, 32)
            vout.setValue(inp.vout)
            sats = QSpinBox()
            sats.setRange(0, 2_100_000_000)
            sats.setValue(inp.sats)
            tok = TokenEditor(inp.token)
            f.addRow("Kind", kind)
            f.addRow("Key", key)
            f.addRow("Owner", owner)
            f.addRow("VOUT", vout)
            f.addRow("Sats", sats)
            f.addRow(tok)
            row = QHBoxLayout()
            dup = QPushButton("Duplicate")
            rm = QPushButton("Remove")
            dup.clicked.connect(lambda _, n=i: self._dup_in(n))
            rm.clicked.connect(lambda _, n=i: self._rm_in(n))
            row.addWidget(dup)
            row.addWidget(rm)
            f.addRow(row)

            def bind(inp=inp, kind=kind, key=key, owner=owner, vout=vout, sats=sats):
                kind.currentTextChanged.connect(lambda t: setattr(inp, "kind", t))
                key.textChanged.connect(lambda t: setattr(inp, "key", t))
                owner.currentTextChanged.connect(lambda t: setattr(inp, "owner", t))
                vout.valueChanged.connect(lambda n: setattr(inp, "vout", n))
                sats.valueChanged.connect(lambda n: setattr(inp, "sats", n))

            bind()
            self.in_host.addWidget(g)
        self.in_host.addStretch()

    def _reload_outputs(self):
        self._clear_layout(self.out_host)
        for i, out in enumerate(self.state.outputs):
            g = QGroupBox(f"OUTPUT #{i}")
            f = QFormLayout(g)
            owner = _combo(OWNERS, out.owner)
            sats = QSpinBox()
            sats.setRange(0, 2_100_000_000)
            sats.setValue(out.sats)
            script = _combo(SCRIPTS, out.script)
            tok = TokenEditor(out.token)
            f.addRow("Owner", owner)
            f.addRow("Sats", sats)
            f.addRow("Script", script)
            f.addRow(tok)
            row = QHBoxLayout()
            dup = QPushButton("Duplicate")
            rm = QPushButton("Remove")
            dup.clicked.connect(lambda _, n=i: self._dup_out(n))
            rm.clicked.connect(lambda _, n=i: self._rm_out(n))
            row.addWidget(dup)
            row.addWidget(rm)
            f.addRow(row)

            def bind(out=out, owner=owner, sats=sats, script=script):
                owner.currentTextChanged.connect(lambda t: setattr(out, "owner", t))
                sats.valueChanged.connect(lambda n: setattr(out, "sats", n))
                script.currentTextChanged.connect(lambda t: setattr(out, "script", t))

            bind()
            self.out_host.addWidget(g)
        self.out_host.addStretch()

    def add_input(self):
        n = len(self.state.inputs)
        self.state.inputs.append(InputUI(key=f"I{n}", kind="token"))
        self._reload_inputs()

    def add_output(self):
        self.state.outputs.append(OutputUI())
        self._reload_outputs()

    def _dup_in(self, n):
        src = self.state.inputs[n]
        self.state.inputs.insert(n + 1, InputUI(key=src.key + "x", kind=src.kind, owner=src.owner, sats=src.sats, token=TokenUI(**src.token.__dict__)))
        self._reload_inputs()

    def _rm_in(self, n):
        if len(self.state.inputs) > 1:
            self.state.inputs.pop(n)
            self._reload_inputs()

    def _dup_out(self, n):
        src = self.state.outputs[n]
        self.state.outputs.insert(n + 1, OutputUI(owner=src.owner, sats=src.sats, token=TokenUI(**src.token.__dict__)))
        self._reload_outputs()

    def _rm_out(self, n):
        if len(self.state.outputs) > 1:
            self.state.outputs.pop(n)
            self._reload_outputs()

    def log(self, msg: str):
        from datetime import datetime

        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self._log_lines.append(line)
        self.log_view.appendPlainText(line)

    def toggle_log(self):
        self.log_dock.setVisible(not self.log_dock.isVisible())

    def new_psbt(self):
        self.state = BuilderState()
        self.last_vector = None
        self._reload_inputs()
        self._reload_outputs()
        self.out_b64.clear()
        self.out_hex.clear()
        self.out_tx.clear()
        self.out_json.clear()
        self.val_panel.setPlainText("CONFIGURING — synthetic laboratory transaction")
        self.ready.setText("● Ready")
        self.log("New PSBT / builder reset")

    def open_psbt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PSBT", "", "PSBT (*.psbt *.hex *.base64 *.txt);;All (*)")
        if not path:
            return
        raw = Path(path).read_bytes()
        text = raw.decode("ascii", "ignore").strip()
        try:
            hx = bytes.fromhex(text).hex()
        except ValueError:
            import base64

            hx = base64.b64decode(text).hex()
        self.out_hex.setPlainText(hx)
        self.last_vector = {"psbt_hex": hx, "psbt_base64": __import__("base64").b64encode(bytes.fromhex(hx)).decode()}
        self.inspect_view.setPlainText(json.dumps(inspect(self.last_vector), indent=2))
        self.log(f"Opened PSBT {path} ({len(hx)//2} bytes)")
        self.tabs.setCurrentIndex(4)

    def validate_only(self):
        self._sync_state_from_widgets()
        self._run_engine(state=self.state)

    def _apply_preset_row(self, item: QListWidgetItem):
        text = item.text()
        cid = text.split("→")[-1].strip() if "→" in text else None
        if not cid:
            cid = next((c for l, c in CATALOG_PRESETS if l == text), None)
        if cid:
            self._load_preset(cid)

    def _apply_preset(self, item: QListWidgetItem):
        label = item.text()
        cid = next((c for l, c in CATALOG_PRESETS if l == label), None)
        if cid:
            self._load_preset(cid)

    def _load_preset(self, cid: str):
        try:
            self.state = builder_from_catalog(cid)
            self.dialect.setCurrentText(self.state.dialect if self.state.dialect in ("paytaca-145", "bip174-v0") else "paytaca-145")
            self._reload_inputs()
            self._reload_outputs()
            self.sync_json()
            self.log(f"Loaded preset {cid} into builder ({len(self.state.inputs)} in / {len(self.state.outputs)} out)")
            self.tabs.setCurrentIndex(0)
            self._run_engine(catalog_id=cid)
        except Exception as e:
            QMessageBox.warning(self, "Preset", f"Could not load {cid}\n\n{type(e).__name__}: {e}")
            self.log(f"Preset {cid} failed: {e}")

    def _load_fixtures(self):
        self.fix_list.clear()
        for row in catalog():
            self.fix_list.addItem(f"{row['id']}  [{row['group']}]  {row['title']}")

    def _open_fixture(self, item: QListWidgetItem):
        ident = item.text().split()[0]
        self._run_engine(catalog_id=ident)

    def sync_json(self):
        self._sync_state_from_widgets()
        self.json_edit.setPlainText(json.dumps(self.state.to_engine_config(), indent=2))

    def generate_json(self):
        try:
            cfg = json.loads(self.json_edit.toPlainText())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON", str(e))
            return
        self._run_engine(raw=cfg)

    def generate(self):
        self._sync_state_from_widgets()
        self._run_engine(state=self.state)

    def random_valid(self):
        seed = self.seed.value() or 1
        vec = random_case(self.complexity.currentText(), seed)
        self._show_vector(vec)

    def _run_engine(self, state=None, catalog_id=None, raw=None):
        try:
            vec = validate_and_generate(
                state,
                catalog_id=catalog_id,
                raw_config=raw,
                seed=self.state.seed,
            )
        except Exception as e:
            msg = f"Could not generate PSBT\n\nReason:\n{type(e).__name__}: {e}"
            self.val_panel.setPlainText(msg)
            self.val_lbl.setText("Validation: FAIL")
            self.ready.setText("● Error")
            self.log(msg.replace("\n", " "))
            QMessageBox.warning(self, "Generate", msg)
            return
        self._show_vector(vec)

    def _show_vector(self, vec: dict):
        self.last_vector = vec
        ok = bool(vec.get("consensus_match"))
        reason = vec.get("actual_consensus_reason") or ""
        lines = [
            f"{'✓' if ok else '✕'} engine consensus={vec.get('actual_consensus')} psbt={vec.get('actual_psbt')}",
            f"dialect={vec.get('dialect')}  inputs/outputs from unsigned tx",
            f"genesis={vec.get('semantics', {}).get('genesis_categories')}",
            f"burns={vec.get('semantics', {}).get('burns')}",
            reason,
        ]
        self.val_panel.setPlainText("\n".join(str(x) for x in lines if x))
        self.val_lbl.setText("READY TO GENERATE" if ok else "INVALID / see panel")
        self.ready.setText("● Generated" if vec.get("psbt_base64") else "● Ready")
        self.out_b64.setPlainText(vec.get("psbt_base64") or "")
        self.out_hex.setPlainText(vec.get("psbt_hex") or "")
        self.out_tx.setPlainText((vec.get("txid") or "") + "\n" + (vec.get("unsigned_tx_hex") or ""))
        slim = {k: vec.get(k) for k in ("id", "txid", "dialect", "semantics", "source_utxos", "outputs", "previous_txs")}
        self.out_json.setPlainText(json.dumps(slim, indent=2))
        try:
            self.inspect_view.setPlainText(json.dumps(inspect(vec), indent=2))
        except Exception as e:
            self.inspect_view.setPlainText(str(e))
        hx = vec.get("psbt_hex") or ""
        if hx:
            try:
                self.ur_panel.encode_from_psbt(hx)
            except Exception as e:
                self.log(f"UR encode failed: {e}")
        n = len(hx) // 2
        self.log(
            f"Generated {vec.get('id')}  {n} bytes  consensus={vec.get('actual_consensus')}  "
            f"psbt={vec.get('actual_psbt')}"
        )

    def copy_ur_seedcash(self):
        self.ur_panel.copy_seedcash()
        self.status.showMessage("UR copied for SeedCash", 4000)

    def _current_text(self) -> str:
        w = self.result_tabs.currentWidget()
        return w.toPlainText() if w else ""

    def copy_current(self):
        QApplication.clipboard().setText(self._current_text())

    def copy_seedcash(self):
        if self.last_vector and self.last_vector.get("psbt_base64"):
            QApplication.clipboard().setText(self.last_vector["psbt_base64"])
            self.status.showMessage("Base64 copied for SeedCash", 4000)

    def save_current(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save", "psbt.txt")
        if path:
            Path(path).write_text(self._current_text(), encoding="utf-8")

    def export_fix(self):
        if not self.last_vector:
            return
        dest = QFileDialog.getExistingDirectory(self, "Fixture folder")
        if not dest:
            return
        save_fixture(self.last_vector, Path(dest))
        ur_dir = Path(dest) / "ur"
        ur_dir.mkdir(exist_ok=True)
        parts = self.ur_panel.current_parts()
        for i, part in enumerate(parts, 1):
            (ur_dir / f"frame-{i:03d}.txt").write_text(part + "\n", encoding="utf-8")
        (ur_dir / "manifest.json").write_text(
            json.dumps({"type": "crypto-psbt", "frames": len(parts), "compat": "same-libraries"}, indent=2),
            encoding="utf-8",
        )
        self.log(f"Exported fixture + {len(parts)} UR frames to {dest}")
        self.status.showMessage(f"Exported to {dest}", 5000)

    def _refresh_status(self):
        st = status_line()
        self.status.showMessage(
            f"Engine: {st['engine']} {st['version']}  |  tests: {st['tests']}  |  "
            f"{st['dialect']}  |  {st['network']}  |  Mode: {st['mode']}"
        )


def run():
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    return app.exec()
