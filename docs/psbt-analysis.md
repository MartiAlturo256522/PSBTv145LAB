# PSBT analysis (BIP-174 / BIP-370) vs BCH

- Magic `psbt\xff`. Maps + 0x00 separators.
- `PSBT_GLOBAL_UNSIGNED_TX = 0x00` required in v0, **forbidden** in v2.
- `PSBT_GLOBAL_VERSION = 0xFB`, value **uint32 LE**, not CompactSize. Omitted ⇒ 0. v2 must be 2. **There is no version 145 in any BIP.**
- Duplicate keys invalid.
- Signer must reject unacceptable sighash. BCH requires FORKID.
- Proprietary 0xFC: compactSize(id len) || id || compactSize(subtype) || subkeydata.
- **No standard CashTokens PSBT key.** Tokens live in tx serialization (`0xef` in the CompactSize-covered script field) inside unsigned tx and NON_WITNESS_UTXO.
- BCH has no segwit: BIP-174-correct UTXO proof is **full previous transaction** at input 0x00.
- BCHN redefines 0x00 as a single CTxOut (`PSBT_IN_UTXO`). That is a breaking dialect (`bchn-v0`).
- Electron Cash: no PSBT implementation found.

Paytaca: see `docs/paytaca-psbt.md`.
