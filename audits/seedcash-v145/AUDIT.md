# Audit: Paytaca PSBT v145 → SeedCash

**Date:** 2026-09-13  
**Paytaca `psbt.js`:** `9c338d2ce07ee33cda2cec33bb340657c6fc1990`  
**SeedCash tree:** `C:\Users\reque\seedcash` (`SeedCashOrg/seedcash`)  
**Vectors:** lab motor `ctlab.engine.generate(..., dialect="paytaca-145")`, live-checked against Paytaca JS `deserialize`+`serialize`  
**Harness:** `audits/seedcash-v145/run_audit.py` → `results.json`

This audit does **not** treat v145 as BIP-174 v0. It treats v145 as Paytaca’s BCH extension of PSBT v2 (BIP-370 field set + CashTokens + hybrid unsigned tx). BIP-44 `145'` is unrelated (derivation path only).

---

## 1. What Paytaca actually emits (from `psbt.js`, confirmed on the wire)

`Psbt.encode(decoded, version = 145)` writes a **hybrid PSBT v2 + v0** blob:

| Layer | What is on the wire |
| --- | --- |
| Magic | `70736274ff` |
| `PSBT_GLOBAL_VERSION` `0xFB` | uint32 LE **145** (`91 00 00 00`) |
| `sanitizeForVersion(145)` | **no-op** — v0 and v2 keys are both kept |
| Global v2 | `02` tx version, `03` fallback locktime, `04` input count (CompactSize), `05` output count |
| Global v0 | `00` **full unsigned transaction** (CashTokens already in each txout script as `0xef` prefix) |
| Global proprietary `0xFC` | identifier `paytaca` and `metadata` (origin/creator/purpose/network). Wallet metadata, not consensus |
| Input v2 | `0e` previous txid, `0f` output index, `10` sequence |
| Input v0 | `00` full previous tx (`NON_WITNESS_UTXO`) |
| Output v2 | `03` amount uint64 LE, `04` locking bytecode **without** token prefix |
| Output CashTokens | `36` = libauth `encodeTokenPrefix` **including `0xef`** (unregistered key; comment: “Version(145) token prefix encoded”) |
| `InputMap.serialize` | extra `0x00` after all input maps (`psbt.js` L1261). `deserialize` skips it (`index+1` at L1273) |

Live Paytaca JS byte-identity vs lab generator (this run):

| Vector | `deserialize`+`serialize` == lab |
| --- | --- |
| GEN-04, IO-2-3, SCR-05, POST-01, MONSTER-01 | **5/5 identical** |

So the lab `paytaca-145` bytes used below **are** Paytaca v145 for these cases.

`setPsbtVersion` comment says “Using BCH's bip44 cointype as PSBT version / TODO: Create CHIP”. That is how Paytaca *named* the version field. On the wire, **145 means this hybrid v2+CashTokens layout**, not a BIP-44 path.

---

## 2. What SeedCash actually implements

Pipeline:

```
QR UR:crypto-psbt
  → URDecoder (.cbor = CBOR bstr of PSBT)     [unwrap added 2026-09-13]
  → parse_psbt (magic, maps, REQUIRE global 0x00 unsigned tx)
  → parse_transaction(unsigned_tx) + 0xef token prefix
  → PSBTParser model / UI buckets
  → BitcoinCashSigner.signed_psbt() hashes unsigned_tx, splices input maps
```

SeedCash does **not** rebuild the transaction from PSBT v2 fields (`0x03`/`0x04`/`0x36`/`0x0e`/`0x0f`).  
It **requires** `PSBT_GLOBAL_UNSIGNED_TX`. A pure BIP-370 v2 PSBT (no unsigned tx) raises `No unsigned transaction found in PSBT`.

Paytaca v145 still carries that unsigned tx, so Paytaca blobs *parse*. That is coincidence of Paytaca’s hybrid layout, not a v2 implementation in SeedCash.

Token data in the model comes from the **unsigned tx script field** (`0xef…`), not from `0x36`.

