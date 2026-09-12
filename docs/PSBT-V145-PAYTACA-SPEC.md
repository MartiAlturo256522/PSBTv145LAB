# PSBT v145 — Paytaca dialect (executable spec)

**Status of this document:** reverse-engineered from Paytaca source. It is
**not** a BIP. Official PSBT versions are 0 (BIP-174) and 2 (BIP-370).

**This lab must not treat v145 as a standard.** It is a Paytaca wallet
dialect that reuses BIP-44 coin type 145 as `PSBT_GLOBAL_VERSION`.

## Provenance (verified)

| Item | Value | Source |
| --- | --- | --- |
| Repo | https://github.com/paytaca/paytaca-app | git |
| App HEAD (2026-09-11) | `6e8954511b1e0871cf1632f770665323d424f2a2` | git ls-remote / commit |
| `psbt.js` last change | `9c338d2ce07ee33cda2cec33bb340657c6fc1990` (2026-04-03) | git log |
| Blob unchanged on HEAD | yes | git |
| App version | v0.27.0 | package.json |
| Libauth package | `bitauth-libauth-v3` → `@bitauth/libauth@^3.1.0-next.4` | package.json |
| Authoritative file | `src/lib/multisig/psbt.js` | Paytaca |
| Writer | `Psbt.encode()` called from `Pst.toPsbt(version = 145)` | pst.js |
| CHIP | **none**. Comment: “TODO: Create CHIP / Using BCH's bip44 cointype as PSBT version” | psbt.js `setPsbtVersion` |

Pinned raw URL:

https://raw.githubusercontent.com/paytaca/paytaca-app/9c338d2ce07ee33cda2cec33bb340657c6fc1990/src/lib/multisig/psbt.js

Live JavaScript execution of this file is the **only** Paytaca oracle.
A Python translation lives at `audits/paytaca/paytaca_codec.py` and is
**labelled a translation, not an oracle**.

## What v145 is

```javascript
setPsbtVersion(version = 145){
  const k = new Key(hexToBin(PSBT_GLOBAL_VERSION))  // 0xFB
  const v = new Value(numberToBinUint32LE(version)) // 91 00 00 00
}
```

- Not BIP-174 v0, not BIP-370 v2.
- `sanitizeForVersion(145)` is a no-op (`if (psbtVersion === 145) break`).
- Result: **hybrid v0 + v2** maps in one blob.

## Wire layout Paytaca actually emits

```
magic          70 73 62 74 ff
global map     <kv>*  00
input map 0    <kv>*  00
...
input map n-1  <kv>*  00
EXTRA          00                 ← InputMap.serialize L1261
output map 0   <kv>*  00
...
output map m-1 <kv>*  00
```

BIP-174 has **no** extra `00` after the input maps. A BIP-174 parser
treats that byte as an empty first output map. Paytaca
`InputMap.deserialize` skips one extra byte (L1273), so Paytaca
round-trips itself and desyncs on a spec-compliant encoder.

## Key-value encoding

- Magic: 5 bytes `psbt\xff`
- Each pair: `CompactSize(keylen) || key || CompactSize(valuelen) || value`
- Key: first byte = type (Paytaca always `slice(0,1)`; CompactSize key
  types are **not** implemented)
- Map terminator: CompactSize 0 (`00`)
- Duplicate **full keys**: Paytaca accepts (promotes to array). BIP-174
  forbids. This spec records both policies.
- Serialize order: `sortObjectKeys` on the **hex type string**
  (`'00'`,`'0e'`,`'fb'`,`'fc'`), `localeCompare('en')`. Same-type keys
  keep insertion order. This is **not** BIP-174 full-key lexicographic
  order.

## Field table

Every row cites Paytaca `psbt.js` at `9c338d2`. “Required” means
required for Paytaca `encode()` / `deserialize()` in practice, **not**
BIP required.

