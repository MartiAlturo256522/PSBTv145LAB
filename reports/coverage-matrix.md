# Coverage matrix (campaign snapshot)

Counts are catalog scenarios + tests added this campaign. A non-zero cell
is **not** independent verification.

| Feature | Positive | Negative | Boundary | Differential | Fuzz | Real TX |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FT genesis | catalog GEN | NEG FT | amount max | self-only | prefix garbage | BLOCKED |
| NFT genesis | catalog GEN | NEG | commit 40/41 | self-only | prefix | BLOCKED |
| Hybrid genesis | GEN-05 | — | bitfield 0x30 | self-only | — | BLOCKED |
| Minting | POST | NEG-03 | — | self-only | — | BLOCKED |
| Mutable | POST | NEG-02/03 | — | self-only | — | BLOCKED |
| Immutable | POST | NEG-01/06 | — | self-only | — | BLOCKED |
| Multi-category | XGEN | — | — | self-only | — | BLOCKED |
| Burn | XGEN/POST | — | amount 0 omit | self-only | — | BLOCKED |
| PSBT v145 | PSBT-02 | PSBT-06..09 | version 145 LE | **FAIL vs Paytaca translation** | hostile maps | BLOCKED |
| Proprietary fields | generator always | — | — | order ≠ Paytaca encode() | — | — |
| NON_WITNESS_UTXO | all v0/v145 | PSBT-05 omit | — | BCHN dialect documented | — | BLOCKED |

Critical empty cells: **Real TX = 0**; **live Paytaca differential = 0**;
**live libauth differential = 0**.