---

## 3. Interoperability matrix (21 Paytaca-v145 vectors)

All 21 **parse without crash**. UR roundtrip (Paytaca `@ngraveio/bc-ur` + SeedCash unwrap) **21/21**. Unsigned-tx token fields **match** Paytaca-aligned `0x36` in every vout (0 mismatches).

| Case | vin/vout | UI route | Extra `00` eaten as empty out map | Notes |
| --- | ---: | --- | --- | --- |
| IO-1-1 | 1/1 | BCH_ONLY | yes | maps: SeedCash `[[]]` vs Paytaca `[03,04]` |
| IO-2-1 | 2/1 | BCH_ONLY | yes | |
| IO-1-2 | 1/2 | BCH_ONLY | yes | change listed as destination; spend = all outputs |
| IO-2-2 | 2/2 | BCH_ONLY | yes | last out-map dropped from parser |
| IO-2-3 | 2/3 | BCH_ONLY | yes | 3 Paytaca maps → SeedCash `[], [03,04], [03,04]` (**vout2 map lost**) |
| IO-3-2 | 3/2 | BCH_ONLY | yes | |
| GEN-01 | 1/1 | **BCH_ONLY** | yes | NFT genesis in model, **not in NFT UI** |
| GEN-04 | 1/1 | **BCH_ONLY** | yes | 1_000_000 FT in model, **FT UI skipped** |
| GEN-05 | 1/1 | **BCH_ONLY** | yes | hybrid minting+FT; NFT-only bucket |
| GEN-06 | 1/3 | BCH_ONLY | yes | multi NFT genesis, BCH review |
| GEN-08 | 2/3 | BCH_ONLY | yes | two categories, BCH review |
| POST-01 | 1/2 | NFT_FIRST | yes | minting warning OK; 2nd `0x36` lost in maps |
| POST-04 | 1/1 | NFT_FIRST | yes | baton burn → warning burning (capability change) |
| POST-08 | 1/1 | NFT_FIRST | yes | |
| SAMECAT-01 | — | NFT/FT | yes | |
| BURN-MULTI | 3/2 | NFT_FIRST | yes | **NFT burn warning silent** (2 in / 1 out) |
| XGEN-07 | 3/3 | NFT_FIRST | yes | genesis+FT+NFT; last `0x36` dropped from maps |
| SCR-02 | 1/1 | BCH_ONLY | yes | P2SH20 token out, genesis-blind |
| SCR-05 | 1/2 | BCH_ONLY | yes | **OP_RETURN first: amount 0 shown for payment addr** |
| BCMR-01 | 1/2 | BCH_ONLY | yes | same index trap + hybrid genesis |
| MONSTER-01 | 6/6 | NFT_FIRST | yes | 6th out-map lost; hybrid NFT-only bucket |

---

## 4. Classified findings

### F1 — Extra input-map `0x00` shifts every output map
**Class:** PSBT v145 interoperability · Parser/model bug  

Paytaca `InputMap.serialize` appends an extra separator. SeedCash `parse_psbt` treats it as an empty first output map and then reads `output_count` maps from there.

Observed on **21/21** vectors:

- 1-output txs: SeedCash output maps = `[[]]` — **`0x36` / `03` / `04` discarded**.
- n-output txs: first map empty, last Paytaca output map **never parsed**.

The **transaction model still matches** because `_build_transaction` uses `unsigned_tx`, not those maps. The signer hashes `unsigned_tx` and splices original tail bytes (`psbt_bytes[input_ends:]`), so the **signed file still contains the original maps**.

Impact today: SeedCash cannot use v145 output metadata (`0x36`, amount, script, `purpose`). It is one desync away from a v2-only producer.

### F2 — SeedCash is not a PSBT v2 decoder
**Class:** PSBT v145 interoperability · Unsupported feature  

