# Audit C — BCHN oracle

**Status: BLOCKED**

`bitcoin-cli` / Bitcoin Cash Node is not installed on this host.

BCHN wallet PSBT input type `0x00` is a single `CTxOut`, not a full
previous transaction (`src/psbt.h` `PSBT_IN_UTXO`). That is a **different
dialect** from BIP-174 and from Paytaca (both use full prev tx).

Do not mark BCHN vs Paytaca PSBT bytes as a generator bug. Classify as
D-BCHN-UTXO (dialect).

Token-aware `decoderawtransaction` would be the right oracle for the
**unsigned transaction** layer (prefix, amounts, scripts), not for
Paytaca maps.

`try_bchn()` in `ctlab.validators.differential` is hardcoded SKIPPED.
SKIPPED is not PASS.
