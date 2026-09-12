# First discrepancy report (before any generator “fix”)

Produced after FASE 1–2 source audit. Generator bytes were **not**
changed to match the translation (that would contaminate the oracle).

| ID | Finding | Evidence | Severity |
| --- | --- | --- | --- |
| D-PAYTACA-EXTRA-00 | Lab `Psbt.serialize` has no extra `00` after inputs. Paytaca `InputMap.serialize` L1261 does. | PSBT-02 lab 708 B vs translation 709 B; inspector `extra_input_separator=null` | **CRITICAL** incompatibility |
| D-KEY-ORDER | Lab input keys `00,0e,0f,10,03,06`. Paytaca type-hex sort `00,03,06,0e,0f,10`. | `audits/paytaca/psbt02-byte-diff.json` first_diff=514 | byte mismatch |
| D-PROP-ORDER | Lab proprietary: network, origin, creator, purpose. Paytaca encode: origin, creator, purpose, network (gated). | `dialect.py` vs `Psbt.encode` L1450+ | dialect |
| D-SIGHASH-ALWAYS | Unsigned lab vectors still write input `03`. | generator always passes `sighash=` | dialect |
| D-ORACLE-NONE | Node not installed; BCHN not installed; libauth JS not run. | `verify-v145` env | **BLOCKER** |
| D-SELF-TEST | Catalog `expected_*` vs same generator. | `test_corpus_generates_and_reports_matches` | contamination |
| D-PALINDROME | `test_prefix.py` category `bb`×32. | tests/unit/test_prefix.py | endianness untested in CHIP hex (fixed separately by `test_prefix_endian.py`, still not live libauth) |
| D-0x36-UI | Paytaca `decode()` trusts key `36` over unsigned tx. | psbt.js `getToken` | Paytaca quirk; lab PSBT-06 encodes the lie |
| D-TXID-ORDER | Paytaca `0e` may be UI-order; lab writes P2P `prev_txid`. | UNVERIFIED without JS | potential semantic |

**Policy:** do not patch `encode_psbt` until a live Paytaca oracle exists
or the project explicitly adopts the translation as a dialect target
(FASE 12). Patching now would make lab bytes match a Python clone of
Paytaca and look like progress without independent evidence.
