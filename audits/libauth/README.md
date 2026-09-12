# Audit B — libauth oracle

**Status: BLOCKED**

libauth has **no PSBT codec**. It is the oracle for:

- `encodeTokenPrefix` / `readTokenPrefix`
- `encodeTransaction` / `decodeTransaction` / `decodeTransactionBch`
- `verifyTransactionTokens`

## Pin (from Paytaca package.json)

`bitauth-libauth-v3` = npm `@bitauth/libauth@^3.1.0-next.4`

Upstream sources (not executed here):

- https://github.com/bitauth/libauth/blob/master/src/lib/message/transaction-encoding.ts
- https://github.com/bitauth/libauth/blob/master/src/lib/vm/instruction-sets/bch/2023/bch-2023-tokens.ts

`encodeTokenPrefix`: `Uint8Array.of(0xef) || category.reverse() || bitfield || …`

## What this host can do

- `audits/libauth/chip_prefix.py` is a CHIP transcription. Matching it
  against `ctlab.cashtokens.prefix` is **in-repo second implementation**,
  not an oracle (methodology rank 6).
- Official CHIP prefix hex vectors use category `0xbb`×32 (**palindrome**).
  They do not prove endianness.
- Node.js was not available at campaign start. Until `@bitauth/libauth`
  runs, libauth differential = **SKIPPED**.

## Lab differential.py

`try_libauth()` is hardcoded SKIPPED. That is honest about absence, but
`differential_report` still returns PASS when the generator matches its
own catalog. That PASS is **not** a libauth result.
