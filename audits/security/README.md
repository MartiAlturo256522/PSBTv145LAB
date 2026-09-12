# Audit R — Security review (parser / generator)

Scope: local lab, no network wallet, no real funds.

## Parser (`src/ctlab/psbt/codec.py` `_parse_map`)

Historical issues (pre-fix in this campaign):

1. `key = buf[pos:pos+klen]; pos += klen` does not reject `klen` past
   EOF (Python slice silently shortens; `pos` can walk past `len(buf)`).
2. Same for values.
3. Trailing bytes after the last output map ignored.
4. `PSBT_GLOBAL_VERSION` non-4-byte values decoded as CompactSize
   (SeedCash quirk), so a hostile version field may be accepted.

Paytaca JS: `readBytes(Number(valueLen))` will throw on overrun if
libauth checks remaining length; not verified live.

## Generator

- No filesystem paths from PSBT keys.
- Proprietary values are UTF-8 labels from a fixed helper
  (`paytaca_global_fields`), not user paths.
- UI (`app/server.py`) is out of this campaign’s “do not build UI”
  scope; XSS on displaying PSBT hex is a separate review.

## Hostile corpus (verify-v145 security section)

Must reject: truncated magic, truncated maps, duplicate global `00`,
huge CompactSize claiming more bytes than remain, trailing garbage,
empty key (separator) in the middle of a pair stream is just end-of-map.

Must not: hang, unbounded allocation from a lying CompactSize when
remaining buffer is small (allocation is `buf[pos:pos+n]` of remaining).

## Dependencies

`ecdsa`, `fastapi`, `uvicorn` — not used by the codec. No
`eval`/`exec`/`pickle` in `ctlab.psbt` or `ctlab.cashtokens`.
