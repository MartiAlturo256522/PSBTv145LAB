# Threat model — PSBT v145 generator and parser

## Assets

- Unsigned transaction bytes (authoritative)
- Previous transactions (`NON_WITNESS_UTXO`)
- Token amounts, categories, NFT capability/commitment
- BIP32 derivation / keys
- Host process integrity when parsing hostile PSBTs

## Attackers

1. Malicious PSBT creator (coordination server, QR, file)
2. UI that displays `0x36` instead of the unsigned tx
3. Combiner that reorders/drops maps
4. Supply-chain: dependency or path traversal on fixture load

## Trust boundaries

| Data | Trust for signing | Trust for display |
| --- | --- | --- |
| Unsigned tx outputs (with `0xef`) | yes | yes |
| `NON_WITNESS_UTXO` matching prevout | yes (must match) | yes |
| `PSBT_OUT_CASHTOKEN` `0x36` | **no** | no (warn if ≠ unsigned tx) |
| Proprietary `0xFC` | **no** | metadata only |
| Output `04` script | cross-check vs unsigned tx locking bytecode | yes if consistent |
| Input `0e`/`0f` | cross-check vs unsigned tx vin | yes if consistent |

Paytaca `decode()` copies output tokens from `36` only. That is a
Paytaca UI trust bug if `36` is attacker-controlled. Lab PSBT-06
encodes this case.

## Parser requirements (hostile input)

The parser MUST:

- Reject bad magic
- Reject truncated CompactSize / key / value
- Reject duplicate full keys (BIP-174; Paytaca does not — document)
- Reject trailing bytes after the last output map
- Bound allocations to remaining buffer (no `klen`/`vlen` beyond EOF)
- Not hang, not recurse unbounded, not execute scripts from PSBT keys
- Not follow filesystem paths encoded in proprietary values

## Generator requirements

- Deterministic given catalog id + dialect + sign state
- Must not silently drop token prefix from unsigned tx
- Must not let `0x36` diverge from unsigned tx unless the vector is a
  negative test
- paytaca-145 must be parseable by Paytaca `deserialize` (extra `00`)

## Out of scope

- Spending real UTXOs
- Network RPC to mainnet wallets
- Paytaca app UI XSS (separate product)
