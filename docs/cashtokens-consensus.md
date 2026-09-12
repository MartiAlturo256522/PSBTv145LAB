# CashTokens consensus (CHIP-2022-02 v2.2.2)

Authoritative: https://cashtokens.org/docs/spec/chip  
Implemented in lab: `src/ctlab/cashtokens/consensus.py` matching libauth `verifyTransactionTokens`.

## Prefix

```
0xef | category(32 HASH256 order) | bitfield | [CompactSize len][commitment] | [CompactSize amount]
```

Bitfield: `0x80` reserved must be 0; `0x40` has commitment; `0x20` has NFT; `0x10` has amount; nibble 0/1/2 = none/mutable/minting.

## Genesis

Input with **outpoint index 0** (parent vout, not vin). Category ID (UI hex) = display txid of that parent. Multiple such inputs → multiple categories. Coinbase (`0xffffffff`) cannot genesis. Spending a token-bearing vout=0 still genesises a **new** category equal to that parent txid.

## FT

All FT of a category created at genesis (sum ≤ 2^63−1). Later: output sum ≤ input sum. Amount 0 is omission of HAS_AMOUNT, not encoded zero.

## NFT

- Minting input: unlimited NFT outputs of that category, any capability except the algorithm allows minting copies.
- Mutable input: one successor, capability none or mutable, any commitment.
- Immutable input: one matching (category, commitment) output, or consume a leftover mutable to create a new immutable.

## Hybrid

One NFT + FT of the **same** category on one output.

## Sighash

Full token prefix immediately before coveredBytecode. `SIGHASH_UTXOS` (0x20) hashes all spent UTXOs after hashPrevouts; requires FORKID; incompatible with ANYONECANPAY.

## Commitment length

Upgrade 9 / CHIP: 40 bytes consensus. BCHN Upgrade 12 (May 2026): 128. Lab default 40. See `docs/discrepancies.md` D-COMMIT-MAX.
