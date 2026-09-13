"""SeedCash PSBT Lab main window.

Format (BCH PSBT v145) is a lab invariant. Scenarios pick the transaction,
not the encoding. The UI must never present a semantic preset as a dialect.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.application.builder_model import BuilderState, InputUI, OutputUI, TokenUI
from desktop.application.identity import fixture_identity
from desktop.application.lab_contract import (
    DEFAULT_SCENARIO_ID,
    FORMAT_LABEL,
    IMPLEMENTED_MODES,
    LabContext,
    MODES,
    REFERENCE_LABEL,
)
from desktop.application.presets import SCENARIOS, builder_from_catalog, get_scenario
from desktop.application.psbt_service import (
    catalog,
    compare_encodings,
    inspect,
    random_case,
    save_fixture,
    status_line,
    validate_and_generate,
)
from desktop.ui.identity_strip import IdentityStrip
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
        self.setWindowTitle("SeedCash PSBT Lab — BCH PSBT v145")
        self.resize(1320, 860)
        self.ctx = LabContext()
        self.state = BuilderState()
        self.last_vector: dict | None = None
        self._log_lines: list[str] = []
        self._build()
        self._refresh_status()
        self._reload_inputs()
        self._reload_outputs()
        self._load_fixtures()
        self._select_scenario(DEFAULT_SCENARIO_ID, generate=False)
        self._update_summaries()

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
        fmt = QLabel("BCH PSBT v145")
        fmt.setObjectName("formatBadge")
        lab = QLabel("Paytaca JS 9c338d2  ·  SYNTHETIC  ·  not broadcastable")
        lab.setObjectName("gold")
        self.ready = QLabel("● Ready")
        self.ready.setObjectName("gold")
        hl.addWidget(brand)
        hl.addWidget(fmt)
        hl.addStretch()
        hl.addWidget(lab)
        hl.addWidget(self.ready)
        outer.addWidget(header)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setMinimumWidth(250)
        side.setMaximumWidth(300)
        sl = QVBoxLayout(side)

        inv = QFrame()
        inv.setObjectName("invariant")
        iv = QVBoxLayout(inv)
        iv.setContentsMargins(8, 6, 8, 6)
        s1 = QLabel("FORMAT")
        s1.setObjectName("section")
        f1 = QLabel(FORMAT_LABEL)
        f1.setObjectName("formatBadge")
        s2 = QLabel("REFERENCE")
        s2.setObjectName("section")
        f2 = QLabel(REFERENCE_LABEL)
        f2.setObjectName("gold")
        f2.setWordWrap(True)
        iv.addWidget(s1)
        iv.addWidget(f1)
        iv.addWidget(s2)
        iv.addWidget(f2)
        sl.addWidget(inv)

        sl.addWidget(self._section("MODE"))
        self.mode = _combo(list(MODES), "generate")
        self.mode.currentTextChanged.connect(self._mode_changed)
        sl.addWidget(self.mode)
        mode_hint = QLabel("generate encodes v145. compare adds BIP-174 only as an interop check.")
        mode_hint.setObjectName("muted")
        mode_hint.setWordWrap(True)
        sl.addWidget(mode_hint)

        sl.addWidget(self._section("SCENARIO"))
        self.scenario_tree = QTreeWidget()
        self.scenario_tree.setHeaderHidden(True)
        self.scenario_tree.setIndentation(12)
        self._fill_scenarios()
        self.scenario_tree.itemClicked.connect(self._scenario_clicked)
        sl.addWidget(self.scenario_tree, 1)

        meta = QFormLayout()
        self.sum_in = QLabel("1")
        self.sum_out = QLabel("1")
        self.sum_tok = QLabel("none")
        self.seed = QSpinBox()
        self.seed.setRange(0, 2**31 - 1)
        self.seed.setSpecialValueText("deterministic")
        meta.addRow("INPUTS", self.sum_in)
        meta.addRow("OUTPUTS", self.sum_out)
        meta.addRow("TOKENS", self.sum_tok)
        meta.addRow("SEED", self.seed)
        sl.addLayout(meta)

        gen = QPushButton("GENERATE")
        gen.setObjectName("primary")
        gen.clicked.connect(self.generate)
        sl.addWidget(gen)
        copyb = QPushButton("Copy PSBT for SeedCash")
        copyb.clicked.connect(self.copy_seedcash)
        sl.addWidget(copyb)
        copyur = QPushButton("Copy UR for SeedCash")
        copyur.clicked.connect(self.copy_ur_seedcash)
        sl.addWidget(copyur)
        newb = QPushButton("Reset / Simple transfer")
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
        self.tabs.addTab(self._json_tab(), "JSON")
        self.tabs.addTab(self._fixtures_tab(), "Catalog")
        self.tabs.addTab(self._inspect_tab(), "Inspector")
        self.tabs.addTab(self._compare_tab(), "Compare")
        right.addWidget(self.tabs)

        out = QWidget()
        ol = QVBoxLayout(out)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)
        self.identity = IdentityStrip()
        ol.addWidget(self.identity)

        artifacts = QWidget()
        al = QVBoxLayout(artifacts)
        al.setContentsMargins(8, 4, 8, 8)
        row = QHBoxLayout()
        row.addWidget(QLabel("ARTIFACTS  ·  encoded as BCH PSBT v145"))
        self.val_lbl = QLabel("Validation: —")
        self.val_lbl.setObjectName("muted")
        row.addStretch()
        row.addWidget(self.val_lbl)
        al.addLayout(row)
        self.result_tabs = QTabWidget()
        self.out_b64 = QPlainTextEdit()
        self.out_hex = QPlainTextEdit()
        self.out_tx = QPlainTextEdit()
        self.out_json = QPlainTextEdit()
        for w in (self.out_b64, self.out_hex, self.out_tx, self.out_json):
            w.setReadOnly(True)
            w.setFont(QFont("Consolas", 10))
        self.ur_panel = UrPanel(log_fn=self.log)
        self.result_tabs.addTab(self.out_b64, "PSBT v145 BASE64")
        self.result_tabs.addTab(self.out_hex, "PSBT v145 HEX")
        self.result_tabs.addTab(self.out_tx, "UNSIGNED TX")
        self.result_tabs.addTab(self.out_json, "JSON semantic")
        self.result_tabs.addTab(self.ur_panel, "UR crypto-psbt")
        al.addWidget(self.result_tabs)
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
        al.addLayout(btns)
        ol.addWidget(artifacts, 1)
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

    def _section(self, text: str) -> QLabel:
        w = QLabel(text)
        w.setObjectName("section")
        return w

    def _fill_scenarios(self):
        self.scenario_tree.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        self._scenario_items: dict[str, QTreeWidgetItem] = {}
        for s in SCENARIOS:
            if s.group not in groups:
                g = QTreeWidgetItem([s.group])
                g.setFlags(g.flags() & ~Qt.ItemIsSelectable)
                self.scenario_tree.addTopLevelItem(g)
                g.setExpanded(True)
                groups[s.group] = g
            item = QTreeWidgetItem([s.label])
            item.setData(0, Qt.UserRole, s.id)
            item.setToolTip(0, f"{s.summary}\nTokens: {s.token_ops}\nAlways encoded as {FORMAT_LABEL}")
            groups[s.group].addChild(item)
            self._scenario_items[s.id] = item

    def _builder_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        form = QHBoxLayout()
        fmt = QLabel(FORMAT_LABEL)
        fmt.setObjectName("formatBadge")
        self.sign = _combo(["unsigned", "signed"], "unsigned")
        self.synth = QRadioButton("Synthetic UTXOs")
        self.synth.setChecked(True)
        self.synth.setEnabled(False)
        warn = QLabel("Synthetic UTXOs are laboratory fixtures and do not exist on-chain.")
        warn.setObjectName("muted")
        form.addWidget(QLabel("Format"))
        form.addWidget(fmt)
        form.addWidget(QLabel("Sign"))
        form.addWidget(self.sign)
        form.addWidget(self.synth)
        form.addStretch()
        v.addLayout(form)
        v.addWidget(warn)

        rnd = QHBoxLayout()
        self.complexity = _combo(["Simple", "Medium", "Complex", "Monster"], "Simple")
        rb = QPushButton("Random valid scenario")
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
        self.val_panel.setMaximumHeight(80)
        self.val_panel.setPlaceholderText("VALIDATION — engine is authoritative; format is always BCH PSBT v145")
        v.addWidget(self.val_panel)
        return w

    def _json_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("Exact engine configuration. dialect is forced to paytaca-145 (BCH PSBT v145)."))
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

    def _fixtures_tab(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        self.fix_list = QListWidget()
        self.fix_list.itemClicked.connect(self._open_fixture)
        h.addWidget(self.fix_list, 1)
        hint = QLabel(
            "Full engine catalog. Clicking a row generates that semantic "
            "transaction as BCH PSBT v145 — even if the catalog lists other "
            "dialects for differential tests."
        )
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

    def _compare_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        hint = QLabel(
            "Interop only. Primary artifact is always BCH PSBT v145. "
            "Compare mode encodes the same semantic transaction as BIP-174 v0 "
            "so you can see they are different envelopes, not different presets."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.compare_view = QPlainTextEdit()
        self.compare_view.setReadOnly(True)
        self.compare_view.setFont(QFont("Consolas", 10))
        v.addWidget(self.compare_view)
        return w

    def _mode_changed(self, name: str):
        self.ctx.mode = name
        if name not in IMPLEMENTED_MODES:
            QMessageBox.information(
                self,
                "Mode",
                f"{name} is listed as a lab mode but is not wired in this surface.\n"
                "Use generate, inspect, or compare.",
            )
            self.mode.setCurrentText("generate")
            self.ctx.mode = "generate"
            return
        if name == "inspect":
            self.tabs.setCurrentIndex(3)
        elif name == "compare":
            self.tabs.setCurrentIndex(4)
        self._refresh_status()
        self.log(f"Mode {self.ctx.mode}")

    def _scenario_clicked(self, item: QTreeWidgetItem, _col: int):
        cid = item.data(0, Qt.UserRole)
        if cid:
            self._select_scenario(cid, generate=True)

    def _select_scenario(self, cid: str, *, generate: bool):
        try:
            scn = get_scenario(cid)
            self.state = builder_from_catalog(cid)
            self.ctx.scenario_id = scn.id
            self.ctx.scenario_label = scn.label
            self.sign.setCurrentText(self.state.sign if self.state.sign in ("unsigned", "signed") else "unsigned")
            self._reload_inputs()
            self._reload_outputs()
            self._update_summaries()
            self.sync_json()
            item = self._scenario_items.get(cid)
            if item:
                self.scenario_tree.setCurrentItem(item)
            self.log(f"Scenario {scn.label} ({cid}) — will encode as {FORMAT_LABEL}")
            self.tabs.setCurrentIndex(0)
            if generate:
                self._run_engine(catalog_id=cid)
        except Exception as e:
            QMessageBox.warning(self, "Scenario", f"Could not load {cid}\n\n{type(e).__name__}: {e}")
            self.log(f"Scenario {cid} failed: {e}")

    def _sync_state_from_widgets(self):
        self.state.sign = self.sign.currentText()
        sv = self.seed.value()
        self.state.seed = None if sv == 0 else sv
        self.state.synthetic = True
        self.ctx.sign = self.state.sign
        self.ctx.seed = self.state.seed
        self.ctx.mode = self.mode.currentText()

    def _update_summaries(self):
        self.sum_in.setText(str(len(self.state.inputs)))
        self.sum_out.setText(str(len(self.state.outputs)))
        self.sum_tok.setText(self.state.token_summary())
        self.in_box.setTitle(f"INPUTS  ({len(self.state.inputs)})")
        self.out_box.setTitle(f"OUTPUTS  ({len(self.state.outputs)})")

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
        self._update_summaries()

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
        self._update_summaries()

    def add_input(self):
        n = len(self.state.inputs)
        self.state.inputs.append(InputUI(key=f"I{n}", kind="bch"))
        self.state.builder_dirty = True
        self._reload_inputs()

    def add_output(self):
        self.state.outputs.append(OutputUI())
        self.state.builder_dirty = True
        self._reload_outputs()

    def _dup_in(self, n):
        src = self.state.inputs[n]
        self.state.inputs.insert(
            n + 1,
            InputUI(key=src.key + "x", kind=src.kind, owner=src.owner, sats=src.sats, token=TokenUI(**src.token.__dict__)),
        )
        self.state.builder_dirty = True
        self._reload_inputs()

    def _rm_in(self, n):
        if len(self.state.inputs) > 1:
            self.state.inputs.pop(n)
            self.state.builder_dirty = True
            self._reload_inputs()

    def _dup_out(self, n):
        src = self.state.outputs[n]
        self.state.outputs.insert(n + 1, OutputUI(owner=src.owner, sats=src.sats, token=TokenUI(**src.token.__dict__)))
        self.state.builder_dirty = True
        self._reload_outputs()

    def _rm_out(self, n):
        if len(self.state.outputs) > 1:
            self.state.outputs.pop(n)
            self.state.builder_dirty = True
            self._reload_outputs()

    def log(self, msg: str):
        from datetime import datetime

        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self._log_lines.append(line)
        self.log_view.appendPlainText(line)

    def toggle_log(self):
        self.log_dock.setVisible(not self.log_dock.isVisible())

    def new_psbt(self):
        self._select_scenario(DEFAULT_SCENARIO_ID, generate=False)
        self.last_vector = None
        self.out_b64.clear()
        self.out_hex.clear()
        self.out_tx.clear()
        self.out_json.clear()
        self.compare_view.clear()
        self.identity.reset()
        self.val_panel.setPlainText("CONFIGURING — Simple transfer encoded as BCH PSBT v145")
        self.ready.setText("● Ready")
        self.log("Reset to default: Simple transfer / BCH PSBT v145 / Synthetic")

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
        import base64 as b64

        self.last_vector = {
            "psbt_hex": hx,
            "psbt_base64": b64.b64encode(bytes.fromhex(hx)).decode(),
        }
        try:
            self.last_vector.update(inspect(self.last_vector))
        except Exception:
            pass
        self.inspect_view.setPlainText(json.dumps(inspect(self.last_vector), indent=2))
        self.log(f"Opened PSBT {path} ({len(hx)//2} bytes)")
        self.mode.setCurrentText("inspect")
        self.tabs.setCurrentIndex(3)

    def _open_fixture(self, item: QListWidgetItem):
        ident = item.text().split()[0]
        self._run_engine(catalog_id=ident)

    def _load_fixtures(self):
        self.fix_list.clear()
        for row in catalog():
            self.fix_list.addItem(f"{row['id']}  [{row['group']}]  {row['title']}")

    def sync_json(self):
        self._sync_state_from_widgets()
        self.json_edit.setPlainText(json.dumps(self.state.to_engine_config(), indent=2))

    def generate_json(self):
        try:
            cfg = json.loads(self.json_edit.toPlainText())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON", str(e))
            return
        cfg["format"] = "bch-psbt-v145"
        cfg["dialect"] = "paytaca-145"
        self._run_engine(raw=cfg)

    def generate(self):
        self._sync_state_from_widgets()
        if self.ctx.mode == "inspect":
            if self.last_vector:
                self.tabs.setCurrentIndex(3)
            return
        if self.ctx.mode == "compare":
            self._run_compare()
            return
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
                mode=self.ctx.mode if self.ctx.mode == "generate" else "generate",
                scenario_label=self.ctx.scenario_label,
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

    def _run_compare(self):
        try:
            vec = compare_encodings(
                self.state,
                catalog_id=self.ctx.scenario_id if not self.state.builder_dirty else None,
                seed=self.state.seed,
            )
        except Exception as e:
            QMessageBox.warning(self, "Compare", str(e))
            return
        self._show_vector(vec)
        cmp = vec.get("_compare") or {}
        self.compare_view.setPlainText(
            json.dumps(
                {
                    "note": "Primary encoding is BCH PSBT v145. BIP-174 is interop-only.",
                    **cmp,
                },
                indent=2,
            )
        )
        self.tabs.setCurrentIndex(4)

    def _show_vector(self, vec: dict):
        self.last_vector = vec
        ident = fixture_identity(
            vec,
            scenario_id=self.ctx.scenario_id,
            scenario_label=self.ctx.scenario_label,
        )
        self.identity.show_identity(ident)
        ok = bool(vec.get("consensus_match"))
        reason = vec.get("actual_consensus_reason") or ""
        lines = [
            f"{'✓' if ok else '✕'} BCH tx consensus={vec.get('actual_consensus')}  PSBT v145={vec.get('actual_psbt')}",
            f"format={FORMAT_LABEL}  reference={REFERENCE_LABEL}",
            f"scenario={self.ctx.scenario_label or vec.get('id')}  {ident.n_in} in / {ident.n_out} out",
            f"tokens={ident.token_operations}  scripts={ident.scripts}",
            reason,
        ]
        self.val_panel.setPlainText("\n".join(str(x) for x in lines if x))
        self.val_lbl.setText("VALID v145" if ident.psbt_valid and ok else "INVALID / see identity")
        self.ready.setText("● Generated v145" if vec.get("psbt_base64") else "● Ready")
        self.out_b64.setPlainText(vec.get("psbt_base64") or "")
        self.out_hex.setPlainText(vec.get("psbt_hex") or "")
        self.out_tx.setPlainText((vec.get("txid") or "") + "\n" + (vec.get("unsigned_tx_hex") or ""))
        slim = {
            k: vec.get(k)
            for k in ("id", "txid", "semantics", "source_utxos", "outputs", "previous_txs")
        }
        slim["lab"] = vec.get("_lab")
        self.out_json.setPlainText(json.dumps(slim, indent=2, default=str))
        try:
            self.inspect_view.setPlainText(json.dumps(inspect(vec), indent=2, default=str))
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
            f"Generated {vec.get('id')} as {FORMAT_LABEL}  {n} bytes  "
            f"consensus={vec.get('actual_consensus')}  psbt={vec.get('actual_psbt')}"
        )
        self._refresh_status()

    def copy_ur_seedcash(self):
        self.ur_panel.copy_seedcash()
        self.status.showMessage("UR copied for SeedCash", 4000)

    def _current_text(self) -> str:
        w = self.result_tabs.currentWidget()
        return w.toPlainText() if hasattr(w, "toPlainText") else ""

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
            json.dumps(
                {
                    "type": "crypto-psbt",
                    "format": FORMAT_LABEL,
                    "frames": len(parts),
                    "compat": "same-libraries",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.log(f"Exported fixture + {len(parts)} UR frames to {dest}")
        self.status.showMessage(f"Exported to {dest}", 5000)

    def _refresh_status(self):
        st = status_line()
        self.status.showMessage(
            f"FORMAT {st['format']}  |  REF {st['reference']}  |  "
            f"MODE {self.ctx.mode} / {st['mode']}  |  "
            f"SCENARIO {self.ctx.scenario_label}  |  "
            f"engine {st['engine']} {st['version']} {st['tests']}"
        )


def run():
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    return app.exec()
