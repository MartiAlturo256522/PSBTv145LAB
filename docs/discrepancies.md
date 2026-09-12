# Discrepancies

Do not silently pick a winner.

| ID | Topic | A | B | Lab policy |
|---|---|---|---|---|
| D-PSBT-145 | PSBT version 145 | Paytaca default | BIP-174/370 only 0 and 2 | Model as **Paytaca dialect**, not a standard |
| D-0x36 | Output key 0x36 | Paytaca CashToken prefix | Unregistered in BIP | Encode only in `paytaca-145`. Signer must not trust it |
| D-BCHN-UTXO | Input type 0x00 | BIP-174: full previous tx | BCHN: single CTxOut | Separate dialect `bchn-v0`. SeedCash needs full prev tx |
| D-COMMIT-MAX | NFT commitment | CHIP/Upgrade 9: 40 | BCHN Upgrade 12 (May 2026): 128 | Default 40. NEG-07 invalid under 40. Document 128 |
| D-VERSION-PARSE | GLOBAL_VERSION value | BIP-174 uint32 LE | SeedCash CompactSize/varint | 0, 2, 145 happen to decode; other values will not |
| D-HYBRID | Hybrid UTXO | CHIP: NFT+FT one output | SeedCash `if nft elif ft` | Vectors GEN-05, POST-13..16, XGEN-03 |
| D-GENESIS-UI | Genesis review | Consensus: output tokens | SeedCash routes on **inputs** | GEN-* SeedCash expected silent |
| D-SIGHASH-NONE | NONE\|FORKID | CHIP/BCH valid | SeedSigner embit skips non-ALL; SeedCash **signs** | SIG-02 |
| D-UTXOS-ACP | UTXOS+ACP | CHIP VM fail | SeedCash does not reject | SIG-06 |
| D-ADDR | Token CashAddr | 0x10 `z` / 0x18 `r` | SeedCash 0x08 `p` / 0x05 | SCR-01 |
| D-ABC | Bitcoin ABC | Chat sometimes cites ABC | ABC does not implement CashTokens | Ignore ABC |
| D-LIBAUTH-PSBT | libauth PSBT | — | libauth has **no** PSBT codec | Tokens via tx encoding only |
| D-POST-VOUT | Post-genesis fixtures | Naive token UTXO at vout=0 also genesises | Lab now places post-genesis tokens at **vout=1** (dummy BCH at 0). GEN-15 is the dedicated token-bearing vout=0 case | |
| D-SIGHASH-SINGLE | hashSequence | Lab originally hashed sequences for SINGLE (wrong) | BIP-143 zeros hashSequence for SINGLE/NONE/ACP. **Fixed.** |

When two oracles disagree, `vectors/differential.json` records both statuses. SKIPPED is not PASS.
