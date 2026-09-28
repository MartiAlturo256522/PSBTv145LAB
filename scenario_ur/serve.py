"""Local page: list the document's PSBT tests and show a UR.

    python scenario_ur/serve.py
    python scenario_ur/serve.py --port 8766 --doc /path/to/psbtV145CashTokenScenarios.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ctlab.engine import generate_from_config  # noqa: E402
from scenario_ur.compile import apply_overrides, compile_config, schema_for  # noqa: E402
from scenario_ur.flow import describe_psbt  # noqa: E402
from scenario_ur.ur_encode import encode_crypto_psbt  # noqa: E402

# Fragment length in bytes. Lower density means smaller pieces and more UR parts.
DENSITY = {
    "Baja": 50,
    "Media": 100,
    "Alta": 200,
    "Máxima": 400,
}

def default_doc() -> Path:
    beside = Path(__file__).resolve().parent / "psbtV145CashTokenScenarios.json"
    if beside.is_file():
        return beside
    return Path("/Users/martialturorequena/Desktop/psbtV145CashTokenScenarios.json")


DEFAULT_DOC = default_doc()

# Manual review of a test on the device. Separate from the document's validity.
REVIEW_STATUSES = {"satisfecho", "errores", "consenso"}
_REVIEWS_LOCK = threading.Lock()


def reviews_path() -> Path:
    override = os.environ.get("SEEDCASH_REVIEWS_PATH")
    if override:
        path = Path(override)
    else:
        path = Path.home() / "Library" / "Application Support" / "Tests PSBT UR" / "reviews.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_reviews() -> dict[str, str]:
    path = reviews_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    marks = data.get("marks") if isinstance(data, dict) else None
    if not isinstance(marks, dict):
        return {}
    return {str(key): value for key, value in marks.items() if value in REVIEW_STATUSES}


def save_review(sid: str, status: str) -> dict[str, str]:
    with _REVIEWS_LOCK:
        marks = load_reviews()
        if status in REVIEW_STATUSES:
            marks[str(sid)] = status
        else:
            marks.pop(str(sid), None)
        reviews_path().write_text(
            json.dumps({"marks": marks}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return marks


def static_dir() -> Path:
    """HTML and QR script. Inside a frozen app they live next to the bundle."""
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS")) / "scenario_ur" / "static"
        if (bundled / "index.html").is_file():
            return bundled
    return Path(__file__).resolve().parent / "static"


def load_doc(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    # OPTN PR 101 vectors live beside the catalog so the 69-row document stays intact.
    if not doc.get("corpusVectors"):
        sibling = path.parent / "optnCorpusVectors.json"
        if sibling.is_file():
            extra = json.loads(sibling.read_text(encoding="utf-8"))
            doc["corpusVectors"] = extra.get("vectors") or []
            if extra.get("source"):
                doc["corpusSource"] = extra["source"]
    return doc


def fixture_index(doc: dict) -> dict[str, str]:
    found: dict[str, str] = {}
    for fix in doc.get("materializedFixtures") or []:
        hex_psbt = fix.get("psbtHex")
        if not hex_psbt:
            continue
        ids = [str(sid) for sid in (fix.get("sourceScenarioIds") or [])]
        # A fixture tagged with several scenarios is one combined transaction,
        # not each of those tests. Only a single id is that test's PSBT.
        if len(ids) == 1:
            found.setdefault(ids[0], hex_psbt)
    for neg in doc.get("materializedNegativeVectors") or []:
        if neg.get("psbtHex"):
            found[str(neg.get("sourceNegativeScenarioId"))] = neg["psbtHex"]
    for item in doc.get("corpusVectors") or []:
        if item.get("psbtHex"):
            found.setdefault(str(item.get("id")), item["psbtHex"])
    return found


def all_rows(doc: dict) -> list[dict]:
    """Numbered catalog first, then OPTN corpus vectors that were not already stored."""
    rows = []
    for item in doc.get("scenarios") or []:
        rows.append(
            {
                "id": str(item.get("id")),
                "label": "",
                "slug": item.get("slug"),
                "title": item.get("title"),
                "description": item.get("description"),
                "domain": item.get("domain"),
                "validity": item.get("validity"),
                "group": "escenario",
                "operation": item.get("operation"),
                "note": "",
            }
        )
    for item in doc.get("corpusVectors") or []:
        rows.append(
            {
                "id": str(item.get("id")),
                "label": item.get("label") or "",
                "slug": item.get("id"),
                "title": item.get("title"),
                "description": item.get("description"),
                "domain": "optn-corpus",
                "validity": item.get("validity"),
                "group": "vector",
                "operation": "corpus",
                "note": item.get("note") or "",
            }
        )
    return rows


def _scenario(doc: dict, sid: str) -> dict | None:
    pools = (
        list(doc.get("scenarios") or [])
        + list(doc.get("negativeScenarios") or [])
        + list(doc.get("corpusVectors") or [])
    )
    for item in pools:
        if str(item.get("id")) == str(sid):
            return item
    return None


def _group(scenario: dict) -> str:
    group = scenario.get("group")
    if group in {"vector", "negativo", "escenario"}:
        return group
    if str(scenario.get("id")).startswith("N"):
        return "negativo"
    return "escenario"


class App:
    def __init__(self, doc_path: Path):
        self.doc_path = doc_path
        self.doc = load_doc(doc_path)
        self.fixtures = fixture_index(self.doc)
        self.rows = all_rows(self.doc)

    def scenario_view(self, sid: str, density: str = "Alta") -> dict:
        scenario = _scenario(self.doc, sid)
        if scenario is None:
            raise KeyError(sid)
        fragment = DENSITY.get(density, DENSITY["Alta"])
        if str(sid) in self.fixtures:
            psbt = bytes.fromhex(self.fixtures[str(sid)])
        else:
            _schema, values = apply_overrides(schema_for(scenario["slug"]), None)
            cfg, _note = compile_config(scenario, values)
            vector = generate_from_config(cfg)
            raw = vector.get("psbt_hex") or ""
            if not raw:
                raise RuntimeError(vector.get("actual_psbt_error") or "el generador no produjo un PSBT")
            psbt = bytes.fromhex(raw)
        encoded = encode_crypto_psbt(psbt, fragment)
        parts = list(encoded["parts"])
        if scenario.get("slug") == "invalid-ur-transport-payload" and parts:
            parts = [parts[0][: max(24, len(parts[0]) // 3)]]
        return {
            "scenario": {
                "id": str(scenario.get("id")),
                "label": scenario.get("label") or "",
                "title": scenario.get("title"),
                "validity": scenario.get("validity"),
                "group": _group(scenario),
            },
            "density": density if density in DENSITY else "Alta",
            "densities": list(DENSITY),
            "psbt_hex": psbt.hex(),
            "parts": parts,
            "single": len(parts) == 1,
            "flow": describe_psbt(psbt),
        }


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send(200, (static_dir() / "index.html").read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/qrcodegen.js":
                self._send(200, (static_dir() / "qrcodegen.js").read_bytes(), "text/javascript; charset=utf-8")
                return
            if path == "/api/scenarios":
                payload = {
                    "document": str(app.doc_path),
                    "count": len(app.rows),
                    "items": [
                        {**row, "fixture": row["id"] in app.fixtures}
                        for row in app.rows
                    ],
                }
                self._send(200, json.dumps(payload).encode(), "application/json")
                return
            if path == "/api/reviews":
                self._send(200, json.dumps({"marks": load_reviews()}).encode(), "application/json")
                return
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            if path == "/api/reviews":
                try:
                    body = json.loads(raw.decode() or "{}")
                    sid = str(body.get("id") or "")
                    status = str(body.get("status") or "")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._send(400, json.dumps({"error": "json inválido"}).encode(), "application/json")
                    return
                known = {row["id"] for row in app.rows}
                if sid not in known:
                    self._send(404, json.dumps({"error": "escenario desconocido"}).encode(), "application/json")
                    return
                if status not in REVIEW_STATUSES and status != "":
                    self._send(400, json.dumps({"error": "estado desconocido"}).encode(), "application/json")
                    return
                marks = save_review(sid, status)
                self._send(200, json.dumps({"marks": marks}).encode(), "application/json")
                return
            if path != "/api/ur":
                self._send(404, b"not found", "text/plain")
                return
            try:
                body = json.loads(raw.decode() or "{}")
                view = app.scenario_view(str(body.get("id")), str(body.get("density") or "Alta"))
            except KeyError:
                self._send(404, json.dumps({"error": "escenario desconocido"}).encode(), "application/json")
                return
            except Exception as exc:
                self._send(
                    400,
                    json.dumps({"error": f"{type(exc).__name__}: {exc}"}).encode(),
                    "application/json",
                )
                return
            self._send(200, json.dumps(view).encode(), "application/json")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Visor de tests PSBT → UR")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    app = App(args.doc)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    print(f"PSBT UR viewer  http://{args.host}:{args.port}  ({len(app.rows)} tests)")
    server.serve_forever()


if __name__ == "__main__":
    main()
