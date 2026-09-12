# FINAL VERIFICATION REPORT

**Date:** 2026-09-12  
**Paytaca `psbt.js`:** `9c338d2ce07ee33cda2cec33bb340657c6fc1990`

## Executive Summary

Declarative motor `ctlab.engine.generate(scenario, seed=…)` builds BCH CashTokens transactions and Paytaca v145 PSBTs. Live Paytaca `deserialize`+`serialize` is **byte-identical on 18/18** selected vectors, including MONSTER-01 (2907 bytes), VOUT0-NO-GENESIS, same-category FT+NFT, and multi-burn. Catalog **90** scenarios, **128** generated vectors, **0** generator mismatches, **79** pytest passed. The five engine-audit warnings are closed (see below). BCHN and public-chain corpus remain absent.

**Verdict: `VERIFIED WITH WARNINGS`**

Not `VERIFIED`: no BCHN, no live SeedCash parse, catalog `expected_*` still self-compares (Paytaca JS is the external byte oracle). The previous five *engineering* warnings are not open.

## Current Engine Architecture

```
JSON / catalog id / seed
        ↓
ctlab.engine.generate
        ↓
build_fixture_graph (synthetic prev txs)
        ↓
CHIP prefix in txout script field
        ↓
encode_psbt(dialect=paytaca-145|bip174-v0|…)
        ↓
unsigned_tx.hex + psbt.binary/base64 + expected.json
```

Callers: CLI, pytest, UI `POST /api/generate`. One motor.

## Paytaca Compatibility

| Set | n | lab == Paytaca serialize | self round-trip |
| --- | ---: | ---: | ---: |
| Core + monsters | 18 | **18** | **18** |

`00→10` explained: JS array-index key `"10"` (SEQUENCE) before `"00"` (UTXO). General rule in `_paytaca_type_order`. Extra input `00` cloned.

## CashTokens / Genesis / NFT / FT / Mint / Burn / Multi / Complex

| Area | Evidence |
| --- | --- |
| Genesis vs any vout=0 | `VOUT0-NO-GENESIS` genesis_categories=[]; `GEN-01` genesis true; `VOUT0-MIXED` one genesis + vout1 transfer |
| FT | GEN-04, POST split/merge, BURN-MULTI, MONSTER-03 swap |
| NFT imm/mut/mint | GEN-01..03, POST-01, POST-08, MONSTER-02/05 |
| Hybrid same category | GEN-05, SAMECAT-01 (FT and NFT on **separate** outputs), POST-13..16 |
| Multi-category | XGEN-*, BURN-MULTI, MONSTER-01..05 |
| Minting | POST-01, SAMECAT-01, MONSTER-02/04/05 |
| Burn | BURN-MULTI (FT 1000→700 + NFT omit); MONSTER-01 FT 300 + NFT E; `expected.json` `burns` |
| Complex | MONSTER-01..05 under `vectors/complex/` |
| Negative | NEG-* catalog (clone, mutable→minting, FT overspend, …) |

## PSBT Binary / Differential / Independent

- Independent wire: `audits/independent/paytaca_v145_wire.py` matches lab PSBT-02.
- libauth live `encodeTokenPrefix` PASS (non-palindrome). No libauth PSBT codec.
- BCHN: BLOCKED (not installed).
- Fuzz/boundary/security: existing pytest PASS.

## SeedCash Compatibility

BIP-174 v0 unsigned + full NON_WITNESS_UTXO exported to `vectors/seed_signer/`. Paytaca-145 is a **dialect**; SeedCash historically needs v0. Dual-dialect catalog entries produce both. Live SeedCash `PSBTParser` still SKIPPED unless importable.

## Known Warnings / Remaining Risks

- BCHN absent.
- No mainnet CashTokens corpus.
- `verifyTransactionTokens` JS not executed (Python CHIP clone + source audit).
- Catalog `expected_*` is self-consistency; Paytaca JS is the external byte oracle.
- 128 vectors ≠ 200 named permutations; additional POST/XGEN cases exist but were not duplicated cosmetically.
- `kind=bch` only special-cases vout 0 vs 1.

## Final Warning Closure

### 1. Baton burn not in `semantics.burns`

