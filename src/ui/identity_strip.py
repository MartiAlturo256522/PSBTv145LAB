"""Compact fixture validation summary for the desktop results pane."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout
from application.identity import FixtureIdentity


def _chip(text: str, kind: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName({"pass": "chipPass", "fail": "chipFail", "mute": "chipMute"}[kind])
    label.setWordWrap(True)
    return label


class IdentityStrip(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("identityStrip")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        self.chips = QGridLayout()
        self.chips.setSpacing(4)
        layout.addLayout(self.chips)
        self.detail = QLabel()
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.reset()

    def _set_chips(self, chips):
        while self.chips.count():
            widget = self.chips.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        for index, (text, kind) in enumerate(chips):
            self.chips.addWidget(_chip(text, kind), index // 2, index % 2)

    def reset(self):
        self._set_chips([("BCH transaction —", "mute"), ("PSBT v145 —", "mute"),
                         ("Paytaca wire —", "mute"), ("Local receiver —", "mute")])
        self.detail.setText("Select a scenario to generate a fixture and validate its contents.")

    def show_identity(self, ident: FixtureIdentity):
        self._set_chips([
            ("BCH transaction: " + ("valid" if ident.bch_tx_valid else "invalid"), "pass" if ident.bch_tx_valid else "fail"),
            ("PSBT v145: " + ("valid" if ident.psbt_valid else "invalid"), "pass" if ident.psbt_valid else "fail"),
            ("Paytaca wire: " + ident.paytaca_status, "pass" if ident.paytaca_status == "wire" else "fail"),
            ("Local receiver: " + ident.seedcash_status, "pass" if ident.seedcash_status in ("parse", "partial") else "fail"),
        ])
        self.detail.setText(
            f"{ident.n_in} inputs · {ident.n_out} outputs · "
            f"{', '.join(ident.scripts)}\nTokens: {', '.join(ident.token_operations)}"
        )
        self.detail.setToolTip("\n".join(ident.detail_lines()))
