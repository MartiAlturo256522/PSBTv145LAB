# SeedCash patches on GitHub HEAD `4e10166` + emulator `9d789cd`

These are the smallest correct fixes so SeedCash parses **actual** BCH PSBT v145 from PSBTLAB. They do not convert v145 to BIP-174, strip CashTokens, or special-case fixtures.

| File | Bug | Fix |
| --- | --- | --- |
| `helpers/ur2/crypto_psbt.py` | GitHub HEAD had no BCR-2020-006 unwrap. Paytaca UR payload is CBOR bstr. `parse_psbt` saw `58/59…` not `psbt\xff`. | wrap/unwrap CBOR bstr (tag 310 / tag 24 / raw magic). |
| `models/decode_qr.py` | `get_data_psbt()` returned `UR.cbor` verbatim. | `unwrap_psbt_cbor(...)` before parser. |
| `models/encode_qr.py` | Encoder put raw PSBT bytes as UR message (not CBOR). | `UR("crypto-psbt", wrap_psbt_cbor(psbt))`. |
| `helpers/ur2/fountain_encoder.py` | Multipart UR padded a `bytes` slice with `.append` → `AttributeError`. | Pad a `bytearray`. |
| `models/psbt_parser.py` | Extra Paytaca input-map `0x00` consumed as empty first output map. | Skip separator when `psbt_version == 145`. |
| `models/psbt_parser.py` | Hybrid NFT+FT used `elif`, so FT amount vanished from FT bucket. | NFT and FT checks are independent; hybrid is in both buckets. |
| `models/psbt_parser.py` | `destination_addresses` / `output_at_index(i)` assumed dest index == vout. | `destination_outputs()` keeps tx order, skips OP_RETURN only for the dest list. |
| `views/psbt_views.py` | Genesis (BCH parent, token outputs) routed as BCH_ONLY. | Route from input **or** output token buckets. |
| `views/psbt_views.py` | Address review paired dest `i` with `output_at_index(i)`. | Pair dest `i` with `destination_outputs()[i]`. |

Harness: `python tools/oracles/seedcash_pipeline.py --set all`
Report: `reports/seedcash-pipeline/dashboard.json`
