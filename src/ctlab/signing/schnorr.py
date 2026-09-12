"""Bitcoin Cash Schnorr (2019), NOT BIP-340.

Challenge: e = SHA256(r || compressed_pubkey || m)  (untagged)
R is disambiguated by Jacobi symbol of Y == 1 (quadratic residue).
Signature is 64 bytes r||s; wallets append a 1-byte hashtype.
"""

from __future__ import annotations

import hashlib

import ecdsa
from ecdsa.util import number_to_string


def sign_schnorr_bch(private_key: bytes, msg_hash: bytes, public_key: bytes) -> bytes:
    d = int.from_bytes(private_key, "big")
    order = ecdsa.SECP256k1.order
    field_prime = ecdsa.SECP256k1.curve.p()
    if d <= 0 or d >= order:
        raise ValueError("invalid private key")
    if len(msg_hash) != 32:
        raise ValueError("msg_hash must be 32 bytes")
    if len(public_key) != 33:
        raise ValueError("public_key must be compressed")

    k = ecdsa.rfc6979.generate_k(order, d, hashlib.sha256, msg_hash, extra_entropy=b"")
    G = ecdsa.SECP256k1.generator
    R = k * G
    if pow(R.y(), (field_prime - 1) // 2, field_prime) != 1:
        k = order - k
        R = k * G
    r_int = R.x()
    if r_int == 0:
        raise ValueError("r is zero")
    r_bytes = number_to_string(r_int, order)
    e = int.from_bytes(hashlib.sha256(r_bytes + public_key + msg_hash).digest(), "big") % order
    s = (k + e * d) % order
    if s == 0:
        raise ValueError("s is zero")
    return r_bytes + number_to_string(s, order)


def verify_schnorr_bch(public_key: bytes, msg_hash: bytes, signature: bytes) -> bool:
    if len(signature) < 64 or len(public_key) != 33 or len(msg_hash) != 32:
        return False
    sig = signature[:64]
    r = int.from_bytes(sig[:32], "big")
    s = int.from_bytes(sig[32:], "big")
    order = ecdsa.SECP256k1.order
    field_prime = ecdsa.SECP256k1.curve.p()
    if r == 0 or s == 0 or s >= order:
        return False
    e = int.from_bytes(hashlib.sha256(sig[:32] + public_key + msg_hash).digest(), "big") % order
    G = ecdsa.SECP256k1.generator
    try:
        P = ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1).pubkey.point
    except Exception:
        return False
    R = s * G + (order - e) * P
    if R.x() != r:
        return False
    if pow(R.y(), (field_prime - 1) // 2, field_prime) != 1:
        return False
    return True