Required global `0x00` unsigned tx. v2-only reconstruction (counts + `0e/0f/10` + `03/04/36`) is absent. Paytaca still writes the unsigned tx, so current Paytaca → SeedCash **parses**. A BCH signer that emits v2-only v145 will be rejected.

Do not describe this as “SeedCash speaks BIP-174 v0 instead of v145”. It speaks **unsigned-tx + CashToken prefix in the tx**, and **tolerates** extra v2/v145 keys except for the extra `00` shift.

### F3 — `0x36` ignored; unsigned tx is the token source
**Class:** PSBT v145 interoperability · Hardening  

On these vectors, unsigned-tx `0xef` prefix **equals** Paytaca `0x36` (0 mismatches). SeedCash never reads `0x36`.

If a PSBT is built with **divergent** `0x36` vs unsigned tx, SeedCash shows and signs the unsigned tx. Paytaca’s UI can show `getToken()` from `0x36`. That is a cross-wallet display split, not a SeedCash signing split.

### F4 — Genesis / token-out with no token-in → BCH UI
**Class:** WYSIWYS / review integrity · CashToken accounting  

`LoadingPSBTView` routes on **inputs** only (`inputs[0]` NFT else `inputs[1]` FT else BCH). Genesis (GEN-01/04/05/06/08, SCR-02/05, BCMR-01) has BCH inputs and token outputs → **BCH_ONLY**.

GEN-04 model contains `ft=1000000` on vout0. UI never opens the FT screen. User sees satoshis and a token-aware cashaddr (`bitcoincash:pp…`). Capability, commitment, FT amount are not reviewed.

This is not “feature not implemented so we refuse to sign”. SeedCash **will sign** genesis.

### F5 — Hybrid NFT+FT classified as NFT-only
**Class:** CashToken accounting · WYSIWYS  

`arrange_outputs`: `if nft elif ft`. Hybrid outputs (GEN-05, BCMR-01, MONSTER-01) go to the NFT bucket; FT amount is not in `outputs[1]`, so `ft_output_amount` / FT screen omit it. The `TxOutput.token.ft_amount` field itself is populated.

### F6 — OP_RETURN before a visible output (SCR-05, BCMR-01)
**Class:** WYSIWYS / review integrity  

`destination_addresses` = outputs **with** an address. `PSBTAddressDetailsView` shows `destination_addresses[i]` with `output_at_index(i).value_satoshis`.

SCR-05: vout0 OP_RETURN (no address, 0 sats), vout1 payment 98000 + NFT.

UI pairs:

| dest_index | shown address | amount from `output_at_index` |
| --- | --- | --- |
| 0 | payment (`pp8sfdh…`) | **0 sats, script `6a` (OP_RETURN)** |

The user is shown the **correct payment address with the OP_RETURN amount**. They can still sign 98000 + NFT. OP_RETURN **after** payments does not desync index 0.

### F7 — Change included as spend / destination
**Class:** WYSIWYS / review integrity  

`destination_addresses` is every P2PKH/P2SH output, including change. BCH overview `spend_amount = output_amount` (sum of all outputs). IO-1-2, IO-2-2, IO-2-3, IO-3-2: change is a “recipient”. Fee math remains `input - output` (correct). Not theft; review is inflated.

### F8 — NFT burn warning inverted / silent
**Class:** CashToken accounting · WYSIWYS  

`get_warning`: if any out is minting → `minting`; elif `len(nft_in) < len(nft_out)` → `burning`; elif equal, compare capability/commitment. **`len(in) > len(out)` (actual burn) is not handled.**

BURN-MULTI: NFT in=2, out=1, warning `None`. POST-04 (1/1 capability change) does warn `burning`. POST-01 minting baton present → `minting` (masks the `in < out` branch).

### F9 — UR/CBOR (fixed this session)
**Class:** UR/CBOR transport issue — **fixed in tree, not on device until flashed**  

Paytaca/`CryptoPSBT` stores CBOR(bstr(psbt)). SeedCash used to pass `.cbor` to `parse_psbt` → `invalid PSBT magic` (`0x59` vs `psbt\xff`). Unwrap is in `helpers/ur2/crypto_psbt.py`. This run: 21/21 UR roundtrips, `cbor_is_raw_psbt=False`.

