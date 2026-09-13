"""UI builder state → frozen-engine catalog dict.

Format is the lab invariant (BCH PSBT v145), not a field the user picks
per scenario. `dialect` in the engine config is the internal wire name
for that format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from desktop.application.lab_contract import (
    DEFAULT_SCENARIO_ID,
    DEFAULT_SCENARIO_LABEL,
    DEFAULT_SIGN,
    FORMAT_ID,
    WIRE_DIALECT,
)


OWNERS = ["alice", "bob", "carol", "dave"]


@dataclass
class TokenUI:
    kind: str = "none"  # none | ft | nft | hybrid | authority
    category_mode: str = "auto"  # auto | group | hex
    category_group: str = "A"
    category_hex: str = ""
    ft_amount: int = 0
    nft: str = "none"  # none | immutable | mutable | minting
    commitment: str = ""
    commitment_is_hex: bool = True

    def capability(self) -> Optional[str]:
        if self.kind in ("none", "ft"):
            return None
        if self.kind == "authority" or self.nft == "minting":
            return "minting"
        if self.nft == "mutable":
            return "mutable"
        if self.nft == "immutable" or self.kind in ("nft", "hybrid"):
            return "none" if self.nft in ("none", "immutable") else self.nft
        return None

    def to_token_dict(self, *, genesis: bool, existing_key: str | None = None) -> dict | None:
        if self.kind == "none":
            return None
        cap = self.capability()
        nft = None
        if self.kind in ("nft", "hybrid", "authority") or (cap is not None):
            if self.kind != "ft":
                c = self.commitment
                nft = {"capability": cap or "none", "commitment": c}
        amt = int(self.ft_amount or 0)
        if self.kind == "nft" or self.kind == "authority":
            amt = 0
        if self.kind == "ft":
            nft = None
        tok: dict[str, Any] = {"amount": amt, "nft": nft}
        if not genesis and existing_key:
            tok["category_from_existing"] = existing_key
        elif self.category_mode == "hex" and len(self.category_hex) == 64:
            tok["category"] = self.category_hex
        return tok

    def summary(self) -> str:
        if self.kind == "none":
            return "BCH only"
        parts = [f"group {self.category_group}" if self.category_mode == "group" else self.category_mode]
        if self.kind in ("ft", "hybrid") and self.ft_amount:
            parts.append(f"FT {self.ft_amount}")
        if self.kind in ("nft", "hybrid", "authority"):
            parts.append(f"NFT {self.nft or 'immutable'}")
            if self.commitment:
                parts.append(f"commit {self.commitment[:16]}")
        return " · ".join(parts)


@dataclass
class InputUI:
    key: str = "I0"
    kind: str = "bch"  # genesis_parent | token | bch
    synthetic: bool = True
    owner: str = "alice"
    vout: int = 0
    sats: int = 50_000
    sequence: int = 0xFFFFFFFF
    token: TokenUI = field(default_factory=TokenUI)

    def engine_existing(self) -> dict | None:
        if self.kind != "token":
            return None
        tok = self.token.to_token_dict(genesis=True) or {"amount": 0, "nft": None}
        row = {
            "key": self.key,
            "owner": self.owner,
            "sats": max(self.sats, 1000),
            "token": tok,
        }
        if self.token.category_mode == "group" and self.token.category_group:
            row["category_group"] = self.token.category_group
        return row

    def engine_input(self) -> dict:
        if self.kind == "genesis_parent":
            return {
                "kind": "genesis_parent",
                "key": self.key,
                "owner": self.owner,
                "sats": self.sats,
                "sequence": self.sequence,
            }
        if self.kind == "token":
            return {"kind": "token", "key": self.key, "owner": self.owner, "sequence": self.sequence}
        return {
            "kind": "bch",
            "key": self.key,
            "owner": self.owner,
            "sats": self.sats,
            "vout": self.vout,
            "sequence": self.sequence,
        }


@dataclass
class OutputUI:
    owner: str = "bob"
    sats: int = 48_000
    script: str = "p2pkh"
    genesis_from: Optional[int] = None
    token: TokenUI = field(default_factory=TokenUI)
    existing_key: str = ""

    def engine_output(self, genesis_vin: int | None) -> dict:
        out: dict[str, Any] = {
            "owner": self.owner,
            "sats": self.sats,
            "script": self.script,
        }
        gfrom = self.genesis_from if self.genesis_from is not None else genesis_vin
        tok = self.token.to_token_dict(
            genesis=gfrom is not None and self.token.kind != "none" and self.token.category_mode == "auto",
            existing_key=self.existing_key or None,
        )
        if tok is not None:
            out["token"] = tok
            if gfrom is not None and self.token.category_mode == "auto":
                out["genesis_from"] = gfrom
        return out


@dataclass
class BuilderState:
    """Semantic transaction under construction. Encoding is always PSBT v145."""

    scenario_id: str = DEFAULT_SCENARIO_ID
    scenario_label: str = DEFAULT_SCENARIO_LABEL
    sign: str = DEFAULT_SIGN
    tx_version: int = 2
    locktime: int = 0
    network: str = "mainnet"
    synthetic: bool = True
    seed: Optional[int] = None
    builder_dirty: bool = False
    inputs: list[InputUI] = field(default_factory=list)
    outputs: list[OutputUI] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.inputs:
            self.inputs = [InputUI(key="A", kind="bch", owner="alice", vout=0, sats=50_000)]
        if not self.outputs:
            self.outputs = [OutputUI(owner="bob", sats=48_000, token=TokenUI(kind="none"))]

    @property
    def format_id(self) -> str:
        return FORMAT_ID

    @property
    def dialect(self) -> str:
        """Engine wire name for the lab format. Not a user-selectable dialect."""
        return WIRE_DIALECT

    def token_summary(self) -> str:
        kinds = [o.token.kind for o in self.outputs if o.token.kind != "none"]
        kinds += [i.token.kind for i in self.inputs if i.kind == "token" and i.token.kind != "none"]
        if not kinds:
            return "none"
        return ", ".join(dict.fromkeys(kinds))

    def to_engine_config(self) -> dict[str, Any]:
        existing = []
        seen: set[str] = set()
        for inp in self.inputs:
            row = inp.engine_existing()
            if row and row["key"] not in seen:
                existing.append(row)
                seen.add(row["key"])
        genesis_vin = next(
            (i for i, inp in enumerate(self.inputs) if inp.kind == "genesis_parent"),
            None,
        )
        outs: list[dict[str, Any]] = []
        for o in self.outputs:
            is_genesis = (
                o.token.kind != "none"
                and o.token.category_mode == "auto"
                and genesis_vin is not None
            )
            existing_key = o.existing_key or None
            if o.token.kind != "none" and o.token.category_mode == "group":
                existing_key = next(
                    (
                        inp.key
                        for inp in self.inputs
                        if inp.kind == "token" and inp.token.category_group == o.token.category_group
                    ),
                    existing_key,
                )
                is_genesis = False
            out: dict[str, Any] = {"owner": o.owner, "sats": o.sats, "script": o.script}
            tok = o.token.to_token_dict(genesis=is_genesis, existing_key=existing_key)
            if tok is not None:
                out["token"] = tok
                if is_genesis:
                    out["genesis_from"] = (
                        o.genesis_from if o.genesis_from is not None else genesis_vin
                    )
            outs.append(out)
        return {
            "id": self.scenario_id or "UI-BUILD",
            "group": "desktop",
            "title": self.scenario_label or "SeedCash PSBT Lab builder",
            "format": FORMAT_ID,
            "dialect": WIRE_DIALECT,
            "sign_state": self.sign,
            "tx_version": self.tx_version,
            "locktime": self.locktime,
            "existing": existing,
            "inputs": [i.engine_input() for i in self.inputs],
            "outputs": outs,
            "extra": {"tx_version": self.tx_version, "locktime": self.locktime},
        }

    def to_json(self) -> dict[str, Any]:
        return self.to_engine_config()


def default_simple_transfer() -> BuilderState:
    return BuilderState()


def default_genesis_ft() -> BuilderState:
    s = BuilderState()
    s.scenario_id = "GEN-04"
    s.scenario_label = "Genesis FT"
    s.inputs = [InputUI(key="A", kind="genesis_parent", token=TokenUI(kind="none"))]
    s.outputs = [
        OutputUI(
            genesis_from=0,
            token=TokenUI(kind="ft", ft_amount=1000, category_mode="auto", category_group="A"),
        )
    ]
    return s
