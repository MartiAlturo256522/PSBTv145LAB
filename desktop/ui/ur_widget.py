"""Animated QR / UR panel. Encodes PSBT bytes only; no PSBT construction."""

from __future__ import annotations

from io import BytesIO

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from desktop.application.ur_service import SPEED_MS, encode_ur


def _qr_pixmap(text: str, box: int = 6) -> QPixmap:
    import qrcode

    img = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=box, border=2)
    img.add_data(text.upper())
    img.make(fit=True)
    pil = img.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    pil.save(buf, format="PNG")
    pix = QPixmap()
    pix.loadFromData(buf.getvalue())
    return pix


class UrPanel(QWidget):
    def __init__(self, log_fn=None):
        super().__init__()
        self._log = log_fn or (lambda *_: None)
        self.parts: list[str] = []
        self.idx = 0
        self.meta: dict = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        lay = QVBoxLayout(self)
        self.info = QLabel("UR: empty — generate a PSBT first")
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignCenter)
        self.qr.setMinimumHeight(280)
        self.qr.setStyleSheet("background:#fff; border:1px solid #333;")
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumHeight(80)
        row = QHBoxLayout()
        self.play = QPushButton("Play")
        self.pause = QPushButton("Pause")
        self.prev = QPushButton("‹ Prev")
        self.nxt = QPushButton("Next ›")
        self.copy_ur = QPushButton("Copy UR")
        self.copy_all = QPushButton("Copy UR for SeedCash")
        for b, fn in (
            (self.play, self.start),
            (self.pause, self.stop),
            (self.prev, self.prev_frame),
            (self.nxt, self.next_frame),
            (self.copy_ur, self.copy_one),
            (self.copy_all, self.copy_seedcash),
        ):
            b.clicked.connect(fn)
            row.addWidget(b)
        dens = QHBoxLayout()
        dens.addWidget(QLabel("Density"))
        self.density = QComboBox()
        self.density.addItems(["Low", "Medium", "High", "Maximum"])
        self.density.setCurrentText("High")
        self.density.currentTextChanged.connect(self._density_changed)
        dens.addWidget(self.density)
        dens.addWidget(QLabel("Speed"))
        self.speed = QComboBox()
        self.speed.addItems(["Slow", "Normal", "Fast", "Very fast"])
        self.speed.setCurrentText("Normal")
        self.speed.currentTextChanged.connect(self._speed_changed)
        dens.addWidget(self.speed)
        self.interval = QSlider(Qt.Horizontal)
        self.interval.setRange(40, 600)
        self.interval.setValue(180)
        self.interval.valueChanged.connect(self._slider)
        dens.addWidget(self.interval)
        self.speed_lbl = QLabel("Interval: 180 ms")
        dens.addWidget(self.speed_lbl)
        dens.addStretch()
        lay.addWidget(self.info)
        lay.addWidget(self.qr, 1)
        lay.addLayout(row)
        lay.addLayout(dens)
        lay.addWidget(self.text)
        self._psbt_hex = ""

    def encode_from_psbt(self, psbt_hex: str):
        self._psbt_hex = psbt_hex
        if not psbt_hex:
            self.parts = []
            self.info.setText("UR: empty")
            return
        data = encode_ur(psbt_hex, self.density.currentText())
        self.meta = data
        self.parts = data.get("parts") or []
        self.idx = 0
        n = data.get("fragmentsLength") or len(self.parts)
        mode = "Single" if data.get("single") else "Multipart fountain"
        self.info.setText(
            f"Type: crypto-psbt  |  {mode}  |  fragmentsLength={n}  |  "
            f"density={data.get('density')} maxFragment={data.get('maxFragment')}  |  "
            f"roundtrip={data.get('roundtrip')}  |  compat={data.get('paytaca_compat')}"
        )
        self._log(f"UR encoded: fragmentsLength={n} roundtrip={data.get('roundtrip')}")
        self._show()
        if not data.get("single"):
            self.start()
        else:
            self.stop()

    def _density_changed(self, *_):
        if self._psbt_hex:
            playing = self.timer.isActive()
            self.encode_from_psbt(self._psbt_hex)
            if playing:
                self.start()

    def _speed_changed(self, name: str):
        ms = SPEED_MS.get(name, 180)
        self.interval.setValue(ms)
        self._slider(ms)

    def _slider(self, ms: int):
        self.speed_lbl.setText(f"Interval: {ms} ms  FPS: {1000/ms:.1f}")
        if self.timer.isActive():
            self.timer.start(ms)

    def start(self):
        if self.parts:
            self.timer.start(self.interval.value())

    def stop(self):
        self.timer.stop()

    def next_frame(self):
        if not self.parts:
            return
        self.idx = (self.idx + 1) % len(self.parts)
        self._show()

    def prev_frame(self):
        if not self.parts:
            return
        self.idx = (self.idx - 1) % len(self.parts)
        self._show()

    def _show(self):
        if not self.parts:
            return
        part = self.parts[self.idx]
        self.text.setPlainText(part)
        try:
            self.qr.setPixmap(_qr_pixmap(part).scaled(280, 280, Qt.KeepAspectRatio, Qt.FastTransformation))
        except Exception as e:
            self.qr.setText(f"QR error: {e}")
        self.info.setText(self.info.text().split(" | Frame:")[0] + f" | Frame: {self.idx+1}/{len(self.parts)}")

    def copy_one(self):
        from PySide6.QtWidgets import QApplication

        if self.parts:
            QApplication.clipboard().setText(self.parts[self.idx])

    def copy_seedcash(self):
        from PySide6.QtWidgets import QApplication

        if self.parts:
            QApplication.clipboard().setText("\n".join(self.parts[: self.meta.get("fragmentsLength") or len(self.parts)]))

    def current_parts(self) -> list[str]:
        return list(self.parts)
