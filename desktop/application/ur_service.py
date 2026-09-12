"""UR encode/decode via Paytaca's npm libraries. No PSBT serialization here."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from typing import Any

LAB = Path(__file__).resolve().parents[2]
NODE = next((LAB / "tools" / "node").glob("node-v*-win-x64/node.exe"), None)
SCRIPT = LAB / "desktop" / "ur" / "paytaca_ur.mjs"

DENSITY = {
    "Low": 50,
    "Medium": 100,
    "High": 200,
    "Maximum": 400,
}

SPEED_MS = {
    "Slow": 400,
    "Normal": 180,
    "Fast": 100,
    "Very fast": 50,
}


def _node() -> Path:
    if NODE is None or not NODE.exists():
        raise RuntimeError("portable Node.js not found under tools/node")
    if not SCRIPT.exists():
        raise RuntimeError(f"missing {SCRIPT}")
    nm = SCRIPT.parent / "node_modules" / "@ngraveio" / "bc-ur"
    if not nm.is_dir():
        raise RuntimeError("npm install desktop/ur (Paytaca @ngraveio/bc-ur)")
    return NODE


def encode_ur(psbt_hex: str, density: str = "High") -> dict[str, Any]:
    max_frag = DENSITY.get(density, 200)
    psbt = bytes.fromhex(psbt_hex.strip())
    payload = json.dumps(
        {
            "op": "roundtrip",
            "psbt": base64.b64encode(psbt).decode("ascii"),
            "maxFragment": max_frag,
        }
    )
    p = subprocess.run(
        [str(_node()), str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(SCRIPT.parent),
        timeout=30,
    )
    if not p.stdout.strip():
        raise RuntimeError(p.stderr[-800:] or "UR encoder produced no output")
    data = json.loads(p.stdout)
    if not data.get("ok"):
        raise RuntimeError(data.get("error") or "UR encode failed")
    data["density"] = density
    data["maxFragment"] = max_frag
    data["paytaca_compat"] = "same-libraries"
    data["note"] = (
        "Encoded with @ngraveio/bc-ur + @keystonehq/bc-ur-registry "
        "(Paytaca package.json). UR *string* identity with the Paytaca app "
        "is unverified; PSBT roundtrip through these libraries is tested."
    )
    return data


def decode_ur_parts(parts: list[str]) -> str:
    payload = json.dumps({"op": "decode", "parts": parts})
    p = subprocess.run(
        [str(_node()), str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(SCRIPT.parent),
        timeout=30,
    )
    data = json.loads(p.stdout or "{}")
    if not data.get("ok"):
        raise RuntimeError(data.get("error") or "UR decode failed")
    return data["hex"]
