"""Identity chips + detail lines for a generated v145 fixture."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from desktop.application.identity import FixtureIdentity


def _chip(text: str, kind: str) -> QLabel:
    w = QLabel(text)
    w.setObjectName({"pass": "chipPass", "fail": "chipFail", "mute": "chipMute"}[kind])
    w.setAutoFillBackground(True)
    w.setContentsMargins(8, 4, 8, 4)
    return w


class IdentityStrip(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("identityStrip")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(8)
        lay.addLayout(self.chips)
        self.detail = QLabel("Generate a scenario to see fixture identity. Format is always BCH PSBT v145.")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        lay.addWidget(self.detail)
        self.reset()

    def _clear_chips(self):
        while self.chips.count():
            item = self.chips.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def reset(self):
        self._clear_chips()
        self.chips.addWidget(_chip("BCH PSBT v145", "pass"))
        self.chips.addWidget(_chip("VALID BCH TRANSACTION —", "mute"))
        self.chips.addWidget(_chip("VALID PSBT v145 —", "mute"))
        self.chips.addWidget(_chip("PAYTACA —", "mute"))
        self.chips.addWidget(_chip("SEEDCASH —", "mute"))
        self.chips.addStretch()
        self.detail.setText(
            "PSBT format = BCH v145 (invariant)\n"
            "unsigned transaction present = —\n"
            "CashTokens = —\n"
            "input count = —    output count = —\n"
            "scripts = —\n"
            "token operations = —\n"
            "Paytaca compatibility = —\n"
            "SeedCash compatibility = —\n"
            "semantic validation = —"
        )

    def show_identity(self, ident: FixtureIdentity):
        self._clear_chips()
        self.chips.addWidget(_chip("BCH PSBT v145", "pass"))
        self.chips.addWidget(
            _chip(
                "VALID BCH TRANSACTION" if ident.bch_tx_valid else "INVALID BCH TRANSACTION",
                "pass" if ident.bch_tx_valid else "fail",
            )
        )
        self.chips.addWidget(
            _chip(
                "VALID PSBT v145" if ident.psbt_valid else "INVALID PSBT v145",
                "pass" if ident.psbt_valid else "fail",
            )
        )
        pay_kind = "pass" if ident.paytaca_status in ("match", "wire") else "fail"
        self.chips.addWidget(_chip(ident.paytaca_badge, pay_kind))
        sc_kind = "pass" if ident.seedcash_status in ("parse", "partial") else "fail"
        self.chips.addWidget(_chip(ident.seedcash_badge, sc_kind))
        self.chips.addStretch()
        self.detail.setText("\n".join(ident.detail_lines()))
