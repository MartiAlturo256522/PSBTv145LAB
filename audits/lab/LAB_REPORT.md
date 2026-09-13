# Synthetic BCH PSBT v145 laboratory — report

**Branch:** `lab/synthetic-v145-campaign`  
**Campaign version:** `0.2.0`  
**Frozen motor:** `ctlab.engine.generate` 0.1.0 (unchanged)  
**Paytaca pin:** `psbt.js @ 9c338d2`  
**SeedCash:** not patched (read-only adapter)

---

## A. Architecture

The laboratory is a **layer on top of the frozen Paytaca-v145 motor**, not a replacement.

```
TransactionIntent  (ground truth: roles, tokens, scripts, sighash)
        │
        ▼
to_engine_config()  →  ctlab.engine.generate(dialect="paytaca-145")
        │
        ├─ unsigned BCH tx (CashTokens in 0xef script field)
        ├─ Paytaca PSBT v145 bytes
        └─ semantics / txid
        │
        ├─ maps.walk_paytaca_v145     (skips extra input 0x00)
        ├─ maps.walk_naive_no_skip    (SeedCash-like)
        ├─ paytaca_diff.compare_vector (live JS deserialize+serialize)
        ├─ ur.wrap_psbt_cbor / roundtrip_ur
        ├─ mutate_psbt / mutate_intent / shrink_intent
        └─ seedcash_adapter.capture → oracle.evaluate
              A transaction_correctness
              B psbt_semantic_correctness
              C review_correctness
```

Package: `src/ctlab/lab/`  
CLI: `python -m ctlab lab <cmd>`

The frozen catalog, codec, and `ENGINE_FREEZE.md` motor are **not** rewritten. Golden M0 lives in `vectors/regression/seedcash-v145-m0/`.

---

## B. Protocol model (PSBT v145)

v145 is **Paytaca’s BCH extension of PSBT v2**, not BIP-174 and not BIP-44 `145'`.

On the wire (from `psbt.js` + live JS):

| Field | Meaning |
| --- | --- |
| `0xFB` GLOBAL_VERSION | uint32 LE **145** |
| `sanitizeForVersion(145)` | no-op; v0 **and** v2 keys kept |
| Global `00` | unsigned tx (tokens already in txout scripts) |
| Global `02`/`03`/`04`/`05` | tx version, locktime, input/output counts |
| Input `00` + `0e`/`0f`/`10` | prev tx + v2 outpoint/sequence |
| Output `03`/`04` | amount + locking script **without** `0xef` |
| Output `36` | `encodeTokenPrefix` **with** `0xef` |
| Extra `00` after input maps | Paytaca `InputMap.serialize` L1261 |

Independent walker: `ctlab.lab.maps.walk_paytaca_v145`.

---

## C. Paytaca compatibility

Live `Psbt.deserialize+serialize` vs lab bytes:

| Vector | Byte-identical |
| --- | --- |
| GEN-04, IO-2-3, SCR-05, POST-01, MONSTER-01 | **yes** (frozen `live_paytaca_byte_eq=true`) |

`tests/lab/test_paytaca_live_m0.py` re-checks these five on every CI run.  
Semantic identity (version 145, extra separator, `0x36` == unsigned-tx prefix) is asserted even if Node is missing.

A byte difference is **not** automatically a semantic difference. Extra-`00` vs BIP-174 is a **Paytaca layout** fact, not a Bitcoin PSBT version.

---

## D. Generator capabilities

| Mode | What it emits |
| --- | --- |
| **M1** | Cardinalities 1/1, 1/2, 2/1, 2/2, 2/3, 3/2, 6/6 × P2PKH, P2SH20, OP_RETURN-first, payment+change |
| **M2** | FT genesis, NFT genesis, hybrid minting+FT, NFT transfer, mint+baton, NFT burn 2→1, FT split, mixed BCH+token |
| **NORMAL** | Random 1–6 in/out, P2PKH, optional change/OP_RETURN |
| **CASH_TOKENS** | M2 + random genesis/FT/NFT |
| **WYSIWYS** | OP_RETURN-first / token-first orderings |
| **ADVERSARIAL** | Hidden outputs, index traps, extra-00 family |
| **MONSTER** | 6–10 in/out mixed |
| **EXHAUSTIVE** | M1 ∪ M2 |
| **SIGHASH** | ALL/NONE/SINGLE × FORKID × ACP × UTXOS (`sighash_cases.py`) |
| **extra00 family** | 1/2/3 outputs × first/last token, OP_RETURN, P2SH, P2PKH |
| **mutations** | unsigned-only swap, `0x36`-only mutate, drop last map, dup unsigned, truncate, bad magic, remove extra `00`, reorder maps, insert empty map |

Hybrid NFT+FT is **both** amount and capability. The generator does not use `if nft elif ft`.

---

## E. Corpus statistics (this session)

| Corpus | n | Notes |
| --- | ---: | --- |
| Frozen M0 golden | **21** | sha256-locked; 5 live Paytaca |
| M1 generate | **21** | all ok |
| M2 generate | **8** | all ok |
| extra00 family | **20** | naive empty first map on all; last map dropped when n_out>1 |
| NORMAL campaign `--count 80 --seed 20260913` | **80** | all ok |
| Coverage sample (M1+M2+80) | **109** intents | n_in/n_out 1–6 filled |
| pytest lab+regression | **37+** passed | includes live Paytaca + UR + extra00 + oracle axes |

