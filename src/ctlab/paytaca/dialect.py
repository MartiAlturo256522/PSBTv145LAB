"""Paytaca proprietary PSBT fields (identifier 'paytaca' / 'metadata').

These are wallet metadata, NOT consensus. A signer MUST NOT trust them
for token amounts, categories, or destinations.
"""

from __future__ import annotations

from ctlab.protocol.compact_size import encode_compact_size

PAYTACA_ID = b"paytaca"
METADATA_ID = b"metadata"

SUBTYPES = {
    "walletHash": 0,
    "origin": 1,
    "purpose": 2,
    "network": 3,
    "creator": 4,
}


def proprietary_key(identifier: bytes, subtype: int, subkey: bytes) -> bytes:
    return (
        bytes([0xFC])
        + encode_compact_size(len(identifier))
        + identifier
        + encode_compact_size(subtype)
        + subkey
    )


def paytaca_global_fields(
    network: str = "mainnet",
    origin: str = "cashtokens-psbt-lab",
    creator: str = "SeedCash laboratory",
    purpose: str = "test-vector",
) -> list[tuple[bytes, bytes]]:
    # Paytaca Psbt.encode() insertion within type 0xFC: origin, creator,
    # purpose (if set), then network (always). Same for identifier "metadata".
    fields = []
    for ident in (PAYTACA_ID, METADATA_ID):
        fields.append((proprietary_key(ident, SUBTYPES["origin"], b"origin"), origin.encode()))
        fields.append((proprietary_key(ident, SUBTYPES["creator"], b"creator"), creator.encode()))
        fields.append((proprietary_key(ident, SUBTYPES["purpose"], b"purpose"), purpose.encode()))
        fields.append((proprietary_key(ident, SUBTYPES["network"], b"network"), network.encode()))
    return fields
