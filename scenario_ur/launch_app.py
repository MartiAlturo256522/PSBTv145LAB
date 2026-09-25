#!/usr/bin/env python3
"""Open the scenario-list UR viewer in its own window.

This is the second app: one concrete test list, its UR/QR, and the
input/output diagram. It does not open the free-form PSBT builder.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def prepare_path() -> None:
    root = bundle_root()
    extras = [root, root / "src", root / "vendor" / "seedcash" / "src"]
    for item in extras:
        text = str(item)
        if item.is_dir() and text not in sys.path:
            sys.path.insert(0, text)


def document_path() -> Path:
    bundled = bundle_root() / "scenario_ur" / "psbtV145CashTokenScenarios.json"
    if bundled.is_file():
        return bundled
    return Path("/Users/martialturorequena/Desktop/psbtV145CashTokenScenarios.json")


def start_server():
    prepare_path()
    from scenario_ur.serve import App, make_handler

    app = App(document_path())
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, app


def _report(line: str) -> None:
    print(line, flush=True)
    dest = os.environ.get("SEEDCASH_SELFTEST_OUT")
    if dest:
        Path(dest).write_text(line + "\n", encoding="utf-8")


def self_test() -> int:
    fd, reviews = tempfile.mkstemp(prefix="psbt-reviews-", suffix=".json")
    os.close(fd)
    os.environ["SEEDCASH_REVIEWS_PATH"] = reviews
    server, app = start_server()
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(base + "/api/scenarios", timeout=30) as response:
            catalog = json.load(response)
        if catalog.get("count", 0) < 1 or not catalog.get("items"):
            _report("SELFTEST_FAIL empty scenario list")
            return 1
        page = urllib.request.urlopen(base + "/", timeout=30).read().decode("utf-8", "replace")
        if "Entradas y salidas" not in page or "qrcodegen.js" not in page:
            _report("SELFTEST_FAIL page is not the test viewer")
            return 1
        if "Satisfechos primero" not in page or "No válido consenso" not in page:
            _report("SELFTEST_FAIL page has no review controls")
            return 1
        sid = str(catalog["items"][0]["id"])
        request = urllib.request.Request(
            base + "/api/ur",
            data=json.dumps({"id": sid, "density": "Alta"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            view = json.load(response)
        parts = view.get("parts") or []
        flow = view.get("flow") or {}
        if not parts or not str(parts[0]).startswith("ur:crypto-psbt"):
            _report("SELFTEST_FAIL missing UR")
            return 1
        if not flow.get("inputs") or not view.get("psbt_hex"):
            _report("SELFTEST_FAIL missing diagram or psbt")
            return 1
        mark = urllib.request.Request(
            base + "/api/reviews",
            data=json.dumps({"id": sid, "status": "satisfecho"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(mark, timeout=30) as response:
            saved = json.load(response)
        if (saved.get("marks") or {}).get(sid) != "satisfecho":
            _report("SELFTEST_FAIL review was not saved")
            return 1
        clear = urllib.request.Request(
            base + "/api/reviews",
            data=json.dumps({"id": sid, "status": ""}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(clear, timeout=30) as response:
            cleared = json.load(response)
        if sid in (cleared.get("marks") or {}):
            _report("SELFTEST_FAIL review was not cleared")
            return 1
        _report(
            "SELFTEST_OK "
            f"tests {catalog['count']} scenario {sid} "
            f"inputs {len(flow['inputs'])} outputs {len(flow.get('outputs') or [])} "
            f"fragments {len(parts)}"
        )
        return 0
    finally:
        server.shutdown()


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    server, app = start_server()
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"

    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView

    qt = QApplication(sys.argv)
    qt.setApplicationName("Tests PSBT UR")
    view = QWebEngineView()
    view.setWindowTitle(f"Tests PSBT → UR  ·  {len(app.rows)} tests")
    view.resize(1440, 920)
    view.load(QUrl(url))
    view.show()
    code = qt.exec()
    server.shutdown()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
