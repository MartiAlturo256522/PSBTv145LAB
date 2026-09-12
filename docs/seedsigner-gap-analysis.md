# SeedCash / SeedSigner gap analysis

Fork: `C:\Users\reque\seedcash` (SeedSigner 0.8.6-era, custom Python, no embit).

## Parser

- Requires `psbt\xff` and GLOBAL unsigned tx. Pure BIP-370 v2 **cannot parse**.
- `PSBT_GLOBAL_VERSION` read as CompactSize; unused as a gate. 145 is ignored.
- Key 0x36 ignored.
- Duplicate unsigned-tx keys last-wins (BIP-174 would reject).
- Tokens from 0xef in unsigned tx outputs and NON_WITNESS_UTXO prevouts — **not** from metadata. Signing is token-aware; **review is not**.

## UI / semantics bugs the corpus targets

| ID | Gap | Vectors |
|---|---|---|
| SC-04 | Genesis silent (route on inputs only) | GEN-* |
| SC-05 hybrid | `if nft elif ft` | GEN-05, POST-13..16, XGEN-03 |
| SC-05 melt | FT burn by UTXO count | POST-12 |
| SC-05 NFT warn | mint labelled burn; 2→1 silent | POST-01, POST-09 |
| SC-01 | Signs NONE\|FORKID | SIG-02 |
| SC-02 | Address list vs raw vout index | SCR-05 |
| NF-01 | CashAddr 0x08 not 0x10 | SCR-01 |
| — | Missing NON_WITNESS_UTXO | PSBT-05 |
| — | v2 unsigned-tx missing | PSBT-03 |
| — | BCHN CTxOut at 0x00 | PSBT-04 |
| — | 0x36 vs unsigned tx | PSBT-06 |

## What to feed SeedCash

`vectors/seed_signer/<id>/psbt.binary` (BIP-174 v0) plus `expected.json` semantics. Parser should be run with `PYTHONPATH=seedcash/src`.
