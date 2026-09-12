from __future__ import annotations

import json
from pathlib import Path

from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_vector
from ctlab.validators.differential import differential_report

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="CashTokens PSBT Test Vector Laboratory", version="0.1.0")
_CATALOG = build_catalog()
_BY_ID = {s["id"]: s for s in _CATALOG}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/catalog")
def catalog():
    slim = [
        {
            "id": s["id"],
            "group": s["group"],
            "title": s["title"],
            "description": s["description"],
            "expected_consensus": s["expected_consensus"],
            "expected_psbt": s["expected_psbt"],
            "dialects": s.get("dialects"),
            "sign_states": s.get("sign_states"),
        }
        for s in _CATALOG
    ]
    return {"count": len(slim), "items": slim}


@app.get("/api/vector/{vid}")
def vector(vid: str, dialect: str | None = None, sign: str | None = None):
    sc = _BY_ID.get(vid)
    if not sc:
        raise HTTPException(404, f"unknown id {vid}")
    vec = generate_vector(sc, dialect=dialect, sign_state=sign)
    vec["differential"] = differential_report(vec)
    return JSONResponse(vec)


@app.post("/api/generate")
def generate_custom(config: dict[str, Any] = Body(...)):
    from ctlab.engine import generate_from_config

    try:
        vec = generate_from_config(config)
    except Exception as e:
        raise HTTPException(400, f"{type(e).__name__}: {e}") from e
    vec["differential"] = differential_report(vec)
    return JSONResponse(vec)


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