10_000-vector production campaign is **wired** (`--count 10000`) but not burned in this run; M1–M4 are proven first as required.

Coverage gaps still listed: `hybrid` dimension (M2 hybrid exists; tracker may classify as genesis), `change-first` ordering, some 4×2 / 5×6 / 6×4 cardinalities.

---

## F. Differential findings (Paytaca vs lab vs SeedCash)

| Axis | Paytaca-aligned lab | SeedCash |
| --- | --- | --- |
| Unsigned tx / vin / vout / sats / `0xef` tokens | match intent | **match** (model from unsigned tx) |
| Output maps `03`/`04`/`36` | correct | extra `00` → empty first map; last map dropped |
| GLOBAL_VERSION 145 | yes | parsed as 145 |
| UR CBOR bstr | roundtrip bytes | unwrap in SeedCash tree; lab `ur.py` independent |
| Signed tx | N/A | follows unsigned tx (`SIGNED_FOLLOWS_UNSIGNED_TX`) |

On 12 M1+M2 SeedCash evaluations: **10 LOW** (map shift, signed tx unchanged), **2 CRITICAL** (OP_RETURN-first index confusion).

---

## G. Security findings (minimal reproducers)

### F-WYSIWYS-OPRETURN (CRITICAL)

- **Repro:** `M1-2-2-opreturn` or frozen `SCR-05`
- OP_RETURN at vout0, payment at vout1
- SeedCash shows payment **address** with **0 sats** / script `6a`
- A PASS: signed tx still correct
- C FAIL: review lies
- Command: `python -m ctlab lab compare-seedcash --count 12`

### F-GENESIS-BLIND (HIGH)

- **Repro:** frozen `GEN-04` / intent `M2-genesis-ft`
- Model has 1_000_000 FT; UI route `BCH_ONLY`
- `tests/lab/test_oracle_axes.py::test_gen04_review_fail_bch_only_tx_ok`

### F-EXTRA00-MAP-SHIFT (LOW / interoperability)

- **Repro:** any v145 with ≥1 output; family `python -m ctlab lab extra00`
- 1-out: SeedCash output maps `[[]]` (`0x36` discarded from maps)
- 3-out: last Paytaca output map never parsed
- Signed tx **unchanged** (unsigned tx)

### F-CHANGE-AS-DEST (LOW / review)

- **Repro:** `M1-1-2-p2pkh-paychange`
- Change listed as a destination; spend = all outputs

Mutants that **diverge unsigned tx vs `0x36`** (`mutate_0x36_amount`, `swap_outputs_in_unsigned_only`) are classified SECURITY-SENSITIVE for a coordinator attack; SeedCash follows unsigned tx.

---

## H. Coverage gaps

- `change-first` ordering not yet in the 109-intent mix
- Hybrid classified as genesis in the coverage counter (intent is hybrid)
- P2SH32 / bare / unknown scripts not in M1
- Sighash NONE/SINGLE/UTXOS generated but not in default campaign
- 100k fuzz campaign not executed (CLI `lab fuzz` exists)
- Live Paytaca JS only auto-checked on the five M0 vectors in CI
- Melt-as-distinct-from-burn not a separate M2 id
- Fountain UR reordering/missing fragments not yet a fuzzer family

---

## I. Reproducibility

```powershell
cd C:\Users\reque\Desktop\PSBTLAB
$env:PYTHONPATH = "src;C:\Users\reque\seedcash\src"

python -m pytest tests/lab tests/regression -q
python -m ctlab lab generate --m1 --seed 20260913
python -m ctlab lab generate --m2 --seed 20260913
python -m ctlab lab generate --count 80 --seed 20260913
python -m ctlab lab generate --tokens --count 50 --seed 20260913
python -m ctlab lab generate --adversarial --count 50 --seed 20260913
python -m ctlab lab extra00
python -m ctlab lab compare-paytaca
python -m ctlab lab compare-seedcash --count 12
python -m ctlab lab mutate --id GEN-04
python -m ctlab lab coverage --count 80 --seed 20260913
python -m ctlab lab inspect vectors\regression\seedcash-v145-m0\GEN-04.psbt.hex
python -m ctlab lab fuzz --count 20 --seed 20260913
```

Same `--seed` + `LAB_CAMPAIGN_VERSION` + frozen motor ⇒ same fixtures.  
M0 sha256 in `vectors/regression/seedcash-v145-m0/index.json`.

---

## J. Next actions

**SeedCash (do not patch to green the oracle):**

1. Skip Paytaca extra input `00` when version==145 (fixes map shift / lost last `0x36`).
2. Pair UI amounts with the **filtered** destination list (fixes CRITICAL OP_RETURN-first).
3. Route genesis token-outs (no token-ins) into NFT/FT review, not BCH_ONLY.
4. Treat hybrid as NFT **and** FT; warn when NFT in > out.
5. Flash UR CBOR unwrap already in the SeedCash tree.

**Laboratory-only:**

- Run `--count 10000` then `--count 100000 --adversarial --tokens`
- Add change-first + hybrid coverage generator bias
- Wire shrinking into `lab fuzz` on first CRITICAL
- Persist campaign JSON under `vectors/lab/`
- Optional: independent serializer that does not call `encode_psbt` (second implementation)

The oracle must keep failing while SeedCash review is wrong. That is the point.