| Campo | Key | Scope | Tipo | Obligatorio v145 | Encoding | Fuente | Test |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Magic | — | file | 5 bytes | yes | `70736274ff` | L4, L126, L1393 | inspector |
| UNSIGNED_TX | `00` | global | no keydata | written always | raw unsigned tx (CashTokens in script field) | L7, L428, L1436 | PSBT-02 |
| XPUB | `01` | global | 78-byte HD payload | if signers | keydata=xpub payload; value=4B fingerprint \|\| uint32LE indexes | L8, L449, L1428 | none yet |
| TX_VERSION | `02` | global | none | written | **int32 LE** (`numberToBinInt32LE`) | L9, L474, L1437 | PSBT-02 |
| FALLBACK_LOCKTIME | `03` | global | none | written | write int32 LE, read uint32 LE | L10, L493, L1441 | PSBT-02 |
| INPUT_COUNT | `04` | global | none | **yes to parse** (0 is falsy → throw) | CompactSize **in the value** | L11, L515, L1438 | PSBT-02 |
| OUTPUT_COUNT | `05` | global | none | **yes to parse** | CompactSize in the value | L12, L527, L1439 | PSBT-02 |
| TX_MODIFIABLE | `06` | global | none | no | setter empty | L13, L535 | — |
| VERSION | `fb` | global | none | default 145 | **uint32 LE** `91 00 00 00` | L16, L545 | PSBT-02 |
| PROPRIETARY | `fc` | global | compact(idLen)\|\|id\|\|subtype\|\|subkeydata | `network` always | UTF-8 value; identifiers `paytaca` and `metadata` | L17, L70–115, L558, L1450 | PSBT-02 |
| NON_WITNESS_UTXO | `00` | input | none | written | **full previous tx** (token-aware) | L20, L675, L1508 | PSBT-02 |
| WITNESS_UTXO | `01` | input | none | **never written** | constant only | L21 | — |
| PARTIAL_SIG | `02` | input | pubkey | if signed | sig \|\| sighash byte | L22, L689, L1509 | GEN-*-signed |
| SIGHASH_TYPE | `03` | input | none | if `sigHash` set | uint32 LE | L23, L728, L1512 | SIG-* |
| REDEEM_SCRIPT | `04` | input | none | typical multisig | raw script | L24, L739, L1513 | — |
| BIP32_DERIVATION | `06` | input | pubkey | typical | fingerprint \|\| uint32LE path | L27, L761, L1514 | PSBT-02 |
| FINAL_SCRIPTSIG | `07` | input | none | if finalized | raw scriptSig | L28, L801, L1521 | — |
| PREVIOUS_TXID | `0e` | input | none | written | 32-byte hash as libauth stores it (UI order) | L35, L820, L1522 | PSBT-02 |
| OUTPUT_INDEX | `0f` | input | none | written | uint32 LE | L36, L838, L1523 | PSBT-02 |
| SEQUENCE | `10` | input | none | written | uint32 LE | L37, L852, L1524 | PSBT-02 |
| PROPRIETARY | `fc` | input | same layout | no | encode() does not write | L51, L893 | — |
| REDEEM_SCRIPT | `00` | output | none | no | raw | L54, L999, L1533 | — |
| BIP32_DERIVATION | `02` | output | pubkey | no | fingerprint \|\| path | L56, L1017, L1534 | — |
| AMOUNT | `03` | output | none | written | uint64 LE satoshis | L57, L1061, L1540 | PSBT-02 |
| SCRIPT | `04` | output | none | written | locking bytecode **without** token prefix | L58, L1127, L1542 | PSBT-02 |
| CASHTOKEN | `36` | output | none | if token | libauth `encodeTokenPrefix` **including `0xef`** | L66, L1085, L1541 | PSBT-02 |
| PROPRIETARY | `fc` | output | same | if `output.purpose` | identifier `paytaca`, subtype 2, subkey `purpose` | L67, L1149, L1543 | — |

`0x36` is **unregistered** in the BIP PSBT key registry. It is Paytaca-only.

## CashTokens in this dialect

| Fact | Paytaca behavior | Authoritative layer |
| --- | --- | --- |
| Output token in unsigned tx | prefix `0xef` concatenated into the txout script field via libauth `encodeTransactionOutput` | CHIP / P2P |
| Output token in PSBT map | key `36`, value = `encodeTokenPrefix` (starts with `0xef`) | Paytaca metadata |
| Output `04` | locking bytecode only — **no** `0xef` | Paytaca |
| Input tokens | recovered from `NON_WITNESS_UTXO` via `decodeTransactionBch` (`getSourceUtxo`) | CHIP / P2P |
| Input token PSBT key | **none** | — |
| WITNESS_UTXO | unused | — |
| Decode UI token | `getToken()` reads **only** key `36`, not the unsigned tx | Paytaca quirk |
| If `36` missing | Paytaca decoded outputs have no `.token` even if unsigned tx has CashTokens | Paytaca quirk |

