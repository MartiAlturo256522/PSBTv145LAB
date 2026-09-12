# Known differences (do not pick a silent winner)

Classification:

- **equivalent** — different bytes, same meaning
- **dialect** — two valid transports for different consumers
- **incompatibility** — one side cannot parse or will mis-parse the other
- **semantic** — token/tx meaning differs

| ID | Topic | A | B | Class | Lab policy |
| --- | --- | --- | --- | --- | --- |
| D-PSBT-145 | Version number 145 | Paytaca default | BIP-174/370 only 0 and 2 | dialect | Model as Paytaca dialect, not a BIP |
| D-0x36 | Output key `36` | Paytaca `encodeTokenPrefix` incl. `0xef` | Unregistered in BIP | dialect | Encode only in `paytaca-145`. Signer must not trust it |
| D-04-SCRIPT | Output key `04` | Paytaca: locking bytecode only | BIP-370: scriptPubKey (would include `0xef`) | dialect / semantic for v2 parsers | Match Paytaca; unsigned tx remains authoritative |
| D-PAYTACA-EXTRA-00 | Extra `00` after input maps | Paytaca serialize L1261 / deserialize L1273 | BIP-174: no such byte | **incompatibility** (Paytaca vs BIP-174) | **Lab `paytaca-145` now emits and parses the extra `00`.** BIP-174 dialect does not. Live Paytaca JS still not executed. |
| D-KEY-ORDER | Map key order | Lab insertion (`00,0e,0f,10,03,06`) | Paytaca type-hex sort (`00,03,06,0e,0f,10`) | equivalent for combiners that ignore order | **Lab `paytaca-145` now type-hex-sorts on serialize.** |
| D-PROP-ORDER | Proprietary `fc` insertion | Lab now: origin, creator, purpose, network | Paytaca encode(): origin, creator, purpose, network | equivalent | **Aligned** with Paytaca encode() insertion |
| D-SIGHASH-ALWAYS | Input `03` on unsigned | Lab unsigned no longer writes `03` | Paytaca writes only if `input.sigHash` set | dialect | **Aligned** for unsigned lab vectors |
| D-BCHN-UTXO | Input type `00` | BIP-174 / Paytaca / SeedCash: full prev tx | BCHN: single CTxOut | dialect | Separate `bchn-v0` |
| D-COMMIT-MAX | NFT commitment | CHIP/Upgrade 9: 40 | BCHN Upgrade 12 (May 2026): 128 | semantic (epoch) | Default 40 |
| D-VERSION-PARSE | GLOBAL_VERSION | BIP-174 uint32 LE | SeedCash CompactSize/varint | incompatibility for other values | Encoder writes 4-byte LE |
| D-HYBRID | Hybrid UTXO | CHIP: NFT+FT one output | SeedCash UI `if nft elif ft` | semantic (UI) | Vectors GEN-05, POST-13..16 |
| D-GENESIS-UI | Genesis review | Consensus: output tokens | SeedCash routes on **inputs** | semantic (UI) | GEN-* expected silent in SeedCash |
| D-LIBAUTH-PSBT | libauth PSBT | — | libauth has **no** PSBT codec | n/a | Tokens via tx encoding only |
| D-DUP-KEYS | Duplicate keys | BIP-174 reject | Paytaca promotes to array | incompatibility | Lab decoder rejects; Paytaca does not |
| D-TRAILING | Bytes after last map | Lab decoder historically ignored | BIP-174 complete at last output separator | incompatibility | Hostile-input: must reject |
| D-TXID-ORDER | `0e` PREVIOUS_TXID | Lab: P2P/HASH256 `TxInput.prev_txid` | Paytaca/libauth: UI order | **semantic / byte** if both write 32 raw bytes | Must confirm against live Paytaca; UNVERIFIED without JS |
| D-ORACLE-SELF | Differential tests | catalog expected vs same generator | independent implementations | circular | SKIPPED ≠ PASS |

D-TXID-ORDER is unresolved without executing libauth `setOutpointTransactionHash`.
If Paytaca stores UI-order hashes in `0e` while the unsigned tx uses P2P
order, a signer that copies `0e` into a reconstructed tx will invert
prevouts. Treat as a **blocker until live JS confirms**.
