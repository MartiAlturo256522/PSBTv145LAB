# libauth CashTokens

Repo: https://github.com/bitauth/libauth  
Prefix encode/decode: `src/lib/message/transaction-encoding.ts`  
Consensus: `src/lib/vm/instruction-sets/bch/2023/bch-2023-tokens.ts` (`verifyTransactionTokens`)  
Fixtures: `src/lib/message/fixtures/token-prefix-{valid,invalid}.json` (copy of CHIP vectors)

Lab `encode_token_prefix` / `validate_transaction_tokens` follow this implementation.

**libauth has no PSBT codec.** Differential libauth status is SKIPPED unless a Node oracle is added.

Category in memory is UI/BE; `encodeTokenPrefix` reverses onto the wire.

Prefix parse does **not** enforce 40-byte commitments; `verifyTransactionTokens` does.
