"""Finite coverage tracker for synthetic campaign intents.

Dimensions are closed sets (not infinite): n_in/n_out 1..6, script types,
token classes, and output ordering.
"""

from __future__ import annotations

from typing import Any

from ctlab.lab.intent import TransactionIntent

EXPECTED_N = tuple(range(1, 7))
EXPECTED_SCRIPTS = ("p2pkh", "p2sh20", "op_return")
EXPECTED_TOKENS = ("none", "FT", "NFT", "hybrid", "genesis")
EXPECTED_ORDERING = ("payment-first", "change-first", "opreturn-first", "token-first")


def token_classes(intent: TransactionIntent) -> set[str]:
    # Hybrid is first-class: a minting+FT genesis is genesis AND hybrid AND NFT AND FT.
    labels: set[str] = set()
    genesis = any(i.kind == "genesis_parent" for i in intent.inputs) or any(
        (o.token is not None and o.token.genesis) or o.genesis_from is not None for o in intent.outputs
    )
    if genesis:
        labels.add("genesis")
    toks = [i.token for i in intent.inputs if i.token is not None] + [
        o.token for o in intent.outputs if o.token is not None
    ]
    if any(t.is_hybrid() for t in toks):
        labels.add("hybrid")
    if any(t.is_nft() for t in toks):
        labels.add("NFT")
    if any(t.is_ft() for t in toks):
        labels.add("FT")
    if not labels:
        labels.add("none")
    return labels


def token_class(intent: TransactionIntent) -> str:
    labels = token_classes(intent)
    for name in ("genesis", "hybrid", "NFT", "FT", "none"):
        if name in labels:
            return name
    return "none"


def ordering_class(intent: TransactionIntent) -> str:
    if not intent.outputs:
        return "payment-first"
    o0 = intent.outputs[0]
    if o0.role == "op_return" or o0.script == "op_return":
        return "opreturn-first"
    if o0.role == "change":
        return "change-first"
    if o0.token is not None and (o0.token.is_ft() or o0.token.is_nft() or o0.token.genesis):
        return "token-first"
    return "payment-first"


class CoverageTracker:
    def __init__(self) -> None:
        self.n_in: set[int] = set()
        self.n_out: set[int] = set()
        self.scripts: set[str] = set()
        self.tokens: set[str] = set()
        self.ordering: set[str] = set()
        self.cardinalities: set[tuple[int, int]] = set()
        self._count = 0

    def observe(self, intent: TransactionIntent) -> None:
        self._count += 1
        self.n_in.add(intent.n_in)
        self.n_out.add(intent.n_out)
        self.cardinalities.add((intent.n_in, intent.n_out))
        for o in intent.outputs:
            self.scripts.add(o.script)
        self.tokens.update(token_classes(intent))
        self.ordering.add(ordering_class(intent))

    def report(self) -> dict[str, Any]:
        expected_cards = {(i, o) for i in EXPECTED_N for o in EXPECTED_N}
        return {
            "intents": self._count,
            "seen": {
                "n_in": sorted(self.n_in),
                "n_out": sorted(self.n_out),
                "scripts": sorted(self.scripts),
                "tokens": sorted(self.tokens),
                "ordering": sorted(self.ordering),
                "cardinalities": sorted(self.cardinalities),
            },
            "missing": {
                "n_in": [n for n in EXPECTED_N if n not in self.n_in],
                "n_out": [n for n in EXPECTED_N if n not in self.n_out],
                "scripts": [s for s in EXPECTED_SCRIPTS if s not in self.scripts],
                "tokens": [t for t in EXPECTED_TOKENS if t not in self.tokens],
                "ordering": [o for o in EXPECTED_ORDERING if o not in self.ordering],
                "cardinalities": sorted(expected_cards - self.cardinalities),
            },
        }
