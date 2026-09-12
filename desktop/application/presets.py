"""Presets only populate builder state or catalog ids. Engine still generates."""

from __future__ import annotations

from typing import Any

from desktop.application.builder_model import BuilderState, InputUI, OutputUI, TokenUI

# (label, catalog_id or None, builder factory name)
CATALOG_PRESETS: list[tuple[str, str]] = [
    ("Genesis FT", "GEN-04"),
    ("Genesis NFT immutable", "GEN-01"),
    ("Genesis NFT mutable", "GEN-02"),
    ("Genesis minting", "GEN-03"),
    ("Genesis hybrid", "GEN-05"),
    ("FT transfer (vout≠genesis)", "VOUT0-NO-GENESIS"),
    ("Minting keep baton", "POST-01"),
    ("Immutable transfer", "POST-08"),
    ("FT burn + NFT burn", "BURN-MULTI"),
    ("Same-category FT+NFT", "SAMECAT-01"),
    ("Multi-category genesis+transfer", "XGEN-01"),
    ("DeFi-like swap", "MONSTER-03"),
    ("Monster 01", "MONSTER-01"),
    ("Monster 05", "MONSTER-05"),
    ("Paytaca v145 sample", "PSBT-02"),
]


def simple_bch() -> BuilderState:
    s = BuilderState()
    s.inputs = [InputUI(key="X", kind="bch", vout=1, sats=100_000)]
    s.outputs = [OutputUI(sats=98_000, token=TokenUI(kind="none"))]
    return s


def genesis_nft() -> BuilderState:
    s = BuilderState()
    s.inputs = [InputUI(key="A", kind="genesis_parent", sats=100_000)]
    s.outputs = [
        OutputUI(
            sats=98_000,
            genesis_from=0,
            token=TokenUI(kind="nft", nft="immutable", commitment="cafebabe", category_mode="auto"),
        )
    ]
    return s


def builder_from_catalog(ident: str) -> BuilderState:
    """Map a catalog scenario into builder widgets. Engine still generates bytes."""
    from ctlab.vectors.catalog import build_catalog

    sc = next(s for s in build_catalog() if s["id"] == ident)
    st = BuilderState()
    st.dialect = (sc.get("dialects") or ["paytaca-145"])[0]
    st.sign = (sc.get("sign_states") or ["unsigned"])[0]
    ins: list[InputUI] = []
    for i, spec in enumerate(sc.get("inputs") or []):
        tok = TokenUI()
        tspec = spec.get("token") if isinstance(spec.get("token"), dict) else None
        if tspec:
            tok.kind = "hybrid" if tspec.get("amount") and tspec.get("nft") else (
                "ft" if tspec.get("amount") else "nft"
            )
            tok.ft_amount = int(tspec.get("amount") or 0)
            nft = tspec.get("nft") or {}
            if isinstance(nft, dict):
                cap = nft.get("capability") or "none"
                tok.nft = {"none": "immutable", "mutable": "mutable", "minting": "minting"}.get(cap, "immutable")
                tok.commitment = str(nft.get("commitment") or "")
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
                        ins[-1].token.kind = "hybrid" if et.get("amount") and et.get("nft") else (
                            "ft" if et.get("amount") else "nft"
                        )
                        ins[-1].token.ft_amount = int(et.get("amount") or 0)
                        nft = et.get("nft") or {}
                        if isinstance(nft, dict):
                            cap = nft.get("capability") or "none"
                            ins[-1].token.nft = {
                                "none": "immutable",
                                "mutable": "mutable",
                                "minting": "minting",
                            }.get(cap, "immutable")
                            ins[-1].token.commitment = str(nft.get("commitment") or "")
                    ins[-1].token.category_mode = "group"
                    ins[-1].token.category_group = str(grp or "A")
    st.inputs = ins or st.inputs
    outs: list[OutputUI] = []
    for spec in sc.get("outputs") or []:
        tok = TokenUI(kind="none")
        tspec = spec.get("token") if isinstance(spec.get("token"), dict) else None
        if tspec:
            tok.kind = "hybrid" if tspec.get("amount") and tspec.get("nft") else (
                "ft" if tspec.get("amount") else "nft"
            )
            tok.ft_amount = int(tspec.get("amount") or 0)
            nft = tspec.get("nft") or {}
            if isinstance(nft, dict):
                cap = nft.get("capability") or "none"
                tok.nft = {"none": "immutable", "mutable": "mutable", "minting": "minting"}.get(cap, "immutable")
                tok.commitment = str(nft.get("commitment") or "")
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


RANDOM_POOL = {
    "Simple": ["GEN-04", "GEN-01", "VOUT0-NO-GENESIS"],
    "Medium": ["GEN-05", "POST-01", "SAMECAT-01", "BURN-MULTI"],
    "Complex": ["XGEN-01", "MONSTER-03", "MONSTER-02", "VOUT0-MIXED"],
    "Monster": ["MONSTER-01", "MONSTER-05", "MONSTER-04"],
}
