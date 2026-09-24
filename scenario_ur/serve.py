"""Local page: list the document's PSBT tests and show a UR.

    python scenario_ur/serve.py
    python scenario_ur/serve.py --port 8766 --doc /path/to/psbtV145CashTokenScenarios.json
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ctlab.engine import generate_from_config  # noqa: E402
from ctlab.lab.ur import wrap_psbt_cbor  # noqa: E402
from scenario_ur.compile import apply_overrides, compile_config, schema_for  # noqa: E402
from scenario_ur.ur_encode import encode_crypto_psbt  # noqa: E402

DEFAULT_DOC = Path("/Users/martialturorequena/Desktop/psbtV145CashTokenScenarios.json")
STATIC = Path(__file__).resolve().parent / "static"


def load_doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_index(doc: dict) -> dict[str, str]:
    found: dict[str, str] = {}
    for fix in doc.get("materializedFixtures") or []:
        hex_psbt = fix.get("psbtHex")
        if not hex_psbt:
            continue
        for sid in fix.get("sourceScenarioIds") or []:
            found.setdefault(str(sid), hex_psbt)
    for neg in doc.get("materializedNegativeVectors") or []:
        if neg.get("psbtHex"):
            found[str(neg.get("sourceNegativeScenarioId"))] = neg["psbtHex"]
    return found


def all_rows(doc: dict) -> list[dict]:
    rows = []
    for group, key in (("escenario", "scenarios"), ("negativo", "negativeScenarios")):
        for item in doc.get(key) or []:
            rows.append(
                {
                    "id": str(item.get("id")),
                    "slug": item.get("slug"),
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "domain": item.get("domain"),
                    "validity": item.get("validity"),
                    "group": group,
                    "operation": item.get("operation"),
                }
            )
    return rows


def _scenario(doc: dict, sid: str) -> dict | None:
    for item in list(doc.get("scenarios") or []) + list(doc.get("negativeScenarios") or []):
        if str(item.get("id")) == str(sid):
            return item
    return None


class App:
    def __init__(self, doc_path: Path):
        self.doc_path = doc_path
        self.doc = load_doc(doc_path)
        self.fixtures = fixture_index(self.doc)
        self.rows = all_rows(self.doc)

    def scenario_view(self, sid: str, overrides: dict | None, source: str | None) -> dict:
        scenario = _scenario(self.doc, sid)
        if scenario is None:
            raise KeyError(sid)
        schema = schema_for(scenario["slug"])
        if str(sid) in self.fixtures:
            schema = [
                {
                    "key": "source",
                    "label": "Origen del PSBT",
                    "type": "select",
                    "value": "documento",
                    "options": ["documento", "generador"],
                },
                *schema,
            ]
        schema, values = apply_overrides(schema, overrides)
        if source:
            values["source"] = source
            for item in schema:
                if item["key"] == "source":
                    item["value"] = source
        use_doc = values.get("source") == "documento" and str(sid) in self.fixtures
        note = ""
        vector = None
        if use_doc:
            psbt = bytes.fromhex(self.fixtures[str(sid)])
            note = "PSBT materializado en el documento, sin regenerar."
            consensus = scenario.get("validity")
            reason = None
            psbt_status = "documento"
        else:
            cfg, note = compile_config(scenario, values)
            vector = generate_from_config(cfg)
            raw = vector.get("psbt_hex") or ""
            if not raw:
                raise RuntimeError(vector.get("actual_psbt_error") or "el generador no produjo un PSBT")
            psbt = bytes.fromhex(raw)
            consensus = vector.get("actual_consensus")
            reason = vector.get("actual_consensus_reason")
            psbt_status = vector.get("actual_psbt")
            if vector.get("actual_psbt_error") and psbt_status != "valid":
                reason = reason or vector.get("actual_psbt_error")
        ur_break = values.get("ur_break") or "none"
        payload = psbt
        if ur_break == "cbor-wrap":
            payload = wrap_psbt_cbor(psbt)
            note = (note + " " if note else "") + "El UR lleva el PSBT dentro de un CBOR bstr; SeedCash espera el PSBT en crudo y no debería aceptarlo."
        encoded = encode_crypto_psbt(payload, int(values.get("fragment_len") or 400))
        parts = encoded["parts"]
        if ur_break == "truncate" and parts:
            parts = [parts[0][: max(24, len(parts[0]) // 3)]]
            encoded = {**encoded, "parts": parts, "single": True}
            note = (note + " " if note else "") + "UR cortado a propósito."
        return {
            "scenario": {
                "id": str(scenario.get("id")),
                "slug": scenario.get("slug"),
                "title": scenario.get("title"),
                "description": scenario.get("description"),
                "domain": scenario.get("domain"),
                "validity": scenario.get("validity"),
                "group": "negativo" if str(scenario.get("id")).startswith("N") else "escenario",
            },
            "params": schema,
            "note": note.strip(),
            "consensus": consensus,
            "consensus_reason": reason,
            "psbt_status": psbt_status,
            "psbt_bytes": len(psbt),
            "ur": parts[0] if parts else "",
            "parts": parts,
            "single": bool(encoded.get("single")),
            "txid": None if vector is None else vector.get("txid"),
        }


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
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
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/ur":
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode() or "{}")
                view = app.scenario_view(str(body.get("id")), body.get("params") or {}, body.get("source"))
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
