"""CashTokens token-prefix serialization (CHIP-2022-02 v2.2.2).

This module is the encoding layer only. Consensus conservation lives in
``consensus.py``. A prefix may be a valid encoding of an output that is
still consensus-invalid (e.g. 41-byte commitment).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ctlab.protocol.compact_size import (
    CompactSizeError,
    decode_compact_size,
    encode_compact_size,
    is_minimal_compact_size,
)

PREFIX_TOKEN = 0xEF
HAS_AMOUNT = 0x10
HAS_NFT = 0x20
HAS_COMMITMENT_LENGTH = 0x40
RESERVED_BIT = 0x80
MAX_FT_AMOUNT = 9223372036854775807
MAX_COMMITMENT_CONSENSUS = 40
CAPABILITY = {"none": 0, "mutable": 1, "minting": 2}
CAPABILITY_NAME = {0: "none", 1: "mutable", 2: "minting"}


class TokenPrefixError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TokenNft:
    capability: str  # none | mutable | minting
    commitment: bytes = b""


@dataclass(frozen=True)
class Token:
    """In-memory token: category is UI/explorer hex (big-endian txid)."""

    category: str  # 64 hex chars, display order
    amount: int = 0
    nft: Optional[TokenNft] = None

    def has_nft(self) -> bool:
        return self.nft is not None

    def has_ft(self) -> bool:
        return self.amount > 0


def _category_to_wire(category_hex: str) -> bytes:
    raw = bytes.fromhex(category_hex)
    if len(raw) != 32:
        raise TokenPrefixError("category_length", "category must be 32 bytes")
    return raw[::-1]


def _category_from_wire(wire: bytes) -> str:
    if len(wire) != 32:
        raise TokenPrefixError("category_length", "category must be 32 bytes")
    return wire[::-1].hex()


def encode_token_prefix(token: Optional[Token]) -> bytes:
    """Encode a token as PREFIX_TOKEN ... or b'' if no tokens.

    Matches libauth ``encodeTokenPrefix``.
    """
    if token is None:
        return b""
    if token.nft is None and token.amount < 1:
        return b""
    if token.amount < 0:
        raise TokenPrefixError("negative_amount", "FT amount cannot be negative")
    if token.amount > MAX_FT_AMOUNT:
        raise TokenPrefixError("excessive_amount", "FT amount exceeds max VM number")

    has_nft = HAS_NFT if token.nft is not None else 0
    cap = 0
    has_commitment = 0
    if token.nft is not None:
        if token.nft.capability not in CAPABILITY:
            raise TokenPrefixError("invalid_capability", token.nft.capability)
        cap = CAPABILITY[token.nft.capability]
        if len(token.nft.commitment) > 0:
            has_commitment = HAS_COMMITMENT_LENGTH
    has_amount = HAS_AMOUNT if token.amount > 0 else 0
    bitfield = has_nft | has_commitment | has_amount | cap

    parts = [bytes([PREFIX_TOKEN]), _category_to_wire(token.category), bytes([bitfield])]
    if has_commitment:
        commit = token.nft.commitment  # type: ignore[union-attr]
        parts.append(encode_compact_size(len(commit)))
        parts.append(commit)
    if has_amount:
        parts.append(encode_compact_size(token.amount))
    return b"".join(parts)


def decode_token_prefix(script: bytes) -> tuple[Optional[Token], bytes, bytes]:
    """Decode a locking-bytecode field that may start with PREFIX_TOKEN.

    Returns ``(token_or_none, prefix_bytes, locking_bytecode)``.

    Prefix *parse* validity is separate from consensus commitment-length
    limits: 41-byte commitments parse, then fail consensus.
    """
    if not script or script[0] != PREFIX_TOKEN:
        return None, b"", script
    if len(script) < 34:
        raise TokenPrefixError("insufficient_length", "token prefix shorter than 34 bytes")
    category_wire = script[1:33]
    bitfield = script[33]
    pos = 34

    if bitfield & RESERVED_BIT:
        raise TokenPrefixError("reserved_bit", "reserved bit is set")

    has_commitment = bool(bitfield & HAS_COMMITMENT_LENGTH)
    has_nft = bool(bitfield & HAS_NFT)
    has_amount = bool(bitfield & HAS_AMOUNT)
    capability_bits = bitfield & 0x0F

    if not has_nft and not has_amount:
        raise TokenPrefixError("no_tokens", "token prefix must encode at least one token")
    if has_commitment and not has_nft:
        raise TokenPrefixError("commitment_without_nft", "commitment requires an NFT")
    if not has_nft and capability_bits != 0:
        raise TokenPrefixError("capability_without_nft", "capability requires an NFT")
    if has_nft and capability_bits > 2:
        raise TokenPrefixError("invalid_capability", f"capability {capability_bits} reserved")

    nft: Optional[TokenNft] = None
    if has_nft:
        commitment = b""
        if has_commitment:
            try:
                length, pos, raw_len = decode_compact_size(script, pos)
            except CompactSizeError as e:
                raise TokenPrefixError("invalid_commitment", str(e)) from e
            if not is_minimal_compact_size(raw_len, length):
                raise TokenPrefixError("nonminimal_commitment_length", "commitment length not minimal")
            if length < 1:
                raise TokenPrefixError("commitment_length_zero", "commitment length must be > 0")
            if pos + length > len(script):
                raise TokenPrefixError("truncated_commitment", "not enough bytes for commitment")
            commitment = script[pos : pos + length]
            pos += length
        nft = TokenNft(capability=CAPABILITY_NAME[capability_bits], commitment=commitment)

    amount = 0
    if has_amount:
        try:
            amount, pos, raw_amt = decode_compact_size(script, pos)
        except CompactSizeError as e:
            raise TokenPrefixError("invalid_amount_encoding", str(e)) from e
        if not is_minimal_compact_size(raw_amt, amount):
            raise TokenPrefixError("nonminimal_amount", "FT amount not minimally encoded")
        if amount == 0:
            raise TokenPrefixError("zero_amount", "if encoded, FT amount must be > 0")
        if amount > MAX_FT_AMOUNT:
            raise TokenPrefixError("excessive_amount", "FT amount exceeds max VM number")

    prefix = script[:pos]
    locking = script[pos:]
    token = Token(category=_category_from_wire(category_wire), amount=amount, nft=nft)
    return token, prefix, locking
