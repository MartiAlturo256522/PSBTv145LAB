"""PSBT encoder/decoder with explicit dialects.

Dialects (never conflated):

- ``bip174-v0``: BIP-174. GLOBAL unsigned tx. Input 0x00 = full previous tx.
- ``bip370-v2``: BIP-370. No unsigned tx. Counts + prevout + amount/script.
- ``paytaca-145``: Paytaca dialect. GLOBAL_VERSION = 145 (uint32 LE).
  Hybrid v0+v2 fields. PSBT_OUT_CASHTOKEN = 0x36.
- ``bchn-v0``: BCHN wallet PSBT. Input 0x00 is a single CTxOut, not a prev tx.
  Documented discrepancy vs BIP-174.

SeedCash currently requires ``bip174-v0`` (unsigned tx + full NON_WITNESS_UTXO).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ctlab.cashtokens.prefix import encode_token_prefix
from ctlab.protocol.compact_size import decode_compact_size, encode_compact_size
from ctlab.transactions.serialize import Transaction, TxOut, encode_transaction, encode_txout

MAGIC = b"psbt\xff"

PSBT_GLOBAL_UNSIGNED_TX = 0x00
PSBT_GLOBAL_XPUB = 0x01
PSBT_GLOBAL_TX_VERSION = 0x02
PSBT_GLOBAL_FALLBACK_LOCKTIME = 0x03
PSBT_GLOBAL_INPUT_COUNT = 0x04
PSBT_GLOBAL_OUTPUT_COUNT = 0x05
PSBT_GLOBAL_VERSION = 0xFB
PSBT_GLOBAL_PROPRIETARY = 0xFC

PSBT_IN_NON_WITNESS_UTXO = 0x00
PSBT_IN_WITNESS_UTXO = 0x01
PSBT_IN_PARTIAL_SIG = 0x02
PSBT_IN_SIGHASH_TYPE = 0x03
PSBT_IN_REDEEM_SCRIPT = 0x04
PSBT_IN_BIP32_DERIVATION = 0x06
PSBT_IN_PREVIOUS_TXID = 0x0E
PSBT_IN_OUTPUT_INDEX = 0x0F
PSBT_IN_SEQUENCE = 0x10

PSBT_OUT_REDEEM_SCRIPT = 0x00
PSBT_OUT_BIP32_DERIVATION = 0x02
PSBT_OUT_AMOUNT = 0x03
PSBT_OUT_SCRIPT = 0x04
PSBT_OUT_CASHTOKEN = 0x36  # Paytaca-only, NOT in BIP registry
PSBT_OUT_PROPRIETARY = 0xFC


class PsbtError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _kv(key: bytes, value: bytes) -> bytes:
    return encode_compact_size(len(key)) + key + encode_compact_size(len(value)) + value


def _is_js_array_index_key(s: str) -> bool:
    """ECMAScript CanonicalNumericIndexString: ToString(ToUint32(s)) === s.

    ``"10"`` is an array index; ``"00"`` is not (canonical form is ``"0"``).
    After libauth ``sortObjectKeys`` rebuilds ``{...all, [key]: val}``,
    ``Object.keys`` emits integer indices first. Paytaca ``serialize``
    iterates that order (psbt.js), so SEQUENCE ``10`` precedes UTXO ``00``.
    """
    if not s or not s.isdigit() or (len(s) > 1 and s[0] == "0"):
        return False
    n = int(s)
    return 0 <= n <= 0xFFFFFFFF and str(n) == s


def _paytaca_type_order(type_hexes: list[str]) -> list[str]:
    """localeCompare('en') then JS Object.keys after sortObjectKeys rebuild."""
    loc = sorted(type_hexes)
    idx = sorted((t for t in loc if _is_js_array_index_key(t)), key=int)
    rest = [t for t in loc if not _is_js_array_index_key(t)]
    return idx + rest


def _paytaca_sort_pairs(pairs: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """Paytaca map order: JS Object.keys(sortObjectKeys(keypairs)).

    Same-type keys keep insertion order (Paytaca stores them in an array).
    """
    groups: dict[str, list[tuple[bytes, bytes]]] = {}
    for key, value in pairs:
        t = f"{key[0]:02x}" if key else ""
        groups.setdefault(t, []).append((key, value))
    out: list[tuple[bytes, bytes]] = []
    for t in _paytaca_type_order(list(groups.keys())):
        out.extend(groups[t])
    return out


def _parse_map(buf: bytes, pos: int) -> tuple[list[tuple[bytes, bytes]], int]:
    pairs: list[tuple[bytes, bytes]] = []
    seen: set[bytes] = set()
    while pos < len(buf):
        klen, pos, _ = decode_compact_size(buf, pos)
        if klen == 0:
            return pairs, pos
        if pos + klen > len(buf):
            raise PsbtError("truncated_key", f"key length {klen} exceeds remaining {len(buf) - pos}")
        key = buf[pos : pos + klen]
        pos += klen
        vlen, pos, _ = decode_compact_size(buf, pos)
        if pos + vlen > len(buf):
            raise PsbtError(
                "truncated_value", f"value length {vlen} exceeds remaining {len(buf) - pos}"
            )
        value = buf[pos : pos + vlen]
        pos += vlen
        if key in seen:
            raise PsbtError("duplicate_key", f"duplicate PSBT key {key.hex()}")
        seen.add(key)
        pairs.append((key, value))
    raise PsbtError("truncated_map", "unexpected end of PSBT map")


@dataclass
class Psbt:
    dialect: str
    global_pairs: list[tuple[bytes, bytes]] = field(default_factory=list)
    inputs: list[list[tuple[bytes, bytes]]] = field(default_factory=list)
    outputs: list[list[tuple[bytes, bytes]]] = field(default_factory=list)
    unsigned_tx: Optional[bytes] = None
    version: int = 0

    def serialize(self) -> bytes:
        paytaca = self.dialect == "paytaca-145" or self.version == 145
        parts = [MAGIC]
        g = _paytaca_sort_pairs(self.global_pairs) if paytaca else self.global_pairs
        for k, v in g:
            parts.append(_kv(k, v))
        parts.append(b"\x00")
        for imap in self.inputs:
            im = _paytaca_sort_pairs(imap) if paytaca else imap
            for k, v in im:
                parts.append(_kv(k, v))
            parts.append(b"\x00")
        if paytaca:
            # Paytaca InputMap.serialize appends an extra 0x00 (psbt.js L1261).
            parts.append(b"\x00")
        for omap in self.outputs:
            om = _paytaca_sort_pairs(omap) if paytaca else omap
            for k, v in om:
                parts.append(_kv(k, v))
            parts.append(b"\x00")
        return b"".join(parts)

    def base64(self) -> str:
        import base64

        return base64.b64encode(self.serialize()).decode("ascii")


def decode_psbt(buf: bytes) -> Psbt:
    if not isinstance(buf, (bytes, bytearray)):
        raise PsbtError("type", "PSBT must be bytes")
    buf = bytes(buf)
    if len(buf) < 5 or buf[:5] != MAGIC:
        raise PsbtError("magic", "invalid PSBT magic")
    pos = 5
    global_pairs, pos = _parse_map(buf, pos)
    unsigned_tx = None
    version = 0
    n_in = 0
    n_out = 0
    for key, value in global_pairs:
        t = key[0]
        if t == PSBT_GLOBAL_UNSIGNED_TX:
            unsigned_tx = value
        elif t == PSBT_GLOBAL_INPUT_COUNT:
            n_in, _, _ = decode_compact_size(value, 0)
        elif t == PSBT_GLOBAL_OUTPUT_COUNT:
            n_out, _, _ = decode_compact_size(value, 0)
        elif t == PSBT_GLOBAL_VERSION:
            if len(value) == 4:
                version = int.from_bytes(value, "little")
            else:
                # SeedCash incorrectly uses CompactSize; record both.
                version, _, _ = decode_compact_size(value, 0)
    if unsigned_tx is not None:
        from ctlab.transactions.serialize import decode_transaction

        parsed = decode_transaction(unsigned_tx)
        if n_in == 0:
            n_in = len(parsed.inputs)
        if n_out == 0:
            n_out = len(parsed.outputs)
    if n_in == 0 or n_out == 0:
        raise PsbtError("counts", "unable to determine input/output counts")
    inputs = []
    for _ in range(n_in):
        pairs, pos = _parse_map(buf, pos)
        inputs.append(pairs)
    outputs: list[list[tuple[bytes, bytes]]] = []
    if version == 145 and pos < len(buf) and buf[pos] == 0x00:
        # Paytaca extra input-map separator. v145 encode() always writes
        # PSBT_OUT_AMOUNT so the first output map is not empty; a lone 0x00
        # here is the extra separator, not an empty output.
        try:
            p = pos + 1
            trial: list[list[tuple[bytes, bytes]]] = []
            for _ in range(n_out):
                pairs, p = _parse_map(buf, p)
                trial.append(pairs)
            if p > len(buf):
                raise PsbtError("truncated_map", "output maps overrun")
            outputs = trial
            pos = p
        except PsbtError:
            outputs = []
            for _ in range(n_out):
                pairs, pos = _parse_map(buf, pos)
                outputs.append(pairs)
    else:
        for _ in range(n_out):
            pairs, pos = _parse_map(buf, pos)
            outputs.append(pairs)
    if pos < len(buf):
        raise PsbtError("trailing_bytes", f"{len(buf) - pos} trailing bytes after output maps")
    dialect = "bip174-v0"
    if version == 145:
        dialect = "paytaca-145"
    elif version == 2:
        dialect = "bip370-v2"
    elif unsigned_tx is None:
        dialect = "bip370-v2"
    return Psbt(
        dialect=dialect,
        global_pairs=global_pairs,
        inputs=inputs,
        outputs=outputs,
        unsigned_tx=unsigned_tx,
        version=version,
    )


def encode_psbt(
    tx: Transaction,
    prev_txs: list[bytes],
    source_outputs: list[TxOut],
    dialect: str = "bip174-v0",
    sighash: int | None = None,
    derivations: list[tuple[bytes, bytes, list[int]]] | None = None,
    partial_sigs: list[tuple[bytes, bytes] | None] | None = None,
    proprietary: list[tuple[bytes, bytes]] | None = None,
    include_output_tokens: bool = False,
) -> Psbt:
    """Build a PSBT for ``tx``.

    ``derivations[i]`` = (pubkey, master_fingerprint, path indices) or omitted.
    ``partial_sigs[i]`` = (pubkey, sig_with_hashtype) or None.
    """
    g: list[tuple[bytes, bytes]] = []
    unsigned = encode_transaction(tx)

    if dialect == "paytaca-145":
        g.append((bytes([PSBT_GLOBAL_UNSIGNED_TX]), unsigned))
        g.append((bytes([PSBT_GLOBAL_TX_VERSION]), tx.version.to_bytes(4, "little")))
        g.append((bytes([PSBT_GLOBAL_FALLBACK_LOCKTIME]), tx.locktime.to_bytes(4, "little")))
        g.append((bytes([PSBT_GLOBAL_INPUT_COUNT]), encode_compact_size(len(tx.inputs))))
        g.append((bytes([PSBT_GLOBAL_OUTPUT_COUNT]), encode_compact_size(len(tx.outputs))))
        g.append((bytes([PSBT_GLOBAL_VERSION]), (145).to_bytes(4, "little")))
        include_output_tokens = True
        include_v2_io = True
        bchn_utxo = False
        version = 145
    elif dialect == "bip370-v2":
        g.append((bytes([PSBT_GLOBAL_TX_VERSION]), tx.version.to_bytes(4, "little")))
        g.append((bytes([PSBT_GLOBAL_FALLBACK_LOCKTIME]), tx.locktime.to_bytes(4, "little")))
        g.append((bytes([PSBT_GLOBAL_INPUT_COUNT]), encode_compact_size(len(tx.inputs))))
        g.append((bytes([PSBT_GLOBAL_OUTPUT_COUNT]), encode_compact_size(len(tx.outputs))))
        g.append((bytes([PSBT_GLOBAL_VERSION]), (2).to_bytes(4, "little")))
        include_v2_io = True
        bchn_utxo = False
        version = 2
        unsigned = None
    elif dialect == "bchn-v0":
        g.append((bytes([PSBT_GLOBAL_UNSIGNED_TX]), unsigned))
        include_v2_io = False
        bchn_utxo = True
        version = 0
    else:
        g.append((bytes([PSBT_GLOBAL_UNSIGNED_TX]), unsigned))
        include_v2_io = False
        bchn_utxo = False
        version = 0

    if proprietary:
        g.extend(proprietary)

    in_maps: list[list[tuple[bytes, bytes]]] = []
    for i, inp in enumerate(tx.inputs):
        pairs: list[tuple[bytes, bytes]] = []
        if bchn_utxo:
            pairs.append((bytes([PSBT_IN_NON_WITNESS_UTXO]), encode_txout(source_outputs[i])))
        else:
            if i < len(prev_txs) and prev_txs[i]:
                pairs.append((bytes([PSBT_IN_NON_WITNESS_UTXO]), prev_txs[i]))
        if include_v2_io:
            pairs.append((bytes([PSBT_IN_PREVIOUS_TXID]), inp.prev_txid))
            pairs.append((bytes([PSBT_IN_OUTPUT_INDEX]), inp.prev_index.to_bytes(4, "little")))
            pairs.append((bytes([PSBT_IN_SEQUENCE]), inp.sequence.to_bytes(4, "little")))
        if sighash is not None:
            pairs.append((bytes([PSBT_IN_SIGHASH_TYPE]), sighash.to_bytes(4, "little")))
        if derivations and i < len(derivations) and derivations[i]:
            pub, fp, path = derivations[i]
            key = bytes([PSBT_IN_BIP32_DERIVATION]) + pub
            val = fp + b"".join(idx.to_bytes(4, "little") for idx in path)
            pairs.append((key, val))
        if partial_sigs and i < len(partial_sigs) and partial_sigs[i]:
            pub, sig = partial_sigs[i]
            pairs.append((bytes([PSBT_IN_PARTIAL_SIG]) + pub, sig))
        in_maps.append(pairs)

    out_maps: list[list[tuple[bytes, bytes]]] = []
    for out in tx.outputs:
        pairs = []
        if getattr(out, "redeem_script", None):
            pairs.append((bytes([PSBT_OUT_REDEEM_SCRIPT]), out.redeem_script))
        if include_v2_io:
            pairs.append((bytes([PSBT_OUT_AMOUNT]), out.value_sats.to_bytes(8, "little")))
            pairs.append((bytes([PSBT_OUT_SCRIPT]), out.locking_bytecode))
        if include_output_tokens and out.token is not None:
            pairs.append((bytes([PSBT_OUT_CASHTOKEN]), encode_token_prefix(out.token)))
        out_maps.append(pairs)

    return Psbt(
        dialect=dialect,
        global_pairs=g,
        inputs=in_maps,
        outputs=out_maps,
        unsigned_tx=unsigned if dialect != "bip370-v2" else None,
        version=version,
    )