A signer that trusts `0x36` over the unsigned tx can be lied to (lab PSBT-06).
A hardware wallet that ignores `0x36` and decodes the unsigned tx + prev
txs is consensus-correct.

## Proprietary key layout

```
key   = 0xFC || CompactSize(len(id)) || id || CompactSize(subtype) || subkeydata
value = UTF-8 bytes   (walletHash would be hex bytes; encode path is commented out)
```

Identifiers: `paytaca`, `metadata` (duplicate set).

Subtypes: 0 walletHash, 1 origin, 2 purpose, 3 network, 4 creator.

`encode()` always writes `network` for both identifiers. origin / creator
/ purpose only if the PST object has those strings.

These fields are **wallet metadata, not consensus**.

## Counts, versions, integers

| Field | Integer encoding |
| --- | --- |
| PSBT version (`fb`) | uint32 LE |
| Tx version (`02`) | int32 LE write |
| Fallback locktime (`03`) | int32 LE write, uint32 LE read |
| Input/output count (`04`/`05`) | CompactSize |
| Outpoint index / sequence / sighash | uint32 LE |
| Output amount | uint64 LE |

`encode()` reads tx version from the unsigned tx with `readCompactUint`
on the first bytes. For version 1 or 2 this equals the first byte of
uint32 LE. It is **not** a general uint32 reader.

Input/output count `0` is unparsable (`if (!inputCount) throw`).

## `sanitizeForVersion`

| Version | Global | Input | Output |
| --- | --- | --- | --- |
| 0 | drop v2 globals | drop `0e`/`0f`/`10`/`11`/`12` | drop amount/script |
| 2 | drop unsigned tx | require `0e`/`0f` if sanitizer actually runs | require amount |
| 145 | keep all | keep all | keep all, including `36` |

**Production path never passes `psbtVersion` into `InputMap.serialize` /
`OutputMap.serialize`.** Those functions take no argument, so
`input.serialize()` sees `undefined`. Required-field throws do not run
on serialize. Only `GlobalMap.serialize(psbtVersion)` sanitizes; for 145
it is a no-op.

## Compatible encoder MUST

1. Magic `70736274ff`.
2. `fb` = 4-byte LE 145 (`91 00 00 00`).
3. Hybrid: unsigned tx **and** v2 counts / prevout / amount / script.
4. Full previous transactions in input `00` (not CTxOut, not witness UTXO).
5. Token outputs: `36` starts with `0xef`; `04` is locking-only; unsigned
   tx outputs contain the prefix.
6. **One extra `0x00` after all input maps.**
7. Type-hex sort of keys on serialize (or Paytaca will rewrite order on
   re-encode).
8. CompactSize lengths. Single-byte key types.

## Compatible encoder MUST NOT

1. Encode version 145 as CompactSize `0x91`.
2. Omit the extra post-input `0x00` if the consumer is Paytaca
   `deserialize` (it will eat the first output byte).
3. Put `0xef` inside output key `04`.
4. Strip `0xef` from key `36`.
5. Rely on `WITNESS_UTXO` for tokens.
6. Assume BIP-174 duplicate-key rejection or full-key lexicographic order.
7. Treat `0x36` as authoritative over the unsigned transaction.

## Lab generator vs this spec (first audit)

See `docs/known-differences.md` and `audits/paytaca/`. Snapshot:

| Requirement | Lab `encode_psbt(..., dialect="paytaca-145")` |
| --- | --- |
| Version 145 uint32 LE | yes |
| Hybrid v0+v2 | yes |
| `36` includes `0xef` | yes |
| `04` locking only | yes |
| Extra input `00` | **NO** |
| Type-hex key sort | **NO** (insertion order) |
| Proprietary `network` | yes (plus origin/creator/purpose always) |
| Sighash on unsigned | lab always writes `03`; Paytaca only if `sigHash` set |
| Live Paytaca JS round-trip | **BLOCKED** (Node not required/installed at audit start) |

Until a **live** Paytaca `Psbt.serialize()`/`deserialize()` round-trip
matches, this dialect is **NOT VERIFIED**.
