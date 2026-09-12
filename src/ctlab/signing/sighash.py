"""BCH signing serialization with CashTokens (CHIP-2022-02).

Preimage (replay-protected BIP-143 style):

    version
    hashPrevouts
    [hashUtxos if SIGHASH_UTXOS]     # inserted after hashPrevouts
    hashSequence
    outpoint
    token_prefix                     # full PREFIX_TOKEN encoding, or empty
    compactSize(len(coveredBytecode))
    coveredBytecode                  # scriptCode, NOT including token prefix
    value (8 LE)
    sequence
    hashOutputs
    locktime
    sighash type (4 LE, includes FORKID)

SIGHASH_UTXOS (0x20) MUST be used with FORKID and MUST NOT be combined
with ANYONECANPAY (CHIP consensus: VM evaluation fails).
"""

from __future__ import annotations

from ctlab.cashtokens.prefix import encode_token_prefix
from ctlab.protocol.compact_size import encode_compact_size
from ctlab.protocol.hashes import double_sha256
from ctlab.transactions.serialize import Transaction, TxOut, encode_txout

SIGHASH_ALL = 0x01
SIGHASH_NONE = 0x02
SIGHASH_SINGLE = 0x03
SIGHASH_FORKID = 0x40
SIGHASH_UTXOS = 0x20
SIGHASH_ANYONECANPAY = 0x80

NAMES = {
    SIGHASH_ALL | SIGHASH_FORKID: "ALL|FORKID",
    SIGHASH_NONE | SIGHASH_FORKID: "NONE|FORKID",
    SIGHASH_SINGLE | SIGHASH_FORKID: "SINGLE|FORKID",
    SIGHASH_ALL | SIGHASH_FORKID | SIGHASH_ANYONECANPAY: "ALL|ANYONECANPAY|FORKID",
    SIGHASH_NONE | SIGHASH_FORKID | SIGHASH_ANYONECANPAY: "NONE|ANYONECANPAY|FORKID",
    SIGHASH_SINGLE | SIGHASH_FORKID | SIGHASH_ANYONECANPAY: "SINGLE|ANYONECANPAY|FORKID",
    SIGHASH_ALL | SIGHASH_FORKID | SIGHASH_UTXOS: "ALL|FORKID|UTXOS",
    SIGHASH_NONE | SIGHASH_FORKID | SIGHASH_UTXOS: "NONE|FORKID|UTXOS",
    SIGHASH_SINGLE | SIGHASH_FORKID | SIGHASH_UTXOS: "SINGLE|FORKID|UTXOS",
}


def sighash_name(ht: int) -> str:
    return NAMES.get(ht, f"0x{ht:02x}")


def parse_sighash(name: str) -> int:
    name = name.upper().replace(" ", "")
    for k, v in NAMES.items():
        if v == name:
            return k
    if name.startswith("0X"):
        return int(name, 16)
    raise ValueError(f"unknown sighash {name}")


def _serialize_utxo(out: TxOut) -> bytes:
    return encode_txout(out)


def sighash_bch(
    tx: Transaction,
    input_index: int,
    covered_bytecode: bytes,
    hash_type: int,
    source_outputs: list[TxOut],
) -> tuple[bytes, bytes]:
    """Return (digest, preimage).

    Raises ValueError for CHIP-invalid combinations that a VM would reject
    (UTXOS without FORKID, UTXOS with ANYONECANPAY). Callers generating
    negative vectors may catch this.
    """
    if hash_type & SIGHASH_UTXOS:
        if not (hash_type & SIGHASH_FORKID):
            raise ValueError("SIGHASH_UTXOS requires SIGHASH_FORKID")
        if hash_type & SIGHASH_ANYONECANPAY:
            raise ValueError("SIGHASH_UTXOS cannot be combined with ANYONECANPAY")

    anyone = hash_type & SIGHASH_ANYONECANPAY
    mode = hash_type & 0x1F
    utxos_flag = hash_type & SIGHASH_UTXOS

    if not anyone:
        prevouts = b"".join(i.prev_txid + i.prev_index.to_bytes(4, "little") for i in tx.inputs)
        hash_prevouts = double_sha256(prevouts)
    else:
        hash_prevouts = b"\x00" * 32

    hash_utxos = b""
    if utxos_flag:
        if len(source_outputs) != len(tx.inputs):
            raise ValueError("SIGHASH_UTXOS requires a source output for every input")
        utxo_blob = b"".join(_serialize_utxo(o) for o in source_outputs)
        hash_utxos = double_sha256(utxo_blob)

    # BIP-143 / BCH: hashSequence is zeroed for ANYONECANPAY, NONE, and SINGLE.
    if not anyone and mode == SIGHASH_ALL:
        seqs = b"".join(i.sequence.to_bytes(4, "little") for i in tx.inputs)
        hash_sequence = double_sha256(seqs)
    else:
        hash_sequence = b"\x00" * 32

    if mode == SIGHASH_NONE:
        hash_outputs = b"\x00" * 32
    elif mode == SIGHASH_SINGLE:
        if input_index >= len(tx.outputs):
            # BIP-143: undefined / 1; BCH implementations vary. We refuse to
            # silently hash as ALL (SeedCash NF-03).
            raise ValueError("SIGHASH_SINGLE with vin >= n_vout")
        hash_outputs = double_sha256(encode_txout(tx.outputs[input_index]))
    else:
        hash_outputs = double_sha256(b"".join(encode_txout(o) for o in tx.outputs))

    spent = source_outputs[input_index]
    token_prefix = encode_token_prefix(spent.token)
    txin = tx.inputs[input_index]

    preimage = b"".join(
        [
            tx.version.to_bytes(4, "little"),
            hash_prevouts,
            hash_utxos,
            hash_sequence,
            txin.prev_txid,
            txin.prev_index.to_bytes(4, "little"),
            token_prefix,
            encode_compact_size(len(covered_bytecode)),
            covered_bytecode,
            spent.value_sats.to_bytes(8, "little"),
            txin.sequence.to_bytes(4, "little"),
            hash_outputs,
            tx.locktime.to_bytes(4, "little"),
            hash_type.to_bytes(4, "little"),
        ]
    )
    return double_sha256(preimage), preimage
