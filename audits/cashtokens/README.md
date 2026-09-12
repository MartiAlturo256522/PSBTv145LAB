# Audit D — CashTokens (CHIP v2.2.2)

Independent comparison: CHIP text + libauth `verifyTransactionTokens`
source vs `src/ctlab/cashtokens/{prefix,consensus}.py`.

| Rule | CHIP | Lab | vs libauth |
| --- | --- | --- | --- |
| Genesis = prevout.n==0 not vin | yes | `consensus.py:72-75` | MATCH |
| FT only at genesis | yes | `consensus.py:125-145` | MATCH |
| Minting → unlimited NFTs | yes | `available_minting` skip | MATCH |
| Mutable one successor, not minting | yes | mutable leftover + unmatched immutable | MATCH |
| Immutable (category, commitment) | yes | pop one match | MATCH |
| Hybrid NFT+FT same output | yes | `Token.amount` + `nft` | MATCH |
| One category / one NFT per output | structural | one `Token` | MATCH |
| Burns by omission | yes | no under-conservation fail | MATCH |
| Multi-category | yes | per-category maps | MATCH |
| Commitment max | 40 (CHIP/2023) | 40 | MATCH 2023; not Upgrade 12 (128) |
| Prefix `0xef` + bitfield + compact | yes | `prefix.py` | MATCH |

Caveats (not protocol mismatches):

- Prefix **hex tests** use palindrome category `bb`×32 — endianness not
  asserted. Implementation **does** reverse.
- FT “or genesis” vs defined `availableSum`: lab = libauth, theoretically
  stricter than CHIP wording (PATFO edge).
- This conservation code is **not** an independent oracle for the PSBT
  generator: the generator calls the same functions.

Catalog coverage exists for GEN/POST/XGEN/NEG. Unit tests do not cover
multi-category; catalog does.
