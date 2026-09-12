# FINAL_TEST_REPORT

CashTokens PSBT Test Vector Laboratory v0.1.0  
Generator seed: BIP-39 `abandon`×11 + `about`, path `m/44'/145'/0'/{change}/{index}`  
Date: 2026-09-12

## Counts

| Metric | Value |
|---|---|
| Catalog scenarios | 80 |
| Generated vectors (scenario × dialect × sign state) | 98 |
| Positive consensus | 64 catalog |
| Negative consensus | 16 catalog |
| Negative PSBT | 14 catalog |
| PSBT variants (distinct dialects in corpus) | 4 (`bip174-v0` 82, `paytaca-145` 14, `bip370-v2` 1, `bchn-v0` 1) |
| Signing variants | unsigned 79, signed 18, partial 1 |
| Script variants | p2pkh, p2sh20, p2sh32, bare P2PK, OP_RETURN |
| Cross-category vectors | 7 XGEN + GEN-08 + GEN-15 |
| pytest | 30 passed (unit, integration, golden, property, fuzz, differential) |
| Generator self-consistency mismatches | **0** |

## Differential

| Oracle | Result |
|---|---|
| Our consensus + PSBT decoder | PASS on all 98 (expected vs actual match) |
| libauth JS | SKIPPED (no Node oracle wired) |
| BCHN `bitcoin-cli` | SKIPPED (node not required) |
| Paytaca JS `Psbt.decode` | SKIPPED (dialect encoded from source; not executed) |
| SeedCash `PSBTParser` | optional; SKIPPED unless `seedcash` is on PYTHONPATH at report time |

SKIPPED is **not** PASS. Live cross-implementation is the next hardening step.

## Fuzz / property

- CompactSize truncated inputs raise, no hang
- `0xef` + junk raises `TokenPrefixError` (does not become BCH-only)
- PSBT bad magic / truncated / duplicate keys rejected
- Prefix encode→decode grid (capability × commitment × amount)
- GEN-01 / GEN-04 determinism (txid, PSBT, signatures)

## Independent review (skeptic)

Substantive findings and disposition:

| Finding | Disposition |
|---|---|
| SIGHASH_SINGLE hashed `hashSequence` (BIP-143 zeros it) | **Fixed** in `sighash.py`; unit test added |
| Post-genesis token UTXOs sat at vout=0 (also genesis) | **Fixed**: dummy BCH at vout=0, tokens at vout=1. GEN-15 remains the vout=0 case. POST-01 now `genesis_categories: []` |
| Invalid prefixes destroyed the PSBT and mis-labelled the envelope | **Fixed**: tx decoder keeps raw field; NEG-08 is now `consensus=invalid`, `psbt=valid` with bytes |
| SIG-06 `expected_psbt=invalid` for a well-formed envelope | **Fixed**: envelope valid; CHIP-invalid combo recorded in `sighash_info` |
| libauth/BCHN oracles stubbed | **Open** — documented SKIPPED, not PASS |

## Known limitations

1. libauth/BCHN/Paytaca JS oracles not executed in CI.
2. Commitment max default **40** (CHIP / Upgrade 9). BCHN Upgrade 12 allows 128.
3. Catalog is a **covering set** (~80 scenarios / 98 variants), not the 350–400 dense expansion.
4. Multisig / covenant scripts are not full CHIP inspection-opcode contracts; SCR-02/03 are hash-locked scripts.
5. Schnorr matches SeedCash (RFC6979, untagged SHA256, Jacobi of R.y). Not independently compared to libauth in this run.
6. UI is a local developer tool; no browser-driver suite. API + static page verified via import and HTTP.
7. Nested GitHub workflow under `cashtokens-psbt-lab/.github` is **not** picked up unless the lab is the git root; copy to repo-root `.github/workflows` to run on SeedCash CI.

## Unresolved discrepancies

See `docs/discrepancies.md`. Principal:

- Paytaca v145 is a dialect, not a BIP
- BCHN input 0x00 is CTxOut, not prev tx
- SeedCash UI is genesis-blind and hybrid-blind
- Upgrade 9 vs 12 commitment length

Failed SeedCash interpretations of **valid** PSBTs are the point of this corpus, not something to greenwash.
