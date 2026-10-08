# Python test laboratory support

These utilities live under `tests/support/lab/` and are excluded from the
installed desktop application. They use `core.engine` for generation and
keep transaction, map, and external SeedCash review checks separate.

Run with:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/lab tests/regression
```

Golden fixtures are in `vectors/regression/seedcash-v145-m0/`. Receiver
checks use `core.receiver` and the project's Python UR helpers. No external
SeedCash checkout or path configuration is required.
