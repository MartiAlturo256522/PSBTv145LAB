"""CashTokens consensus validation algorithm (CHIP-2022-02 v2.2.2).

Implements the same algorithm as libauth ``verifyTransactionTokens``.
This is independent of PSBT encoding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ctlab.cashtokens.prefix import MAX_COMMITMENT_CONSENSUS, MAX_FT_AMOUNT, Token


@dataclass
class TokenValidationResult:
    ok: bool
    reason: Optional[str] = None
    code: Optional[str] = None

    @property
    def status(self) -> str:
        return "valid" if self.ok else "invalid"


def _category_hex_from_outpoint_hash_internal(prev_txid_internal: bytes) -> str:
    """prev_txid_internal is HASH256/P2P order (as serialized in the tx input).

    Libauth stores outpoint hashes in UI order. We store them in wire/P2P
    order in TxInput.prev_txid. Display/UI category = reverse(wire).
    """
    return prev_txid_internal[::-1].hex()


def validate_transaction_tokens(
    inputs: list[dict],
    outputs: list[dict],
) -> TokenValidationResult:
    """Validate CashTokens conservation.

    ``inputs`` items:
        prev_txid: bytes (P2P/HASH256 order, 32 bytes)
        prev_index: int
        token: Token | None  (spent output token, in-memory UI category)

    ``outputs`` items:
        token: Token | None
    """
    from ctlab.cashtokens.prefix import PREFIX_TOKEN, TokenPrefixError, decode_token_prefix

    # An output whose script field starts with PREFIX_TOKEN but does not parse
    # as a valid prefix invalidates the transaction (CHIP, post-activation).
    for i, item in enumerate(outputs):
        field = item.get("script_field")
        if field and field[:1] == bytes([PREFIX_TOKEN]):
            try:
                decode_token_prefix(field)
            except TokenPrefixError as e:
                return TokenValidationResult(False, str(e), e.code)

    # Commitment length consensus limit (parse may have already succeeded).
    for side, items in (("input", inputs), ("output", outputs)):
        for i, item in enumerate(items):
            tok: Optional[Token] = item.get("token")
            if tok and tok.nft and len(tok.nft.commitment) > MAX_COMMITMENT_CONSENSUS:
                return TokenValidationResult(
                    False,
                    f"{side} {i} commitment length {len(tok.nft.commitment)} exceeds {MAX_COMMITMENT_CONSENSUS}",
                    "commitment_too_long",
                )

    genesis_categories: list[str] = []
    for inp in inputs:
        if int(inp["prev_index"]) == 0:
            genesis_categories.append(_category_hex_from_outpoint_hash_internal(inp["prev_txid"]))

    available_sums: dict[str, int] = {}
    available_mutable: dict[str, int] = {}
    input_minting: list[str] = []
    available_immutable: list[tuple[str, bytes]] = []

    for inp in inputs:
        tok: Optional[Token] = inp.get("token")
        if tok is None:
            continue
        cat = tok.category
        available_sums[cat] = available_sums.get(cat, 0) + tok.amount
        if tok.nft:
            if tok.nft.capability == "minting":
                input_minting.append(cat)
            elif tok.nft.capability == "mutable":
                available_mutable[cat] = available_mutable.get(cat, 0) + 1
            else:
                available_immutable.append((cat, tok.nft.commitment))

    output_sums: dict[str, int] = {}
    output_mutable: dict[str, int] = {}
    output_minting: list[str] = []
    output_immutable: list[tuple[str, bytes]] = []

    for out in outputs:
        tok = out.get("token")
        if tok is None:
            continue
        cat = tok.category
        output_sums[cat] = output_sums.get(cat, 0) + tok.amount
        if tok.nft:
            if tok.nft.capability == "minting":
                output_minting.append(cat)
            elif tok.nft.capability == "mutable":
                output_mutable[cat] = output_mutable.get(cat, 0) + 1
            else:
                output_immutable.append((cat, tok.nft.commitment))

    available_minting = set(genesis_categories) | set(input_minting)

    for cat in set(output_minting):
        if cat not in available_minting:
            return TokenValidationResult(
                False,
                f"output minting token category {cat} is not substantiated by genesis or minting inputs",
                "unsubstantiated_minting",
            )

    for cat, total in output_sums.items():
        if total > MAX_FT_AMOUNT:
            return TokenValidationResult(
                False,
                f"FT output sum for {cat} exceeds max VM number ({total})",
                "ft_exceeds_max",
            )
        available = available_sums.get(cat)
        if available is None:
            if total > 0 and cat not in genesis_categories:
                return TokenValidationResult(
                    False,
                    f"creates FT for category {cat} without a matching genesis input",
                    "ft_without_genesis",
                )
        elif total > available:
            return TokenValidationResult(
                False,
                f"FT overspend for {cat}: inputs {available} outputs {total}",
                "ft_overspend",
            )

    remaining_mutable = dict(available_mutable)
    for cat, count in output_mutable.items():
        if cat in available_minting:
            continue
        remaining_mutable[cat] = remaining_mutable.get(cat, 0) - count
        if remaining_mutable[cat] < 0:
            return TokenValidationResult(
                False,
                f"creates more mutable tokens than available for {cat}",
                "mutable_overspend",
            )

    unmatched: list[tuple[str, bytes]] = []
    remaining_imm = list(available_immutable)
    for cat, commitment in output_immutable:
        if cat in available_minting:
            continue
        found = None
        for i, (acat, acom) in enumerate(remaining_imm):
            if acat == cat and acom == commitment:
                found = i
                break
        if found is None:
            unmatched.append((cat, commitment))
        else:
            remaining_imm.pop(found)

    required_mutable: dict[str, int] = {}
    for cat, _c in unmatched:
        required_mutable[cat] = required_mutable.get(cat, 0) + 1
    for cat, required in required_mutable.items():
        available = remaining_mutable.get(cat, 0)
        if available < required:
            return TokenValidationResult(
                False,
                f"immutable token for {cat} lacks matching immutable or mutable to downgrade "
                f"(need {required}, mutable left {available})",
                "immutable_unmatched",
            )

    return TokenValidationResult(True)