### F10 — Signer constants `PSBT_OUT_AMOUNT=0x00`
**Class:** Hardening · False positive for signing  

`psbt_signer.py` labels output amount as `0x00` (that is redeem script in v2). Those constants are **not used** in `signed_psbt()`. Signing uses `unsigned_tx` + input `NON_WITNESS_UTXO`. No signing-correctness failure on these vectors.

### F11 — Proprietary `paytaca`/`metadata` ignored
**Class:** Unsupported feature · False positive  

Network/origin/purpose/creator are wallet metadata. SeedCash does not display them. Must not be trusted for amounts (Paytaca itself writes them as UTF-8 tags).

---

## 5. Security question

> Does SeedCash preserve exact BCH v145 transaction semantics from received PSBT through review to the signed tx?

| Stage | Preserved? |
| --- | --- |
| UR → bytes | Yes, after CBOR unwrap (firmware must be updated) |
| Bytes → unsigned tx / vin / vout / sats / `0xef` tokens | **Yes** (model matches Paytaca unsigned tx and `0x36`) |
| Bytes → PSBT v2/`0x36` maps | **No** (extra `00` shift; last output map dropped) |
| Model → UI review | **No** for genesis, hybrid FT, OP_RETURN-first amounts, change-as-spend, NFT burns |
| UI → signed tx | Signer signs **unsigned_tx**, not the UI. Signed tx **matches received unsigned tx** on these vectors. User can confirm a **wrong picture** of a **correct** tx |

No vector in this run showed SeedCash **altering** input/output scripts, amounts, or token prefixes in the transaction it would sign. The failures are **review integrity** and **v145 map interoperability**, plus genesis/hybrid/burn **accounting screens**.

A crafted PSBT with unsigned tx ≠ `0x36` is not represented in this corpus; SeedCash would follow the unsigned tx.

---

## 6. Format SeedCash must accept for Paytaca v145

Minimum to interoperate with Paytaca’s encoder (not a BIP):

1. Magic `psbt\xff`.
2. Global version **145** uint32 LE (`0xFB`).
3. Keep hybrid maps: unsigned tx **and** v2 counts / outpoint / amount / script.
4. After `input_count` input maps, **skip one extra `0x00`** before output maps (Paytaca `InputMap`).
5. Output `0x36` = token prefix including `0xef`; `0x04` = locking script only. Prefer reconstructing tokens from unsigned tx **and** checking they equal `0x36`.
6. UR type `crypto-psbt` payload = CBOR byte-string of the PSBT (BCR-2020-006), not raw magic bytes.
7. Do not require dropping v2 keys; do not convert the blob to BIP-174 v0 as a substitute for v145.

---

## 7. What is *not* a vulnerability

- Missing BCMR / Paytaca `purpose` UI: unsupported metadata.
- Token-aware cashaddr (`pp`/`pq`) vs raw P2PKH script: display convention, script on chain is still `76a914…88ac`.
- Extra `00` not changing the signed unsigned-tx: interoperability bug, not a consensus change.
- Live Paytaca JS agreeing with the lab on 5/5 vectors: the corpus is Paytaca v145, not a second dialect.

---

## 8. Suggested fix order (not done in this audit)

1. Flash SeedCash with UR CBOR unwrap (already in tree).
2. Skip Paytaca extra input separator in `parse_psbt` when `psbt_version==145` (or when the next map would be empty and `output_count` maps fit after one skip) — same rule as lab `decode_psbt`.
3. Route genesis (token outputs, no token inputs) into NFT/FT review, not BCH-only.
4. Pair address screens by the same filtered output list used for destinations (fixes SCR-05).
5. Classify hybrid as both NFT and FT; warn NFT burns when `n_in > n_out`.
6. Cross-check `0x36` vs unsigned tx and refuse or warn on divergence.