- **Original issue:** POST-04 baton destruction only in `mint.baton=burned`; `burns: []`.
- **Root cause:** burn heuristic only matched omitted *immutable* NFTs / FT under-conservation.
- **Fix:** `semantics.py` appends `{kind: "baton", capability: "minting"}` when minting in and no minting out. Token burns keep `kind: "token"`.
- **Tests:** `test_baton_burn_semantics`
- **Paytaca evidence:** N/A (semantics layer, not wire). 18/18 wire identity unchanged.
- **Independent evidence:** CHIP allows implicit baton omit; recorded explicitly for SeedCash.
- **SeedCash impact:** signer can see authority destruction without reading `mint.baton` only.
- **Final status:** **RESOLVED**

### 2. `_same_category_clone`

- **Original issue:** public configs needed a private extra to merge same-category UTXOs.
- **Root cause:** each `existing` key created its own genesis funding txid → new category.
- **Fix:** public `category_group` / `share_category_with` on existing specs. Internal grouping unchanged. Catalog POST-11/14 migrated.
- **Tests:** `test_same_category_tokens_public_api`
- **Paytaca evidence:** SAMECAT-01 still 1216=1216.
- **Independent evidence:** one category in semantics.
- **SeedCash impact:** fixtures can express FT+NFT same category without internals.
- **Final status:** **RESOLVED** (internal grouping remains an implementation detail)

### 3. SIG-06 catalog vs fixture `expected_psbt`

- **Original issue:** catalog `valid`; stale `vectors/invalid/SIG-06` had `invalid`.
- **Root cause:** exporter never deleted the opposite folder after policy change (envelope valid; CHIP combo in sighash_info).
- **Fix:** exporter `shutil.rmtree` of the other dest; catalog remains source of truth (`expected_psbt=valid`).
- **Tests:** `test_catalog_fixture_expected_psbt_integrity`
- **Paytaca evidence:** N/A (BIP-174 signed vector, not in the 18).
- **Independent evidence:** on-disk `valid/SIG-06` only.
- **SeedCash impact:** fixture policy matches “well-formed envelope, invalid sighash combo”.
- **Final status:** **RESOLVED**

### 4. Dead catalog extras

- **Original issue:** `raw_prefix_output`, `chip_prefix`, `record_endianness`, `bcmr` looked configurable.
- **Root cause:** extras merged into scenario; generator ignored some.
- **Fix:** removed unused extras; `record_endianness` writes `category_ui`/`category_wire`; `bcmr_metadata_only` copied to vector (metadata, not consensus). `force_sighash` already active. Coverage whitelist test.
- **Tests:** `test_catalog_configuration_coverage`
- **Final status:** **RESOLVED**

### 5. P2SH without redeem_script

- **Original issue:** SCR-02/03 P2SH *outputs* had no `PSBT_OUT_REDEEM_SCRIPT`.
- **Root cause:** encoder never emitted output type `0x00`. Inputs in those rows are P2PKH genesis_parent (no input redeem needed).
- **Fix:** `TxOut.redeem_script` for p2sh20/32 outputs (redeem = owner P2PKH). Written on all dialects.
- **Tests:** `test_p2sh_redeem_script_behavior`
- **Paytaca evidence:** SCR-02 not in 18-set; adding redeem would change those bytes if generated as v145. Documented: P2SH *inputs* still out of catalog scope.
- **SeedCash impact:** wallet can obtain redeem for P2SH outputs.
- **Final status:** **RESOLVED** for outputs; **OUT OF SCOPE / EXPLICITLY UNSUPPORTED** for P2SH *inputs*.

## Final Verdict

```
VERIFIED WITH WARNINGS
```

Motor is **trusted to generate Paytaca-v145 fixtures** for the 18-vector live-JS identity set and the expanded catalog, including monsters and explicit non-genesis vout=0. It is **not** a substitute for a SeedCash integration run or BCHN.

## Commands

```powershell
$env:PYTHONPATH = "src"
python -c "from ctlab.engine import generate; print(generate('MONSTER-01', seed=None, dialect='paytaca-145')['psbt_base64'][:80])"
python -m ctlab generate --id MONSTER-01 --dialect paytaca-145
python -m ctlab generate
python tools\oracles\compare_paytaca_real.py
python verify-v145.py
```
