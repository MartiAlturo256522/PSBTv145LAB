"""Receiver parser snapshot before the v145 compatibility fix; no hardware dependencies."""
import struct
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

@dataclass
class Token:
    @dataclass
    class NFTData:
        capability: str
        commitment: str

    class Warning(Enum):
        MINTING = "minting"
        BURNING = "burning"

    prefix: bytes
    script_pubkey: bytes
    category_id: str
    ft_amount: Optional[int] = None
    nft_data: Optional[NFTData] = None

def read_varint(buf: bytes, pos: int) -> Tuple[int, int]:
    """Read a Bitcoin-style varint (CompactSize uint) at ``pos``."""
    if pos >= len(buf):
        raise ValueError("pos out of range")
    b = buf[pos]
    if b < 0xFD:
        return b, pos + 1
    if b == 0xFD:
        if pos + 3 > len(buf):
            raise ValueError("truncated CompactSize uint16")
        value = struct.unpack_from("<H", buf, pos + 1)[0]
        if value < 0xFD:
            raise ValueError("non-minimal CompactSize encoding")
        return value, pos + 3
    if b == 0xFE:
        if pos + 5 > len(buf):
            raise ValueError("truncated CompactSize uint32")
        value = struct.unpack_from("<I", buf, pos + 1)[0]
        if value <= 0xFFFF:
            raise ValueError("non-minimal CompactSize encoding")
        return value, pos + 5
    if pos + 9 > len(buf):
        raise ValueError("truncated CompactSize uint64")
    value = struct.unpack_from("<Q", buf, pos + 1)[0]
    if value <= 0xFFFFFFFF:
        raise ValueError("non-minimal CompactSize encoding")
    return value, pos + 9

def read_token_varint(buf: bytes, pos: int) -> Tuple[int, int]:
    """Read a minimally encoded CashTokens CompactSize value."""

    if pos >= len(buf):
        raise ValueError("missing CompactSize value")

    value, new_pos = read_varint(buf, pos)
    marker = buf[pos]

    if (
        (marker == 0xFD and value < 0xFD)
        or (marker == 0xFE and value <= 0xFFFF)
        or (marker == 0xFF and value <= 0xFFFFFFFF)
    ):
        raise ValueError("non-minimal CompactSize encoding")

    return value, new_pos

def parse_token_script(script: bytes) -> Optional[Token]:
    """Parse a CashTokens prefix and return the token + remaining locking bytecode."""

    if not script or script[0] != 0xEF:
        return None

    pos = 1

    # category_id
    if len(script) < pos + 32:
        return None

    category = script[pos:pos + 32]
    pos += 32

    # bitfield
    if len(script) <= pos:
        return None

    bitfield = script[pos]
    pos += 1

    # RESERVED_BIT
    if bitfield & 0x80:
        return None

    has_commitment_length = bool(bitfield & 0x40)
    has_nft = bool(bitfield & 0x20)
    has_amount = bool(bitfield & 0x10)
    capability_bits = bitfield & 0x0F

    if not has_nft and has_commitment_length:
        return None
    if not has_nft and capability_bits != 0:
        return None
    if has_nft and capability_bits > 2:
        return None
    if not has_nft and not has_amount:
        return None

    capability_map = { 0: "none", 1: "mutable", 2: "minting"}
    capability = (capability_map[capability_bits] if has_nft else None)

    nft_data = None
    if has_nft:
        if has_commitment_length:
            try:
                nft_len, pos = read_token_varint(script, pos)
            except (IndexError, struct.error, ValueError):
                return None
            if nft_len == 0 or nft_len > 40:
                return None
            if len(script) < pos + nft_len:
                return None
            nft_bytes = script[pos:pos + nft_len]
            pos += nft_len
        else:
            nft_bytes = b""
        nft_data: Token.NFTData = Token.NFTData(capability=capability,commitment=nft_bytes.hex())

    ft_amount = None
    if has_amount:
        try:
            ft_amount, pos = read_token_varint(script, pos)
        except (IndexError, struct.error, ValueError):
            return None
        if not 0 < ft_amount <= 0x7FFFFFFFFFFFFFFF:
            return None

    return Token(
        prefix=script[:pos],
        script_pubkey=script[pos:],
        category_id=category[::-1].hex(),
        ft_amount=ft_amount,
        nft_data=nft_data)

