#!/usr/bin/env python3
"""Put Qt WebEngine where the frozen macOS app looks for it.

PyInstaller leaves QtWebEngineProcess and the .pak files under
Versions/Resources, while Qt follows Versions/Current (A). Without
these links the app aborts when it opens the window.
"""

from __future__ import annotations

import sys
from pathlib import Path


def fix_webengine(app: Path) -> None:
    framework = app / "Contents/Frameworks/PySide6/Qt/lib/QtWebEngineCore.framework"
    version_a = framework / "Versions/A"
    misplaced = framework / "Versions/Resources"
    helpers = version_a / "Helpers"
    if not helpers.exists():
        helpers.symlink_to(Path("../Resources/Helpers"))
    source = misplaced / "Resources"
    dest = version_a / "Resources"
    if source.is_dir() and dest.is_dir():
        for item in source.iterdir():
            link = dest / item.name
            if not link.exists():
                link.symlink_to(Path("../../Resources/Resources") / item.name)
    process = framework / "Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
    resources = framework / "Resources/icudtl.dat"
    if not process.is_file() or not resources.is_file():
        raise SystemExit(f"WebEngine still missing in {app}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix_macos_bundle.py 'Tests PSBT UR.app'")
    fix_webengine(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
