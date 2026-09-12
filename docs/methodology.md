# Verification methodology

## Oracle ranking (never invert)

1. Live Paytaca `psbt.js` (`Psbt.serialize` / `deserialize` / `encode`)
2. Live libauth (`encodeTokenPrefix`, `encodeTransaction`, `verifyTransactionTokens`)
3. BCHN (`decoderawtransaction`, token-aware tx)
4. CHIP-2022-02-CashTokens v2.2.2 and BIP-174 / BIP-370 text
5. Independent parsers in this repo that **do not import** `ctlab.psbt.codec`
6. In-repo second implementation (translation) — **not** an oracle
7. Generator under test

If (6) and (7) agree, that is self-consistency, not verification.

## What counts as PASS

A check PASSes only when an oracle at rank ≤ 5 agrees, or when a
negative test shows a clean reject of hostile input.

SKIPPED is not PASS. A pytest that asserts `status in ("PASS", "FAIL")`
is not a test.

## Layers (never conflate)

| Layer | What is true |
| --- | --- |
| Consensus (CHIP) | Token conservation, genesis = prevout.n==0, prefix in txout |
| P2P tx | `0xef` in the output script field |
| Sighash | FORKID, optional UTXOS, prefix in covered bytecode |
| BIP-174/370 | Map structure, versions 0 and 2 only |
| Paytaca dialect | Version 145, key `36`, extra input `00`, hybrid v0+v2 |
| Wallet metadata | `0xFC` paytaca/metadata — not consensus |
| SeedCash UI | Display bugs are not protocol bugs |

## Phases

1. Audit existing lab code (done)
2. Audit Paytaca from source (done; JS not executed)
3. Executable spec (`docs/PSBT-V145-PAYTACA-SPEC.md`)
4. Independent oracles (Python translation + inspector; live JS/BCHN blocked)
5. Differential harness (`verify-v145`)
6. Corpus (existing catalog; real-chain corpus not fetched)
7. Fuzz (bounded; in-repo parser)
8. Property tests (in-repo round-trip)
9. Real TX (public chain corpus: not built)
10. Security (hostile PSBT)
11. Independent skeptic
12. Fix generator only after blockers are documented
13. Re-run `./verify-v145`

## Reproducibility

```
python -m ctlab generate --id PSBT-02 --dialect paytaca-145 --sign unsigned
python tools/psbt_inspector.py vectors/valid/PSBT-02/psbt.binary
python verify-v145.py
```

Deterministic seed: mnemonic `abandon` × 11 + `about`, path
`m/44'/145'/0'/{change}/{index}`.
