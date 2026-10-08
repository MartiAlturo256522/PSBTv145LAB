# PSBTv145-LAB

A Python desktop application for building, inspecting, comparing, and exporting
synthetic Bitcoin Cash PSBT v145 fixtures with CashTokens. The UI uses PySide6;
UR creation and decoding run in Python without Node, npm, or a web server.

Install and launch from the project directory:

```bash
python -m pip install -e '.[dev]'
python src/main.py
```

An installed application can also be opened with `psbtv145-lab`.

```text
src/
  main.py                 Desktop entry point
  ui/                     Window, theme, identity strip, animated QR panel
  application/            Builder state, presets, PSBT service, fixture identity
  helpers/                Engine adapter and UR creation/decoding
    ur2/                  Vendored Python UR implementation and license
  core/                   PSBT, CashTokens, transaction and signing engine
    receiver/             Local receiver parser, transaction models, QR decoder
tests/
  vectors.json            Scenario definitions for desktop v145 testing
  vectors.py              Load, generate, and extract selected test vectors
  test_vectors.py         Manifest validation and extraction tests
  application/            Desktop service and UI tests
  fixtures/scenarios/     Preserved scenario and corpus JSON data
  scenarios/              Python scenario compiler and fixture validation
  support/lab/            Test-only lab and external integration utilities
  ...                     Existing protocol and regression tests
vectors/                  Existing generated fixtures and golden regression data
tools/                    Development and independent verification tools
```

`src/core/` remains the shared engine: UI and helpers use its codecs rather
than duplicating PSBT serialization. The engine supports other formats for
comparison; the desktop generation service selects Paytaca v145.

`tests/vectors.json` contains scenario inputs, including expected invalid cases.
`tests/vectors.py` generates unsigned v145 fixtures and extracts selected cases
with `extract_vectors(destination, ids=["GEN-04"])`. It is imported by tests,
with no command line interface. Existing frozen artifacts stay in `vectors/`
so byte-level regressions remain available.

Run checks:

```bash
python -m pytest -q
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

The second command supports machines without a graphical display. Validation
uses standalone Python CHIP token-prefix and Paytaca v145 wire references,
protocol checks, scenario tests, and frozen regression fixtures. The reference
modules are under `src/core/validators/` and do not use the production codecs.
They are specification translations, not live Paytaca verification.

The receiver parser, transaction models, and QR decoding live in
`src/core/receiver/`. They are adapted from SeedCash and use this project's
CashAddr and UR helpers. There is no external SeedCash dependency or source-path
configuration. Receiver and pipeline tests run locally, without camera libraries
or a device wallet installation. Local validation does not claim testing against
an independently running device.

`requirements.txt` installs this local package and its declared Python libraries;
`pyproject.toml` is the single source of dependency declarations. Original receiver
attribution and license are in `src/core/receiver/SOURCE.md` and `LICENSE`.
Historical receiver patch files under `patches/` document the previous device fix;
they are not dependencies of this application.

UR uses the Foundation Devices implementation with its BSD-2-Clause Plus Patent
license in `src/helpers/ur2/LICENSE`. Roundtrip tests check PSBT byte preservation;
matching Paytaca's exact UR strings is not asserted.

The desktop uses a landscape layout with scenarios on the left, the builder in
the center, and validation, artifacts, and animated QR on the right. The default
window size follows the available screen. Splitters resize the working panels;
long input/output lists scroll within their panels. All six BCH transfer presets
use `application.transfer_config`, which ships with the installed application.
