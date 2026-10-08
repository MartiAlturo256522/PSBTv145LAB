"""CashAddr encoding (spec + CHIP-2022-02 token-aware version bytes).

Token-aware addresses are ADDRESS ENCODING ONLY. The on-chain locking
bytecode of a token-bearing P2PKH output is still standard P2PKH
(OP_DUP OP_HASH160 <20> OP_EQUALVERIFY OP_CHECKSIG) with a CashTokens
prefix prepended to the locking bytecode in the output serialization.
"""

from __future__ import annotations

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
CHARSET_MAP = {c: i for i, c in enumerate(CHARSET)}

# CHIP-2022-02 CashAddress version bytes
VERSION = {
    "p2pkh": 0x00,
    "p2sh20": 0x08,
    "p2sh32": 0x0B,
    "p2pkh_token": 0x10,
    "p2sh20_token": 0x18,
    "p2sh32_token": 0x1B,
}


def version_byte_for(script_type: str, token_aware: bool) -> int:
    key = script_type
    if token_aware:
        key = {
            "p2pkh": "p2pkh_token",
            "p2sh20": "p2sh20_token",
            "p2sh32": "p2sh32_token",
        }.get(script_type, script_type)
    if key not in VERSION:
        raise ValueError(f"unknown script type {script_type!r}")
    return VERSION[key]


def _polymod(values: list[int]) -> int:
    generators = [
        0x98F2BC8E61,
        0x79B76D99E2,
        0xF33E5FB3C4,
        0xAE2EABE2A8,
        0x1E4F43E470,
    ]
    c = 1
    for d in values:
        c0 = c >> 35
        c = ((c & 0x07FFFFFFFF) << 5) ^ d
        for i in range(5):
            if (c0 >> i) & 1:
                c ^= generators[i]
    return c


def _prefix_expand(prefix: str) -> list[int]:
    return [ord(x) & 0x1F for x in prefix] + [0]


def convertbits(data: bytes | list[int], frombits: int, tobits: int, pad: bool = True) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("invalid convertbits value")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid convertbits padding")
    return ret


def encode_cashaddr(payload: bytes, version_byte: int, prefix: str = "bitcoincash") -> str:
    data8 = bytes([version_byte]) + payload
    payload5 = convertbits(data8, 8, 5, pad=True)
    checksum_input = _prefix_expand(prefix) + payload5 + [0] * 8
    polymod = _polymod(checksum_input) ^ 1
    checksum = [(polymod >> 5 * (7 - i)) & 31 for i in range(8)]
    return prefix + ":" + "".join(CHARSET[d] for d in payload5 + checksum)


def decode_cashaddr(address: str) -> tuple[str, int, bytes]:
    addr = address.lower()
    if ":" not in addr:
        raise ValueError("cashaddr missing prefix")
    prefix, body = addr.split(":", 1)
    if any(c not in CHARSET_MAP for c in body):
        raise ValueError("invalid cashaddr charset")
    values = [CHARSET_MAP[c] for c in body]
    if _polymod(_prefix_expand(prefix) + values) != 1:
        raise ValueError("invalid cashaddr checksum")
    data8 = bytes(convertbits(values[:-8], 5, 8, pad=False))
    if not data8:
        raise ValueError("empty cashaddr payload")
    return prefix, data8[0], data8[1:]
