#!/usr/bin/env python3
"""Launch SeedCash PSBT Lab.

    python desktop/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from desktop.ui.main_window import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run())
