from __future__ import annotations

import hashlib


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def double_sha256(data: bytes) -> bytes:
    return sha256(sha256(data))


def hash160(data: bytes) -> bytes:
    ripe = hashlib.new("ripemd160")
    ripe.update(sha256(data))
    return ripe.digest()


def txid_internal(raw_tx: bytes) -> bytes:
    """HASH256 of the serialized transaction (outpoint / prefix byte order)."""
    return double_sha256(raw_tx)


def txid_display_hex(raw_tx: bytes) -> str:
    """Explorer / UI txid: internal HASH256 reversed, hex."""
    return txid_internal(raw_tx)[::-1].hex()
