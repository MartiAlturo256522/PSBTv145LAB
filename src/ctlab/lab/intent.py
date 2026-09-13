"""Ground-truth transaction intent. Hybrid NFT+FT is first-class (never elif)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


ROLES = (
    "payment",
    "change",
    "op_return",
    "token_transfer",
    "genesis",
    "burn",
    "unknown",
)
SCRIPTS = ("p2pkh", "p2sh20", "p2sh32", "op_return", "bare", "unknown")
NFT_CAPS = ("none", "mutable", "minting")


@dataclass
class TokenIntent:
    amount: int = 0
    nft_capability: str | None = None
    commitment: bytes = b""
    genesis: bool = False
    category_from: str | None = None  # existing UTXO key

    def is_ft(self) -> bool:
        return self.amount > 0

    def is_nft(self) -> bool:
        return self.nft_capability is not None

    def is_hybrid(self) -> bool:
        return self.is_ft() and self.is_nft()

    def to_engine_token(self) -> dict[str, Any]:
        nft = None
        if self.nft_capability is not None:
            nft = {
                "capability": self.nft_capability,
                "commitment": self.commitment.hex() if self.commitment else "",
            }
        d: dict[str, Any] = {"nft": nft, "amount": int(self.amount)}
        if self.category_from:
            d["category_from_existing"] = self.category_from
        return d


@dataclass
class InputIntent:
    kind: str  # bch | genesis_parent | token
    key: str
    owner: str = "alice"
    sats: int = 50_000
    token: TokenIntent | None = None
    sequence: int = 0xFFFFFFFF
    vout: int | None = None


@dataclass
class OutputIntent:
    owner: str
    sats: int
    role: str = "payment"
    script: str = "p2pkh"
    token: TokenIntent | None = None
    genesis_from: int | None = None
    malformed_script: bytes | None = None


@dataclass
class TransactionIntent:
    id: str
    seed: int = 0
    inputs: list[InputIntent] = field(default_factory=list)
    outputs: list[OutputIntent] = field(default_factory=list)
    existing: list[dict[str, Any]] = field(default_factory=list)
    locktime: int = 0
    sighash: str = "ALL|FORKID"
    mode: str = "NORMAL"
    mutations: list[str] = field(default_factory=list)
    description: str = ""

    @property
    def n_in(self) -> int:
        return len(self.inputs)

    @property
    def n_out(self) -> int:
        return len(self.outputs)

    def expected_review(self) -> dict[str, Any]:
        token_ins = sum(1 for i in self.inputs if i.kind == "token" or (i.token and (i.token.is_ft() or i.token.is_nft())))
        token_outs = [o for o in self.outputs if o.token and (o.token.is_ft() or o.token.is_nft() or o.token.genesis)]
        genesis = any(o.token and o.token.genesis for o in self.outputs) or any(
            i.kind == "genesis_parent" for i in self.inputs
        )
        hybrid = any(o.token and o.token.is_hybrid() for o in self.outputs)
        if genesis and token_ins == 0:
            ui_route = "TOKEN_GENESIS"  # SeedCash currently routes BCH_ONLY — expected != actual
        elif any(o.token and o.token.is_nft() for o in self.outputs) or any(
            i.token and i.token.is_nft() for i in self.inputs
        ):
            ui_route = "NFT_FIRST"
        elif any(o.token and o.token.is_ft() for o in self.outputs) or any(
            i.token and i.token.is_ft() for i in self.inputs
        ):
            ui_route = "FT_FIRST"
        else:
            ui_route = "BCH_ONLY"
        return {
            "ui_route": ui_route,
            "n_in": self.n_in,
            "n_out": self.n_out,
            "roles": [o.role for o in self.outputs],
            "scripts": [o.script for o in self.outputs],
            "payments": [i for i, o in enumerate(self.outputs) if o.role == "payment"],
            "change": [i for i, o in enumerate(self.outputs) if o.role == "change"],
            "op_return": [i for i, o in enumerate(self.outputs) if o.role == "op_return" or o.script == "op_return"],
            "token_outputs": [i for i, o in enumerate(self.outputs) if o in token_outs or (o.token and (o.token.is_ft() or o.token.is_nft()))],
            "genesis": genesis,
            "hybrid": hybrid,
            "sighash": self.sighash,
        }

    def to_engine_config(self) -> dict[str, Any]:
        existing = list(self.existing)
        for inp in self.inputs:
            if inp.kind == "token" and inp.token is not None:
                if not any(e.get("key") == inp.key for e in existing):
                    existing.append(
                        {
                            "key": inp.key,
                            "owner": inp.owner,
                            "sats": inp.sats,
                            "token": inp.token.to_engine_token(),
                        }
                    )
        inputs = []
        for inp in self.inputs:
            row: dict[str, Any] = {
                "kind": inp.kind,
                "key": inp.key,
                "owner": inp.owner,
                "sats": inp.sats,
                "sequence": inp.sequence,
            }
            if inp.vout is not None:
                row["vout"] = inp.vout
            inputs.append(row)
        outputs = []
        for out in self.outputs:
            row: dict[str, Any] = {
                "owner": out.owner,
                "sats": out.sats,
                "script": out.script,
            }
            if out.token is not None:
                row["token"] = out.token.to_engine_token()
            if out.genesis_from is not None:
                row["genesis_from"] = out.genesis_from
            outputs.append(row)
        return {
            "id": self.id,
            "dialect": "paytaca-145",
            "sign_state": "unsigned",
            "sighash": self.sighash,
            "locktime": self.locktime,
            "existing": existing,
            "inputs": inputs,
            "outputs": outputs,
            "_seed": self.seed,
            "description": self.description,
            "mode": self.mode,
            "mutations": list(self.mutations),
        }

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        for inp in d["inputs"]:
            tok = inp.get("token")
            if tok and isinstance(tok.get("commitment"), (bytes, bytearray)):
                tok["commitment"] = tok["commitment"].hex()
        for out in d["outputs"]:
            tok = out.get("token")
            if tok and isinstance(tok.get("commitment"), (bytes, bytearray)):
                tok["commitment"] = tok["commitment"].hex()
            if out.get("malformed_script"):
                out["malformed_script"] = out["malformed_script"].hex()
        d["expected_review"] = self.expected_review()
        return d

    def clone(self, **kwargs: Any) -> "TransactionIntent":
        return replace(self, **kwargs)
