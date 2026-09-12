# ENGINE FREEZE — CashTokens PSBT v145 motor

**Version:** `GENERATOR_VERSION` 0.1.0 (`ctlab.__init__`)  
**Frozen:** 2026-09-12  
**Paytaca pin:** `paytaca-app` `psbt.js` @ `9c338d2ce07ee33cda2cec33bb340657c6fc1990`

Do not change architecture unless a demonstrated bug appears.

## Architecture

```
generate(scenario, seed?, dialect?, sign?)
    → fixture graph (synthetic prev txs)
    → CHIP token prefix in txout
    → encode_psbt (paytaca-145 | bip174-v0 | bip370-v2 | bchn-v0)
    → unsigned_tx.hex / psbt.binary / psbt.base64 / expected.json
```

Public entry: `ctlab.engine.generate`. CLI/UI must call this.

## Input

Catalog id string or declarative dict:

```json
{
  "existing": [
    {"key": "A1", "category_group": "A", "token": {"amount": 40, "nft": null}},
    {"key": "A2", "category_group": "A", "token": {"amount": 0, "nft": {"capability": "none", "commitment": "id"}}}
  ],
  "inputs": [{"kind": "token", "key": "A1"}, {"kind": "token", "key": "A2"}],
  "outputs": [{"owner": "bob", "sats": 14000, "token": {"category_from_existing": "A1", "amount": 40, "nft": {"capability": "none", "commitment": "id"}}}]
}
```

`category_group` (or `share_category_with`) is the public same-category API. Do not use `_same_category_clone` in new specs.

Kinds: `genesis_parent` (vout=0 genesis), `token` (default parent vout=1, not genesis), `bch` (`vout` 0 or 1).

## Output

`unsigned_tx.hex`, `psbt.hex` / `.binary` / `.base64`, `vector.json`, `expected.json` (genesis/mint/burns), `decoded.json`, `previous/`.

## Corpus

90 catalog scenarios, 128 generated vectors. Complex: `vectors/complex/`. SeedCash BIP-174 drop: `vectors/seed_signer/`.

## Oracles

- Paytaca REAL: `python tools/oracles/compare_paytaca_real.py` — 18/18 byte-identical.
- Independent wire: `audits/independent/paytaca_v145_wire.py`
- libauth: `encodeTokenPrefix` live (no PSBT codec)
- BCHN: not installed

## Paytaca quirks cloned

- Version 145 uint32 LE
- Extra `0x00` after input maps
- JS `Object.keys(sortObjectKeys)` type order (`10` before `00`, `36` before `03`)
- Output `0x36` = prefix with `0xef`; `0x04` locking only

## Known limitations (not bugs)

- BCHN oracle absent
- No public-chain CashTokens corpus
- Live SeedCash `PSBTParser` optional
- libauth has no PSBT implementation
- P2SH **outputs** include `PSBT_OUT_REDEEM_SCRIPT`; P2SH **inputs** are not in the catalog (unsigned genesis_parent is P2PKH)
- Commitment cap 40 (CHIP v2.2.2)
- Catalog `expected_*` is self-consistency; Paytaca JS is the external byte oracle

## Repro

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m ctlab generate
python tools\oracles\compare_paytaca_real.py
python verify-v145.py
python -c "from ctlab.engine import generate; print(generate('MONSTER-01', dialect='paytaca-145')['psbt_base64'][:80])"
```