def parse_keypairs(buf: bytes, pos: int) -> Tuple[List[Tuple[bytes, bytes]], int]:
    """Parse one PSBT key-value map, returning ``[(key, value), ...]``."""
    pairs = []
    seen_keys = set()
    limit = len(buf)
    while pos < limit:
        key_len, pos = read_varint(buf, pos)
        if key_len == 0:
            return pairs, pos
        if pos + key_len > limit:
            raise ValueError("truncated PSBT key")
        key = buf[pos:pos + key_len]
        pos += key_len
        if key in seen_keys:
            raise ValueError("duplicate PSBT key")
        seen_keys.add(key)
        val_len, pos = read_varint(buf, pos)
        if pos + val_len > limit:
            raise ValueError("truncated PSBT value")
        value = buf[pos:pos + val_len]
        pos += val_len
        pairs.append((key, value))
    raise ValueError("unexpected end while parsing keypairs")

def parse_psbt(buf) -> Dict[str, Any]:
    """Parse a PSBT binary into global/input/output key-value maps.

    Key-value maps are lists of ``(key, value)`` tuples (in serialization
    order, duplicates preserved) rather than dicts, since PSBT allows
    repeated key *types* (e.g. multiple BIP32 derivations) that only differ
    by the data appended to the key type byte.
    """
    if isinstance(buf, (bytearray, memoryview)):
        buf = bytes(buf)
    if not isinstance(buf, bytes):
        raise TypeError(f"PSBT buffer must be bytes-like, got {type(buf).__name__}")
    if len(buf) < 5 or buf[:5] != b"psbt\xff":
        raise ValueError("invalid PSBT magic")
    pos = 5

    global_pairs, pos = parse_keypairs(buf, pos)

    known_global_types = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0xFB, 0xFC}
    known_input_types = {
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x0E, 0x0F, 0x10, 0xFC,
    }
    known_output_types = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0xFC, 0x36}

    def reject_unknown_types(pairs, allowed_types, scope):
        for key, _ in pairs:
            if not key:
                raise ValueError(f"empty PSBT {scope} key")
            if key[0] not in allowed_types:
                raise ValueError(f"unknown PSBT {scope} field 0x{key[0]:02x}")

    reject_unknown_types(global_pairs, known_global_types, "global")

    unsigned_tx = None
    input_count = 0
    output_count = 0
    psbt_version = 0
    proprietary: List[Tuple[bytes, bytes]] = []
    for key, value in global_pairs:
        if not key:
            raise ValueError("empty PSBT key")
        if key[0] == 0x00:  # PSBT_GLOBAL_UNSIGNED_TX
            unsigned_tx = value
        elif key[0] == 0x04:  # PSBT_GLOBAL_INPUT_COUNT (v2)
            input_count, count_pos = read_varint(value, 0)
            if count_pos != len(value):
                raise ValueError("invalid PSBT input count")
        elif key[0] == 0x05:  # PSBT_GLOBAL_OUTPUT_COUNT (v2)
            output_count, count_pos = read_varint(value, 0)
            if count_pos != len(value):
                raise ValueError("invalid PSBT output count")
        elif key[0] == 0xFB:  # PSBT_GLOBAL_VERSION
            psbt_version, version_pos = read_varint(value, 0)
            if version_pos != len(value):
                raise ValueError("invalid PSBT version")
        elif key[0] == 0xFC:  # PSBT_GLOBAL_PROPRIETARY
            proprietary.append((key, value))

    if unsigned_tx is None:
        raise ValueError("No unsigned transaction found in PSBT")

    input_starts: int = 0
    input_ends: int = 0
    inputs = []
    for _ in range(input_count):
        if _ == 0:
            input_starts = pos
        pairs, pos = parse_keypairs(buf, pos)
        reject_unknown_types(pairs, known_input_types, "input")
        inputs.append(pairs)
        if _ == input_count - 1:
            input_ends = pos

    outputs = []
    for _ in range(output_count):
        pairs, pos = parse_keypairs(buf, pos)
        reject_unknown_types(pairs, known_output_types, "output")
        for key, value in pairs:
            if key == b"\x36" and parse_token_script(value) is None:
                raise ValueError("invalid token prefix")
        outputs.append(pairs)

    if pos != len(buf):
        raise ValueError("PSBT has trailing bytes")

    return {
        "global": global_pairs,
        "input_starts": input_starts,
        "input_ends": input_ends,
        "inputs": inputs,
        "outputs": outputs,
        "input_count": input_count,
        "output_count": output_count,
        "psbt_version": psbt_version,
        "unsigned_tx": unsigned_tx,
        "proprietary": proprietary,
    }
