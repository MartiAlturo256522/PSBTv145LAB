# SeedCash PSBT Lab

Desktop laboratory UI over the **frozen** CashTokens PSBT v145 engine.
The UI does not serialize PSBTs. It only configures cases and displays engine output.

## Launch

From the lab root:

```powershell
cd C:\Users\reque\seedcash\cashtokens-psbt-lab
$env:PYTHONPATH = "src"
pip install -r desktop/requirements.txt
python desktop/run.py
```

Or: `python -m desktop` with `PYTHONPATH=src`.

## Workflow

Configure inputs/outputs/tokens → **GENERATE PSBT** (`Ctrl+Enter`) → copy Base64 for SeedCash.

Presets and Fixtures call `ctlab.engine.generate` by catalog id.
JSON tab sends the exact engine config.

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
