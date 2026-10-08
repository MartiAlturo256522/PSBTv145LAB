"""Python-only scenario fixture support; no server or browser UI."""
import json
from pathlib import Path
from core.engine import generate_from_config
from scenario_compile import apply_overrides, compile_config, schema_for
from scenario_flow import describe_psbt
from helpers.ur_service import encode_ur

DENSITY = {"Baja": "Low", "Media": "Medium", "Alta": "High", "Máxima": "Maximum"}

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


class ScenarioFixtures:
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
        encoded = encode_ur(psbt.hex(), fragment)
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
