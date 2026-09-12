"""Signer-facing semantic interpretation of a CashTokens transaction.

Derived only from unsigned transaction + source UTXOs. Never from
Paytaca PSBT_OUT_CASHTOKEN (0x36) or proprietary metadata.
"""

from __future__ import annotations

from typing import Any, Optional

from ctlab.cashtokens.consensus import validate_transaction_tokens
from ctlab.cashtokens.prefix import Token


def _genesis_categories(inputs: list[dict]) -> list[str]:
    cats = []
    for inp in inputs:
        if int(inp["prev_index"]) == 0:
            cats.append(inp["prev_txid"][::-1].hex())
    return cats


def interpret_token_semantics(inputs: list[dict], outputs: list[dict]) -> dict[str, Any]:
    genesis_ids = _genesis_categories(inputs)
    genesis_set = set(genesis_ids)

    validation = validate_transaction_tokens(inputs, outputs)

    by_cat_in: dict[str, dict[str, Any]] = {}
    by_cat_out: dict[str, dict[str, Any]] = {}

    def bucket(store: dict, tok: Token) -> dict:
        b = store.setdefault(
            tok.category,
            {"ft_in": 0, "ft_out": 0, "nfts_in": [], "nfts_out": []},
        )
        return b

    for inp in inputs:
        tok: Optional[Token] = inp.get("token")
        if not tok:
            continue
        b = bucket(by_cat_in, tok)
        b["ft_in"] += tok.amount
        if tok.nft:
            b["nfts_in"].append(
                {"capability": tok.nft.capability, "commitment": tok.nft.commitment.hex()}
            )

    for out in outputs:
        tok = out.get("token")
        if not tok:
            continue
        b = bucket(by_cat_out, tok)
        b["ft_out"] += tok.amount
        if tok.nft:
            b["nfts_out"].append(
                {"capability": tok.nft.capability, "commitment": tok.nft.commitment.hex()}
            )

    categories = sorted(set(by_cat_in) | set(by_cat_out) | genesis_set)

    genesis: list[dict] = []
    mint: list[dict] = []
    transfers: list[dict] = []
    burns: list[dict] = []
    mutations: list[dict] = []

    for cat in categories:
        inn = by_cat_in.get(cat, {"ft_in": 0, "nfts_in": []})
        out = by_cat_out.get(cat, {"ft_out": 0, "nfts_out": []})
        is_genesis = cat in genesis_set

        ft_in = inn.get("ft_in", 0)
        ft_out = out.get("ft_out", 0)
        nfts_in = list(inn.get("nfts_in", []))
        nfts_out = list(out.get("nfts_out", []))

        if is_genesis:
            genesis.append(
                {
                    "category": cat,
                    "ft_amount": ft_out,
                    "nfts": nfts_out,
                    "type": _classify(ft_out, nfts_out),
                }
            )
            # Additional minting of *this new* category in the same tx is genesis, not post-genesis mint.
            continue

        has_minting_in = any(n["capability"] == "minting" for n in nfts_in)
        minting_in = [n for n in nfts_in if n["capability"] == "minting"]
        minting_out = [n for n in nfts_out if n["capability"] == "minting"]
        mutable_in = [n for n in nfts_in if n["capability"] == "mutable"]
        mutable_out = [n for n in nfts_out if n["capability"] == "mutable"]
        imm_in = [n for n in nfts_in if n["capability"] == "none"]
        imm_out = [n for n in nfts_out if n["capability"] == "none"]

        if has_minting_in and (len(nfts_out) > len(nfts_in) or any(
            o not in nfts_in for o in nfts_out
        )):
            mint.append(
                {
                    "category": cat,
                    "minting_in": minting_in,
                    "minting_out": minting_out,
                    "nfts_out": nfts_out,
                    "baton": _baton_fate(minting_in, minting_out, mutable_out, nfts_out),
                }
            )

        # Mutable commitment rewrite / downgrade
        if mutable_in:
            mutations.append(
                {
                    "category": cat,
                    "mutable_in": mutable_in,
                    "mutable_out": mutable_out,
                    "immutable_out_unmatched": [
                        n for n in imm_out if n not in imm_in
                    ],
                }
            )

        if ft_out > 0 or (nfts_out and not is_genesis):
            transfers.append(
                {
                    "category": cat,
                    "ft_in": ft_in,
                    "ft_out": ft_out,
                    "nfts_in": nfts_in,
                    "nfts_out": nfts_out,
                }
            )

        ft_burned = max(ft_in - ft_out, 0)
        nft_burned = []
        remaining_imm_out = list(imm_out)
        for n in imm_in:
            if n in remaining_imm_out:
                remaining_imm_out.remove(n)
            else:
                nft_burned.append(n)
        baton_burned = bool(minting_in) and not minting_out
        if ft_burned or nft_burned or (nfts_in and not nfts_out and not is_genesis):
            burns.append(
                {
                    "category": cat,
                    "kind": "token",
                    "ft_burned": ft_burned,
                    "nfts_dropped": nft_burned,
                    "implicit": True,
                }
            )
        if baton_burned:
            burns.append(
                {
                    "category": cat,
                    "kind": "baton",
                    "capability": "minting",
                    "ft_burned": 0,
                    "nfts_dropped": minting_in,
                    "implicit": True,
                }
            )

    return {
        "valid": validation.ok,
        "invalid_reason": validation.reason,
        "invalid_code": validation.code,
        "genesis_categories": genesis_ids,
        "categories": categories,
        "genesis": genesis,
        "mint": mint,
        "transfers": transfers,
        "burns": burns,
        "mutations": mutations,
        "cross_category": len(categories) > 1,
    }


def _classify(ft_amount: int, nfts: list) -> str:
    has_nft = bool(nfts)
    has_ft = ft_amount > 0
    if has_nft and has_ft:
        return "hybrid"
    if has_nft:
        caps = {n["capability"] for n in nfts}
        if caps == {"none"}:
            return "NFT"
        if caps == {"mutable"}:
            return "NFT-mutable"
        if caps == {"minting"}:
            return "NFT-minting"
        return "NFT-mixed"
    if has_ft:
        return "FT"
    return "empty"


def _baton_fate(minting_in, minting_out, mutable_out, nfts_out) -> str:
    if minting_out:
        return "preserved"
    if mutable_out and not minting_out:
        return "downgraded"
    if not minting_out and not any(n["capability"] == "minting" for n in nfts_out):
        return "burned"
    return "unknown"
