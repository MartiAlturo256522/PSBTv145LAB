# Architecture map (verification campaign)

```
catalog.py  ──► generator.py ──► encode_transaction
                    │                    │
                    │                    ▼
                    │            unsigned tx (0xef in script field)
                    │                    │
                    ├── encode_psbt(dialect)
                    │     bip174-v0 | bip370-v2 | paytaca-145 | bchn-v0
                    │
                    ▼
              vectors/**/psbt.binary

Independent (no ctlab.psbt.codec):
  tools/psbt_inspector.py
  tools/psbt_hexdump.py
  audits/paytaca/paytaca_codec.py   ← translation, NOT live Paytaca
  audits/libauth/chip_prefix.py     ← CHIP transcription, NOT live libauth

Blocked oracles:
  Paytaca psbt.js  (Node)
  @bitauth/libauth (Node)
  BCHN bitcoin-cli
```

SUT: `src/ctlab/psbt/codec.py` `encode_psbt(..., dialect="paytaca-145")`.

Do not use generator output as the expected oracle for the same generator.
