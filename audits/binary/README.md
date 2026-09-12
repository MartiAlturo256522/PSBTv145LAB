# Audit E — PSBT binary forensics

Independent walker: `tools/psbt_inspector.py`, `tools/psbt_hexdump.py`.
No `ctlab` imports. Uses `audits/paytaca/paytaca_codec.py` only for
CompactSize + extra-separator parse.

Each record:

```
offset, kind, map, key_length, key_bytes, value_length, value_bytes
```

The inspector tries BIP-174 maps first, then Paytaca extra `00` after
inputs. Trailing bytes make `ok=false`.

Expected findings on lab `paytaca-145` vectors:

- `parse_dialect = bip174`
- `extra_input_separator = null`
- input key order not type-sorted when sighash (`03`) and derivation
  (`06`) follow v2 prevout fields
- `36` values start with `ef`
- `04` values do not start with `ef`
