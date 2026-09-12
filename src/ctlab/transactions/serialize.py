"""Bitcoin Cash transaction serialization with CashTokens prefixes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ctlab.cashtokens.prefix import Token, decode_token_prefix, encode_token_prefix
from ctlab.protocol.compact_size import decode_compact_size, encode_compact_size
from ctlab.protocol.hashes import hash160, txid_display_hex, txid_internal


@dataclass
class TxIn:
    prev_txid: bytes  # 32 bytes, P2P/HASH256 order (as serialized)
    prev_index: int
    script_sig: bytes = b""
    sequence: int = 0xFFFFFFFF
    spent_output: Optional["TxOut"] = None


@dataclass
class TxOut:
    value_sats: int
    locking_bytecode: bytes
    token: Optional[Token] = None
    redeem_script: Optional[bytes] = None

    def script_field(self) -> bytes:
        """token prefix || locking bytecode (the CompactSize-covered field)."""
        return encode_token_prefix(self.token) + self.locking_bytecode


@dataclass
class Transaction:
    version: int = 2
    inputs: list[TxIn] = field(default_factory=list)
    outputs: list[TxOut] = field(default_factory=list)
    locktime: int = 0

    def serialize(self) -> bytes:
        return encode_transaction(self)

    def txid_internal(self) -> bytes:
        return txid_internal(self.serialize())

    def txid_hex(self) -> str:
        return txid_display_hex(self.serialize())


def p2pkh_script(pubkey_or_hash: bytes) -> bytes:
    h = pubkey_or_hash if len(pubkey_or_hash) == 20 else hash160(pubkey_or_hash)
    return b"\x76\xa9\x14" + h + b"\x88\xac"


def p2sh20_script(script_hash: bytes) -> bytes:
    if len(script_hash) != 20:
        raise ValueError("P2SH20 hash must be 20 bytes")
    return b"\xa9\x14" + script_hash + b"\x87"


def p2sh32_script(script_hash: bytes) -> bytes:
    if len(script_hash) != 32:
        raise ValueError("P2SH32 hash must be 32 bytes")
    return b"\xaa\x20" + script_hash + b"\x87"


def locking_script(script_type: str, payload: bytes) -> bytes:
    if script_type == "p2pkh":
        return p2pkh_script(payload)
    if script_type == "p2sh20":
        return p2sh20_script(payload if len(payload) == 20 else hash160(payload))
    if script_type == "p2sh32":
        from ctlab.protocol.hashes import sha256

        h = payload if len(payload) == 32 else sha256(payload)
        return p2sh32_script(h)
    if script_type == "op_return":
        return b"\x6a" + payload
    if script_type == "bare":
        return payload
    raise ValueError(f"unknown script type {script_type}")


def encode_txout(out: TxOut) -> bytes:
    field = out.script_field()
    return out.value_sats.to_bytes(8, "little") + encode_compact_size(len(field)) + field


def encode_transaction(tx: Transaction) -> bytes:
    parts = [tx.version.to_bytes(4, "little"), encode_compact_size(len(tx.inputs))]
    for inp in tx.inputs:
        if len(inp.prev_txid) != 32:
            raise ValueError("prev_txid must be 32 bytes")
        parts.append(inp.prev_txid)
        parts.append(inp.prev_index.to_bytes(4, "little"))
        parts.append(encode_compact_size(len(inp.script_sig)))
        parts.append(inp.script_sig)
        parts.append(inp.sequence.to_bytes(4, "little"))
    parts.append(encode_compact_size(len(tx.outputs)))
    for out in tx.outputs:
        parts.append(encode_txout(out))
    parts.append(tx.locktime.to_bytes(4, "little"))
    return b"".join(parts)


def decode_transaction(raw: bytes) -> Transaction:
    pos = 0
    if len(raw) < 10:
        raise ValueError("transaction too short")
    version = int.from_bytes(raw[0:4], "little")
    pos = 4
    n_in, pos, _ = decode_compact_size(raw, pos)
    inputs: list[TxIn] = []
    for _ in range(n_in):
        prev = raw[pos : pos + 32]
        pos += 32
        prev_index = int.from_bytes(raw[pos : pos + 4], "little")
        pos += 4
        slen, pos, _ = decode_compact_size(raw, pos)
        script_sig = raw[pos : pos + slen]
        pos += slen
        sequence = int.from_bytes(raw[pos : pos + 4], "little")
        pos += 4
        inputs.append(TxIn(prev_txid=prev, prev_index=prev_index, script_sig=script_sig, sequence=sequence))
    n_out, pos, _ = decode_compact_size(raw, pos)
    outputs: list[TxOut] = []
    for _ in range(n_out):
        value = int.from_bytes(raw[pos : pos + 8], "little")
        pos += 8
        flen, pos, _ = decode_compact_size(raw, pos)
        field = raw[pos : pos + flen]
        pos += flen
        from ctlab.cashtokens.prefix import TokenPrefixError

        try:
            token, _prefix, locking = decode_token_prefix(field)
        except TokenPrefixError:
            # Keep the raw field so a PSBT can carry a consensus-invalid prefix
            # without the envelope decoder destroying the bytes.
            token, locking = None, field
        outputs.append(TxOut(value_sats=value, locking_bytecode=locking, token=token))
    locktime = int.from_bytes(raw[pos : pos + 4], "little")
    return Transaction(version=version, inputs=inputs, outputs=outputs, locktime=locktime)
