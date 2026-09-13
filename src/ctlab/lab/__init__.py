"""Synthetic BCH PSBT v145 laboratory layer.

Sits on top of the frozen motor ``ctlab.engine.generate``. Does not replace it.
Does not patch SeedCash. Default dialect is Paytaca PSBT v145 (BCH extension of
PSBT v2), never BIP-174/v0.

Layers of a finding (never collapsed):
  A. TRANSACTION CORRECTNESS — signed tx == intended unsigned tx
  B. PSBT SEMANTIC CORRECTNESS — maps describe that tx (incl. 0x36, extra 00)
  C. REVIEW CORRECTNESS — UI shows what will be signed
"""

from ctlab.lab.intent import OutputIntent, TokenIntent, TransactionIntent, InputIntent
from ctlab.lab.maps import maps_vs_unsigned, walk_naive_no_skip, walk_paytaca_v145
from ctlab.lab.oracle import evaluate
from ctlab.lab.paytaca_diff import compare_vector
from ctlab.lab.seedcash_adapter import capture, parse_psbt_maps, shown_address_amounts, ui_route
from ctlab.lab.ur import roundtrip_ur, unwrap_psbt_cbor, wrap_psbt_cbor

LAB_CAMPAIGN_VERSION = "0.2.0"
PAYTACA_PSBT_JS = "9c338d2ce07ee33cda2cec33bb340657c6fc1990"
PSBT_V145 = 145  # GLOBAL_VERSION. Not BIP-44 coin type.

__all__ = [
    "LAB_CAMPAIGN_VERSION",
    "PAYTACA_PSBT_JS",
    "PSBT_V145",
    "TransactionIntent",
    "InputIntent",
    "OutputIntent",
    "TokenIntent",
    "compare_vector",
    "wrap_psbt_cbor",
    "unwrap_psbt_cbor",
    "roundtrip_ur",
    "capture",
    "evaluate",
    "maps_vs_unsigned",
    "parse_psbt_maps",
    "shown_address_amounts",
    "ui_route",
    "walk_naive_no_skip",
    "walk_paytaca_v145",
]
