# Paytaca psbt.js quirks (commit 9c338d2)

1. Extra `0x00` after input maps (serialize L1261, deserialize L1273).
2. `sortObjectKeys` by hex type; same-type keys insertion-ordered.
3. `sanitizeForVersion(145)` keeps unsigned tx and v2 fields.
4. Production `InputMap.serialize()` / `OutputMap.serialize()` ignore
   `psbtVersion` (functions take no parameter).
5. Key type is always the first byte (`slice(0,1)`).
6. Duplicate types become arrays; no BIP-174 uniqueness.
7. `getBip32Derivation()` returns `undefined` (not `{}`) when a single
   derivation was stored as a non-array KeyPair.
8. `encode()` reads tx version with `readCompactUint` on unsigned tx.
9. `getUnsignedTx` fallback does `tx.inputs.push` without initializing
   arrays — throws if unsigned tx missing.
10. `new Uint8Array[0]` if version missing on serialize (L1370).
11. Network proprietary always emitted; `utf8ToBin(decoded.network)`.
12. Output tokens on decode come from key `36` only.
13. `TX_VERSION` signed int32 write; `VERSION` unsigned uint32 write;
    locktime signed write / unsigned read.
14. `keypair.prototype = KeyPair` in input serialize (no-op).
15. Empty PSBT `70736274ff0000` cannot deserialize (no counts).
