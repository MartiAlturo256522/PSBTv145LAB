#!/usr/bin/env python3
"""CHIP-2022-02 token-prefix encoder transcribed from the CHIP, not from ctlab.

THIS IS NOT libauth. Live libauth JS is the independent oracle and is
BLOCKED until Node can execute @bitauth/libauth encodeTokenPrefix.

CHIP (cashtokens.org / CHIP-2022-02-CashTokens v2.2.2):

  PREFIX_TOKEN (0xef)
  + category (32 bytes, P2P / HASH256 byte order)
  + bitfield
  + [CompactSize commitment length + commitment] if bit 0x40
  + [CompactSize FT amount] if bit 0x10

Bitfield:
  0x80 reserved, must be 0
  0x40 HAS_COMMITMENT_LENGTH
  0x20 HAS_NFT
  0x10 HAS_AMOUNT
  low nibble: 0 none, 1 mutable, 2 minting, 3+ reserved

Libauth stores category in UI/explorer order and reverses it on encode.
This module takes *wire* category bytes (HASH256 order) so endianness is
explicit and palindrome categories cannot hide a reverse bug.

No imports from ctlab.
"""

from __future__ import annotations

PREFIX_TOKEN = 0xEF
HAS_AMOUNT = 0x10
HAS_NFT = 0x20
HAS_COMMITMENT_LENGTH = 0x40
RESERVED = 0x80
MAX_FT = 9223372036854775807
CAP = {"none": 0, "mutable": 1, "minting": 2}


def compact_size(n: int) -> bytes:
    if n < 0:
        raise ValueError("negative")
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    return b"\xff" + n.to_bytes(8, "little")


def encode_prefix_wire(
    category_wire: bytes,
    amount: int = 0,
    nft_capability: str | None = None,
    commitment: bytes = b"",
) -> bytes:
    if len(category_wire) != 32:
        raise ValueError("category must be 32 wire bytes")
    if amount < 0 or amount > MAX_FT:
        raise ValueError("FT amount out of range")
    has_nft = nft_capability is not None
    if not has_nft and amount < 1:
        return b""
    cap = 0
    has_commit = 0
    if has_nft:
        if nft_capability not in CAP:
            raise ValueError(f"bad capability {nft_capability}")
        cap = CAP[nft_capability]
        if commitment:
            has_commit = HAS_COMMITMENT_LENGTH
    bitfield = (HAS_NFT if has_nft else 0) | has_commit | (HAS_AMOUNT if amount > 0 else 0) | cap
    parts = [bytes([PREFIX_TOKEN]), category_wire, bytes([bitfield])]
    if has_commit:
        parts.append(compact_size(len(commitment)))
        parts.append(commitment)
    if amount > 0:
        parts.append(compact_size(amount))
    return b"".join(parts)


def ui_category_to_wire(ui_hex: str) -> bytes:
    raw = bytes.fromhex(ui_hex)
    if len(raw) != 32:
        raise ValueError("category must be 32 bytes")
    return raw[::-1]
