# Agent O — Independent skeptic

Read `src/`, `tests/`, `vectors/`, `tools/` only. Did not treat lab
docs as truth. Compared against Paytaca `psbt.js` and libauth sources
on GitHub.

## Verdict

Calling the generator **VERIFIED** would be dishonest.

## Fatal interoperability

1. Lab omits Paytaca extra `0x00` after input maps.
2. Lab does not type-hex-sort keys (`00,0e,0f,10,03,06` vs
   `00,03,06,0e,0f,10`).
3. Lab `decode_psbt` now rejects trailing bytes, so a **real Paytaca**
   blob (extra `00` seen as empty output + leftover) will fail lab
   parse. **Neither direction interoperates.**
4. Proprietary order differs; unsigned vectors always include sighash.

Measured on PSBT-02: lab 708 bytes, Paytaca-faithful translation 709
bytes, first diff at offset 514 (key order). See
`audits/paytaca/psbt02-byte-diff.json`.

## Circular tests

- `psbt_match` is catalog expected vs the same generator.
- `try_libauth` / `try_bchn` hardcoded SKIPPED.
- Prefix CHIP hex uses palindrome `bb`×32.
- Round-trip tests use `bip174-v0`, not `paytaca-145`.
- If SeedCash imports, differential could PASS while ignoring `0x36`.

## Minimum bar (skeptic)

1. Live Paytaca JS deserialize of lab vectors **and** lab decode of
   Paytaca encode() bytes.
2. Explicit policy: clone extra `00` + sort, **or** stop calling the
   dialect Paytaca.
3. No PASS when oracles SKIPPED (partially done).
4. Negative tests that fail if the decoder is too loose — not catalog
   flags after successful decode.
5. Non-palindrome CHIP/libauth prefix goldens.
6. Tx decoder reject leftover bytes.

Until then the honest labels are: **self-consistent lab dialect**,
**Paytaca-inspired**, **unverified vs Paytaca JS**.
