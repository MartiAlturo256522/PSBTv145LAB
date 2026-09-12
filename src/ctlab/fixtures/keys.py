"""Deterministic BIP-39 / BIP-32 / BIP-44 keys for the laboratory.

Mnemonic is the BIP-39 test vector:
    abandon × 11 + about
Path: m/44'/145'/0'/change/index
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from ecdsa import SECP256k1, SigningKey

from ctlab import LAB_ACCOUNT, LAB_COIN_TYPE, LAB_MNEMONIC, LAB_PASSPHRASE
from ctlab.protocol.cashaddr import encode_cashaddr, version_byte_for
from ctlab.protocol.hashes import hash160
from ctlab.transactions.serialize import p2pkh_script

HARDENED = 0x80000000


def mnemonic_to_seed(mnemonic: str = LAB_MNEMONIC, passphrase: str = LAB_PASSPHRASE) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic.encode("utf-8"),
        ("mnemonic" + passphrase).encode("utf-8"),
        2048,
        dklen=64,
    )


def master_from_seed(seed: bytes) -> tuple[bytes, bytes]:
    I = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    return I[:32], I[32:]


def _ckd_priv(parent_key: bytes, parent_cc: bytes, index: int) -> tuple[bytes, bytes]:
    order = SECP256k1.order
    if index & HARDENED:
        data = b"\x00" + parent_key + index.to_bytes(4, "big")
    else:
        data = private_to_public(parent_key) + index.to_bytes(4, "big")
    I = hmac.new(parent_cc, data, hashlib.sha512).digest()
    IL, IR = I[:32], I[32:]
    child = (int.from_bytes(IL, "big") + int.from_bytes(parent_key, "big")) % order
    if child == 0:
        raise ValueError("derived key is zero")
    return child.to_bytes(32, "big"), IR


def private_to_public(priv: bytes) -> bytes:
    return SigningKey.from_string(priv, curve=SECP256k1).verifying_key.to_string("compressed")


def derive_path(path: str, seed: bytes | None = None) -> tuple[bytes, bytes]:
    if seed is None:
        seed = mnemonic_to_seed()
    key, cc = master_from_seed(seed)
    if path in ("m", "M", ""):
        return key, cc
    if not path.startswith("m/"):
        raise ValueError(path)
    for part in path[2:].split("/"):
        hardened = part.endswith("'") or part.endswith("h")
        n = int(part[:-1] if hardened else part)
        if hardened:
            n |= HARDENED
        key, cc = _ckd_priv(key, cc, n)
    return key, cc


def fingerprint(priv: bytes) -> bytes:
    return hash160(private_to_public(priv))[:4]


@dataclass(frozen=True)
class Actor:
    name: str
    index: int
    change: int
    priv: bytes
    pub: bytes
    pkhash: bytes
    path: list[int]
    path_str: str

    def p2pkh(self) -> bytes:
        return p2pkh_script(self.pkhash)

    def address(self, token_aware: bool = False, prefix: str = "bitcoincash") -> str:
        return encode_cashaddr(self.pkhash, version_byte_for("p2pkh", token_aware), prefix)


def actor(name: str, index: int, change: int = 0) -> Actor:
    path_str = f"m/44'/{LAB_COIN_TYPE}'/{LAB_ACCOUNT}'/{change}/{index}"
    priv, _cc = derive_path(path_str)
    pub = private_to_public(priv)
    path = [
        44 | HARDENED,
        LAB_COIN_TYPE | HARDENED,
        LAB_ACCOUNT | HARDENED,
        change,
        index,
    ]
    return Actor(
        name=name,
        index=index,
        change=change,
        priv=priv,
        pub=pub,
        pkhash=hash160(pub),
        path=path,
        path_str=path_str,
    )


ALICE = actor("alice", 0)
BOB = actor("bob", 1)
CAROL = actor("carol", 2)
DAVE = actor("dave", 3)
CHANGE = actor("change", 0, change=1)

ACTORS = {"alice": ALICE, "bob": BOB, "carol": CAROL, "dave": DAVE, "change": CHANGE}


def master_fingerprint() -> bytes:
    seed = mnemonic_to_seed()
    priv, _ = master_from_seed(seed)
    return fingerprint(priv)
