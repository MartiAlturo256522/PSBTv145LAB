# PAYTACA PSBT V145 VERIFICATION

Generated: 2026-09-12T17:04:48.722640+00:00
Paytaca psbt.js: `9c338d2ce07ee33cda2cec33bb340657c6fc1990`
Paytaca HEAD: `6e8954511b1e0871cf1632f770665323d424f2a2`

## Environment

- Python: 3.11.9
- Node: C:\Users\reque\seedcash\cashtokens-psbt-lab\tools\node\node-v20.19.5-win-x64\node.exe
- BCHN: NOT FOUND

## Dashboard

```
PAYTACA PSBT V145 VERIFICATION

Protocol docs:          PASS
Paytaca identified:     PASS
Binary encoding:        PASS
CashTokens:             WARN
Genesis:                WARN
Minting:                WARN
Mutable:                WARN
Immutable:              WARN
Fungible Tokens:        WARN
Hybrid:                 WARN
Multi-category:         WARN
PSBT fields:            PASS
Paytaca differential:   PASS
libauth differential:   PASS
BCHN differential:      BLOCKED
Property tests:         PASS
Fuzz tests:             PASS
Boundary tests:         PASS
Security tests:         PASS
Real TX corpus:         BLOCKED
Determinism:            PASS
Independent oracles:    WARN
Skeptic:                WARN

Critical discrepancies:  0
Open blockers:           0

FINAL STATUS:
VERIFIED WITH WARNINGS
```

## Blockers

None.

## PSBT-02 byte inspection

```json
{
  "bytes_equal_paytaca_translation": true,
  "byte_diff": {
    "equal": true,
    "len_a": 702,
    "len_b": 702,
    "first_diff": null,
    "a_at": "",
    "b_at": ""
  },
  "inspector": {
    "version": 145,
    "parse_dialect": "paytaca",
    "extra_input_separator": 623,
    "global_key_order": [
      "00",
      "02",
      "03",
      "04",
      "05",
      "fb",
      "fc",
      "fc",
      "fc",
      "fc",
      "fc",
      "fc",
      "fc",
      "fc"
    ],
    "input_key_orders": [
      [
        "10",
        "00",
        "06",
        "0e",
        "0f"
      ]
    ],
    "inputs_type_sorted": true,
    "has_0x36": true,
    "0x36_starts_with_ef": true,
    "0x04_starts_with_ef": [
      false
    ],
    "trailing": "",
    "ok": true
  }
}
```

## Catalog

- scenarios: 90
- paytaca-145 ids: 28
- groups: {"genesis": 18, "cross-genesis": 7, "post-genesis": 17, "negative": 16, "encoding": 4, "psbt": 10, "sighash": 6, "script": 5, "metadata": 1, "hybrid": 1, "complex": 5}

## Verdict notes

Paytaca REAL `deserialize`+`serialize` is the oracle for v145 bytes.
JS `Object.keys` after `sortObjectKeys` puts integer type keys (`10`, `36`)
before leading-zero hex types (`00`). Lab clones that rule.
BCHN and public-chain corpus remain optional/blocked.

## Remaining warnings

Catalog expected_* still self-compares. BCHN not installed.
libauth has no PSBT codec. Live `verifyTransactionTokens` not executed.

