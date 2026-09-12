# Audit A — Paytaca reference

**Oracle status: BLOCKED for live JS. TRANSLATION available.**

## Pin

| Item | Value |
| --- | --- |
| Repo | https://github.com/paytaca/paytaca-app |
| HEAD | `6e8954511b1e0871cf1632f770665323d424f2a2` (2026-09-11) |
| `psbt.js` commit | `9c338d2ce07ee33cda2cec33bb340657c6fc1990` (2026-04-03) |
| App | v0.27.0 |
| Libauth | `@bitauth/libauth@^3.1.0-next.4` via `bitauth-libauth-v3` |
| File | `src/lib/multisig/psbt.js` (1731 lines) |

Fetched independently from GitHub raw. Lab docs were not used as truth.

## What v145 is

Not a BIP. Paytaca `setPsbtVersion(145)` comment: “Using BCH's bip44
cointype as PSBT version / TODO: Create CHIP”. Value is uint32 LE
`91 00 00 00` under key `fb`.

## Confirmed quirks (from source)

1. **Extra `0x00` after all input maps** (`InputMap.serialize` L1261,
   `deserialize` L1273). BIP-174 parsers see an empty extra output.
   Paytaca parsers skip one extra byte. **Incompatibility, not
   equivalent encoding.**
2. **`sortObjectKeys` on hex type strings**, not full-key order.
3. **Hybrid v0+v2**: unsigned tx AND v2 counts/prevouts/amounts.
   `sanitizeForVersion(145)` no-op.
4. **`PSBT_OUT_CASHTOKEN = 0x36`**: value = libauth `encodeTokenPrefix`
   including `0xef`. Output `04` is locking bytecode only.
5. **No input token key.** Tokens from `NON_WITNESS_UTXO` via
   `decodeTransactionBch`.
6. **`WITNESS_UTXO` never written.**
7. **Duplicates accepted** (type-keyed arrays).
8. **`decode()` output tokens come from `36` only**, not unsigned tx.
9. **`InputMap.serialize(psbtVersion)` drops the version argument** so
   input/output sanitizers do not run on the production path.
10. **Count 0 unparsable** (`if (!inputCount)`).

## Lab vs Paytaca bytes

See `paytaca_codec.py` (translation, **not** live JS).

On lab `paytaca-145` vectors inspected in this campaign:

- Extra input separator: **absent**
- Input key order: insertion `00,0e,0f,10,03,06` not type-sorted
  `00,03,06,0e,0f,10`
- `36` does start with `ef` when present
- `04` does not start with `ef`

**Conclusion:** field *set* is in the Paytaca ballpark; **byte stream is
not Paytaca-canonical**. Live `Psbt.deserialize` of a lab blob is
expected to desync on the first output map.

## Files

- `paytaca_codec.py` — translation of serialize/parse rules
- `quirks.md` — short list
- Spec: `docs/PSBT-V145-PAYTACA-SPEC.md`
