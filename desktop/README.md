# SeedCash PSBT Lab

Desktop laboratory UI over the **frozen** CashTokens PSBT v145 engine.
The UI does not serialize PSBTs. It only configures cases and displays engine output.

**Format is a lab invariant, not a preset.** Every generated fixture is
`BCH PSBT v145` (engine wire name `paytaca-145`, Paytaca `psbt.js` @ `9c338d2`).
A scenario (Genesis FT, Simple transfer, Monster, …) picks **what transaction**
is built. It does not pick a PSBT dialect.

```
BCH PSBT v145
    → transaction scenario / preset
    → synthetic transaction
    → PSBT v145
    → optional UR crypto-psbt
    → SeedCash / Paytaca / differential validation
```

Default session: **FORMAT** BCH PSBT v145 · **REFERENCE** Paytaca 9c338d2 ·
**MODE** Synthetic / generate · **SCENARIO** Simple transfer.

Another encoding (BIP-174 v0) appears only in **compare** mode, as an
interoperability check against the same semantic transaction.

## Launch

From the lab root:

```powershell
cd C:\Users\reque\Desktop\PSBTLAB
$env:PYTHONPATH = "src"
pip install -r desktop/requirements.txt
python desktop/run.py
```

Or: `python -m desktop` with `PYTHONPATH=src`.

## Workflow

Pick a **scenario** → **GENERATE** (`Ctrl+Enter`) → copy Base64 / UR for SeedCash.

The identity strip on every fixture states: format = BCH v145, unsigned tx
present, CashTokens yes/no, in/out counts, scripts, token operations, Paytaca
compatibility, SeedCash compatibility, semantic validation.

JSON tab sends the exact engine config; `dialect` is forced to `paytaca-145`.

Synthetic UTXOs are laboratory fixtures, not chain UTXOs.

Examples (engine output, not UI-serialized): `desktop/examples/genesis-ft.psbt.base64`, `genesis-nft.psbt.base64`, `monster.psbt.base64`.

## UR / QR

Encoded with the **same npm packages Paytaca lists** (`@ngraveio/bc-ur`, `@keystonehq/bc-ur-registry`). Type `crypto-psbt`. Multipart uses fountain `UREncoder`.

**UR implementation: library-verified (PSBT roundtrip). Paytaca app string identity: unverified.**

```powershell
python -m pytest -q desktop/tests
```

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q desktop/tests
```
