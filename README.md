# CashTokens PSBT v145 generator (Paytaca + BCH)

This tool is completely experimental.

Deterministic generator of Bitcoin Cash CashTokens PSBTs in the **Paytaca v145** dialect. No mainnet. No real funds.

**Status: `VERIFIED WITH WARNINGS`** — live Paytaca `Psbt` JS is byte-identical on **18/18** vectors including MONSTER-01 and vout=0-not-genesis. Catalog 90 / 128 vectors. BCHN not installed. See [`FINAL_VERIFICATION_REPORT.md`](FINAL_VERIFICATION_REPORT.md).

## Motor

`ctlab.engine.generate_from_config(config)` is the only generation entry used by CLI, tests, and UI.

Paytaca v145 wire quirks cloned from `psbt.js` @ `9c338d2`:

- `PSBT_GLOBAL_VERSION` = 145 (uint32 LE)
- extra `0x00` after input maps
- `0x36` = token prefix including `0xef`; `0x04` = locking bytecode only
- map key order = JavaScript `Object.keys(sortObjectKeys(...))` (integer type keys such as `10` / `36` before `"00"`)

## Quick start

```powershell
cd C:\Users\reque\Desktop\PSBTLAB
$env:PYTHONPATH = "src"
python -m pytest -q
python -m ctlab generate --id MONSTER-01 --dialect paytaca-145 --sign unsigned
python -c "from ctlab.engine import generate; v=generate('MONSTER-01', dialect='paytaca-145'); print(v['psbt_base64'][:60])"
python tools\oracles\compare_paytaca_real.py
python verify-v145.py
python -m ctlab serve --port 8765
pip install -r desktop/requirements.txt
python desktop/run.py
```

Custom JSON:

```powershell
python -m ctlab generate --config path\to\config.json
```

```json
{
  "id": "CUSTOM-FT",
  "dialect": "paytaca-145",
  "sign_state": "unsigned",
  "inputs": [{"kind": "genesis_parent", "key": "A", "owner": "alice", "sats": 100000}],
  "outputs": [{"owner": "bob", "sats": 98000, "genesis_from": 0, "token": {"nft": null, "amount": 9}}]
}
```

Desktop UI: `python desktop/run.py`  
Web catalog: http://127.0.0.1:8765

## Layout

```
src/ctlab/engine.py          data-driven motor
src/ctlab/psbt/codec.py      Paytaca v145 + BIP-174/370/BCHN dialects
desktop/                     SeedCash PSBT Lab (PySide6)
app/                         local web UI (FastAPI)
tools/oracles/               live Paytaca JS + libauth
audits/paytaca/vendor/       real psbt.js @ 9c338d2
tests/repro/                 00→10 proof
```

Seed: `abandon` × 11 + `about`, path `m/44'/145'/0'/{change}/{index}`.
