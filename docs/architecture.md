# Architecture

```
catalog (data)
   ↓
scenario model
   ↓
deterministic fixture builder   (synthetic tx graph, no mainnet)
   ↓
BCH transaction builder         (tx serialization)
   ↓
CashTokens encoding             (prefix layer)
   ↓
PSBT encoder                    (dialect: bip174-v0 | bip370-v2 | paytaca-145 | bchn-v0)
   ↓
optional signing                (BCH Schnorr 2019 + sighash)
   ↓
validators                      (consensus ≠ PSBT ≠ SeedCash UI)
   ↓
exporter                        (vectors/, seed_signer/)
```

## Layers (never conflated)

1. **Consensus semantics** — `ctlab.cashtokens.consensus`
2. **Token-prefix serialization** — `ctlab.cashtokens.prefix`
3. **BCH transaction serialization** — `ctlab.transactions`
4. **Sighash / Schnorr** — `ctlab.signing`
5. **PSBT envelope BIP-174/370** — `ctlab.psbt`
6. **Paytaca v145 dialect** — `ctlab.paytaca` + `encode_psbt(..., dialect="paytaca-145")`
7. **Wallet metadata** — proprietary `0xFC`; ignored for amounts
8. **SeedCash parser** — optional import; differential only

The lab can report:

- “CashTokens transaction is valid, but PSBT encoding is invalid.”
- “PSBT envelope is valid, but the transaction violates CashTokens consensus.”
- “PSBT is valid but SeedSigner/SeedCash incorrectly interprets token information.”

## Determinism

- Mnemonic: BIP-39 `abandon`×11 + `about`
- Path: `m/44'/145'/0'/{change}/{index}`
- Alice=0, Bob=1, Carol=2, Dave=3, change=`m/…/1/0`
- No CSPRNG. Same catalog + generator version ⇒ same txid, PSBT, signatures.

## Authoritative token data for a signer

Must be derived from:

1. unsigned transaction outputs (0xef prefix),
2. previous transactions / source outputs,
3. consensus validation.

Must **not** be derived from:

- `PSBT_OUT_CASHTOKEN` (0x36),
- proprietary purpose/network/creator,
- BCMR OP_RETURN.

A mismatch between 0x36 and the unsigned tx is a **security failure** (`PSBT-06`).

## Dialects

| Dialect | GLOBAL version | Unsigned tx | Input 0x00 | Output 0x36 |
|---|---|---|---|---|
| `bip174-v0` | omit / 0 | yes | full prev tx | no |
| `bip370-v2` | 2 uint32 LE | no | v2 prevout fields | no |
| `paytaca-145` | **145** uint32 LE | yes (hybrid) | full prev tx | yes |
| `bchn-v0` | omit | yes | **CTxOut only** | no |
