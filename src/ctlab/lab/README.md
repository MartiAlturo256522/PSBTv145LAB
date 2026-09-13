# `ctlab.lab` — synthetic PSBT v145 laboratory

Sits on the frozen motor `ctlab.engine.generate`. Default dialect is **Paytaca PSBT v145** (BCH extension of PSBT v2). Not BIP-174. Not coin type `145'`.

```powershell
$env:PYTHONPATH = "src;C:\Users\reque\seedcash\src"
python -m ctlab lab generate --m1 --seed 20260913
python -m ctlab lab generate --count 10000 --adversarial --tokens --seed 20260913
python -m ctlab lab compare-paytaca
python -m ctlab lab compare-seedcash --count 20
python -m ctlab lab extra00
python -m ctlab lab fuzz --count 100 --seed 20260913
python -m pytest tests/lab tests/regression -q
```

Oracle axes (never collapsed): **A** signed/unsigned tx, **B** PSBT maps, **C** SeedCash review.

Full report: `audits/lab/LAB_REPORT.md`. Golden M0: `vectors/regression/seedcash-v145-m0/`.
