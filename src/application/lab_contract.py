"""Lab-wide invariants. Format is not a per-preset choice.

The frozen engine can encode several PSBT dialects for differential tests.
This desktop product does not: every generated fixture is BCH PSBT v145
unless the user is explicitly in interoperability/compare mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Product format — global invariant of generated fixtures.
FORMAT_ID = "bch-psbt-v145"
FORMAT_LABEL = "BCH PSBT v145"
FORMAT_VERSION = 145

# Engine codec name for FORMAT_ID. Internal wire mapping, not a UI dialect.
WIRE_DIALECT = "paytaca-145"

# Byte-oracle pin. Same commit the frozen motor clones.
REFERENCE_ID = "paytaca-js-9c338d2"
REFERENCE_LABEL = "Paytaca JS psbt.js @ 9c338d2"
REFERENCE_COMMIT = "9c338d2ce07ee33cda2cec33bb340657c6fc1990"
REFERENCE_REPO = "https://github.com/paytaca/paytaca-app"

NETWORK = "BCH"
UTXO_SOURCE = "synthetic"
DEFAULT_SIGN = "unsigned"
DEFAULT_MODE = "generate"
DEFAULT_SCENARIO_ID = "IO-1-1"
DEFAULT_SCENARIO_LABEL = "Simple transfer"

# Workflow modes. Only "compare" may introduce a second PSBT encoding.
MODES = ("generate", "inspect", "compare", "mutate", "fuzz")
IMPLEMENTED_MODES = ("generate", "inspect", "compare")

# The one other encoding allowed, and only in compare mode.
INTEROP_DIALECT = "bip174-v0"
INTEROP_FORMAT_LABEL = "BIP-174 v0 (interop only)"


@dataclass
class LabContext:
    """Session-level product state. Format/reference are not writable."""

    mode: str = DEFAULT_MODE
    utxo_source: str = UTXO_SOURCE
    scenario_id: str = DEFAULT_SCENARIO_ID
    scenario_label: str = DEFAULT_SCENARIO_LABEL
    sign: str = DEFAULT_SIGN
    seed: Optional[int] = None
    interop_dialect: Optional[str] = None  # set only in compare mode

    @property
    def format_id(self) -> str:
        return FORMAT_ID

    @property
    def format_label(self) -> str:
        return FORMAT_LABEL

    @property
    def reference_id(self) -> str:
        return REFERENCE_ID

    @property
    def reference_label(self) -> str:
        return REFERENCE_LABEL

    @property
    def wire_dialect(self) -> str:
        return WIRE_DIALECT

    def encoding_dialect(self) -> str:
        """Dialect passed to the frozen engine."""
        if self.mode == "compare" and self.interop_dialect:
            return self.interop_dialect
        return WIRE_DIALECT
