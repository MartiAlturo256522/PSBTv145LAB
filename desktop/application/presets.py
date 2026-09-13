"""Semantic transaction scenarios. A scenario is not a PSBT format.

Every scenario generates one BCH transaction encoded as PSBT v145.
IO-* cases reuse the frozen M0 configs so Simple transfer matches the
21-vector regression corpus when generated from the scenario, not the
builder widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from desktop.application.builder_model import BuilderState, InputUI, OutputUI, TokenUI
from desktop.application.lab_contract import DEFAULT_SCENARIO_ID


@dataclass(frozen=True)
class Scenario:
    id: str
    label: str
    group: str
    summary: str
    token_ops: str
    catalog_id: Optional[str] = None
    config: Optional[dict[str, Any]] = None

    io: tuple | None = None  # (n_in, n_out, change) → frozen M0 BCH IO config

    def engine_source(self) -> str | dict[str, Any]:
        if self.catalog_id:
            return self.catalog_id
        if self.io is not None:
            from tools.lab.freeze_m0 import bch_io

            n_in, n_out, change = self.io
            return bch_io(self.id, n_in, n_out, change=change)
        if self.config is not None:
            return dict(self.config)
        return self.id


SCENARIOS: list[Scenario] = [
    # Transfer — default first. Format is always v145; this only picks the tx.
    Scenario("IO-1-1", "Simple transfer", "Transfer", "1-in 1-out BCH payment", "none", io=(1, 1, False)),
    Scenario("IO-1-2", "1-in 2-out", "Transfer", "Payment + change", "none", io=(1, 2, True)),
    Scenario("IO-2-1", "2-in 1-out", "Transfer", "Two inputs, one payment", "none", io=(2, 1, False)),
    Scenario("IO-2-2", "2-in 2-out", "Transfer", "Two inputs, payment + change", "none", io=(2, 2, True)),
    Scenario("IO-2-3", "2-in 3-out", "Transfer", "Two inputs, three outputs", "none", io=(2, 3, True)),
    Scenario("IO-3-2", "3-in 2-out", "Transfer", "Three inputs, payment + change", "none", io=(3, 2, True)),
    Scenario("SCR-05", "OP_RETURN", "Transfer", "OP_RETURN before payment (WYSIWYS)", "none", catalog_id="SCR-05"),
    # Genesis
    Scenario("GEN-04", "Genesis FT", "Genesis", "Fungible token genesis", "FT genesis", catalog_id="GEN-04"),
    Scenario("GEN-01", "Genesis NFT immutable", "Genesis", "Immutable NFT genesis", "NFT genesis", catalog_id="GEN-01"),
    Scenario("GEN-02", "Genesis NFT mutable", "Genesis", "Mutable NFT genesis", "NFT genesis", catalog_id="GEN-02"),
    Scenario("GEN-03", "Genesis minting", "Genesis", "Minting-baton genesis", "NFT genesis", catalog_id="GEN-03"),
    Scenario("GEN-05", "Genesis hybrid", "Genesis", "NFT + FT genesis", "hybrid genesis", catalog_id="GEN-05"),
    # Post-genesis
    Scenario("VOUT0-NO-GENESIS", "FT transfer", "Post-genesis", "FT move; parent vout ≠ genesis", "FT transfer", catalog_id="VOUT0-NO-GENESIS"),
    Scenario("POST-01", "Minting keep baton", "Post-genesis", "Mint NFT, preserve baton", "mint", catalog_id="POST-01"),
    Scenario("POST-08", "Immutable transfer", "Post-genesis", "Immutable NFT transfer", "NFT transfer", catalog_id="POST-08"),
    # Burn / multi
    Scenario("BURN-MULTI", "FT burn + NFT burn", "Burn / multi", "Burn FT and NFT together", "burn", catalog_id="BURN-MULTI"),
    Scenario("SAMECAT-01", "Same-category FT+NFT", "Burn / multi", "Same category, separate outputs", "FT+NFT", catalog_id="SAMECAT-01"),
    Scenario("XGEN-01", "Multi-category genesis+transfer", "Burn / multi", "Genesis one category, transfer another", "genesis+transfer", catalog_id="XGEN-01"),
    # Complex
    Scenario("MONSTER-03", "DeFi-like swap", "Complex", "Multi-party token swap shape", "mixed", catalog_id="MONSTER-03"),
    Scenario("MONSTER-01", "Monster", "Complex", "MONSTER-01 multi-input/output", "mixed", catalog_id="MONSTER-01"),
    Scenario("MONSTER-05", "Monster 05", "Complex", "MONSTER-05", "mixed", catalog_id="MONSTER-05"),
    # Wire sample of a v145 blob — still a scenario, not a format.
    Scenario("PSBT-02", "Reference sample TX", "Samples", "Canonical Paytaca-shaped sample transaction", "mixed", catalog_id="PSBT-02"),
]

SCENARIO_BY_ID: dict[str, Scenario] = {s.id: s for s in SCENARIOS}

# (label, id) — same surface as the old preset list, now explicitly scenarios.
CATALOG_PRESETS: list[tuple[str, str]] = [(s.label, s.id) for s in SCENARIOS]


def get_scenario(ident: str) -> Scenario:
    if ident in SCENARIO_BY_ID:
        return SCENARIO_BY_ID[ident]
    # Catalog-only ids (fixtures tree) become anonymous scenarios.
    return Scenario(ident, ident, "Catalog", ident, "catalog", catalog_id=ident)


def scenario_engine_source(ident: str) -> str | dict[str, Any]:
    return get_scenario(ident).engine_source()


def simple_bch() -> BuilderState:
    """Default builder: Simple transfer. Format is the lab invariant, not this preset."""
    s = BuilderState()
    s.scenario_id = DEFAULT_SCENARIO_ID
    s.scenario_label = "Simple transfer"
    s.inputs = [InputUI(key="A", kind="bch", owner="alice", vout=0, sats=50_000)]
    s.outputs = [OutputUI(owner="bob", sats=48_000, token=TokenUI(kind="none"))]
    return s


def genesis_nft() -> BuilderState:
    s = BuilderState()
    s.scenario_id = "GEN-01"
    s.scenario_label = "Genesis NFT immutable"
    s.inputs = [InputUI(key="A", kind="genesis_parent", sats=100_000)]
    s.outputs = [
        OutputUI(
            sats=98_000,
            genesis_from=0,
            token=TokenUI(kind="nft", nft="immutable", commitment="cafebabe", category_mode="auto"),
        )
    ]
    return s


def _token_from_spec(tspec: dict | None) -> TokenUI:
    tok = TokenUI(kind="none")
    if not tspec:
        return tok
    tok.kind = "hybrid" if tspec.get("amount") and tspec.get("nft") else (
        "ft" if tspec.get("amount") else "nft"
    )
    tok.ft_amount = int(tspec.get("amount") or 0)
    nft = tspec.get("nft") or {}
    if isinstance(nft, dict):
        cap = nft.get("capability") or "none"
        tok.nft = {"none": "immutable", "mutable": "mutable", "minting": "minting"}.get(cap, "immutable")
        tok.commitment = str(nft.get("commitment") or "")
    return tok


def builder_from_spec(sc: dict[str, Any], *, scenario_id: str = "", scenario_label: str = "") -> BuilderState:
    """Map a semantic spec into builder widgets. Never copies a dialect from the catalog."""
    st = BuilderState()
    st.scenario_id = scenario_id or sc.get("id") or ""
    st.scenario_label = scenario_label or sc.get("title") or st.scenario_id
    st.sign = (sc.get("sign_states") or [sc.get("sign_state") or "unsigned"])[0]
    ins: list[InputUI] = []
    for i, spec in enumerate(sc.get("inputs") or []):
        tok = _token_from_spec(spec.get("token") if isinstance(spec.get("token"), dict) else None)
        kind = spec.get("kind", "bch")
        ins.append(
            InputUI(
                key=spec.get("key") or f"I{i}",
                kind=kind,
                owner=spec.get("owner", "alice"),
                sats=int(spec.get("sats") or 10000),
                vout=int(spec.get("vout") or (1 if kind == "token" else 0)),
                token=tok if kind == "token" else TokenUI(),
            )
        )
        if kind == "token":
            grp = None
            for ex in sc.get("existing") or []:
                if ex.get("key") == spec.get("key"):
                    grp = ex.get("category_group") or spec.get("key")
                    et = ex.get("token") or {}
                    if isinstance(et, dict):
                        ins[-1].token = _token_from_spec(et)
                    ins[-1].token.category_mode = "group"
                    ins[-1].token.category_group = str(grp or "A")
    st.inputs = ins or st.inputs
    outs: list[OutputUI] = []
    for spec in sc.get("outputs") or []:
        tspec = spec.get("token") if isinstance(spec.get("token"), dict) else None
        tok = _token_from_spec(tspec)
        if tspec:
            if spec.get("genesis_from") is not None:
                tok.category_mode = "auto"
            elif tspec.get("category_from_existing"):
                tok.category_mode = "group"
                tok.category_group = str(tspec.get("category_from_existing"))
        outs.append(
            OutputUI(
                owner=spec.get("owner", "bob"),
                sats=int(spec.get("sats") or 1000),
                script=spec.get("script") or sc.get("script_type") or "p2pkh",
                genesis_from=spec.get("genesis_from"),
                existing_key=str((tspec or {}).get("category_from_existing") or ""),
                token=tok,
            )
        )
    st.outputs = outs or st.outputs
    return st


def builder_from_catalog(ident: str) -> BuilderState:
    """Load a scenario into the builder. Format stays v145 regardless of catalog dialects[]."""
    scn = get_scenario(ident)
    src = scn.engine_source()
    if isinstance(src, dict):
        return builder_from_spec(src, scenario_id=scn.id, scenario_label=scn.label)
    from ctlab.vectors.catalog import build_catalog

    row = next(s for s in build_catalog() if s["id"] == src)
    return builder_from_spec(row, scenario_id=scn.id, scenario_label=scn.label)


RANDOM_POOL = {
    "Simple": ["IO-1-1", "GEN-04", "GEN-01", "VOUT0-NO-GENESIS"],
    "Medium": ["GEN-05", "POST-01", "SAMECAT-01", "BURN-MULTI"],
    "Complex": ["XGEN-01", "MONSTER-03", "MONSTER-02", "VOUT0-NO-GENESIS"],
    "Monster": ["MONSTER-01", "MONSTER-05", "MONSTER-04"],
}
