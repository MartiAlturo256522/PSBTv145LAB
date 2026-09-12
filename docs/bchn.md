# Bitcoin Cash Node

- Consensus: `src/consensus/tokens.cpp` `CheckTxTokens`; `src/primitives/token.h`.
- Matches CHIP genesis (`prevout.GetN()==0`), FT conservation, NFT algorithm.
- RPC `decoderawtransaction` / `decodepsbt` expose `tokenData` (category explorer hex, nft capability/commitment, amount).
- PSBT is **v0 only**. Input type 0x00 is **`PSBT_IN_UTXO` = one CTxOut**, not a full previous transaction. BIP-174 wallets that expect a prev tx at 0x00 cannot parse BCHN PSBTs and vice versa.
- Default `walletprocesspsbt` sighash `ALL|FORKID`; UTXOS accepted after May 2023.
- Upgrade 12 (May 2026) raises commitment max 40 → 128. Lab NEG-07 follows CHIP 40.

BCHN binary is not required to generate the corpus. Differential `bchn` status is SKIPPED unless `bitcoin-cli` is configured.
