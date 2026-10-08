"""Machine-readable campaign reports. Axes A/B/C never collapsed."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def summarize(findings: list[dict[str, Any]]) -> dict[str, Any]:
    sev = Counter(f.get("severity") or "INFO" for f in findings)
    cls = Counter(f.get("classification") or "VALID" for f in findings)
    a = Counter((f.get("A") or {}).get("status") or (f.get("transaction_correctness") or {}).get("status") for f in findings)
    b = Counter((f.get("B") or {}).get("status") or (f.get("psbt_semantic_correctness") or {}).get("status") for f in findings)
    c = Counter((f.get("C") or {}).get("status") or (f.get("review_correctness") or {}).get("status") for f in findings)
    return {
        "n": len(findings),
        "severity": dict(sev),
        "classification": dict(cls),
        "A_transaction": dict(a),
        "B_psbt_maps": dict(b),
        "C_review": dict(c),
    }


def write_report(path: Path, findings: list[dict[str, Any]], extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = {"summary": summarize(findings), "findings": findings}
    if extra:
        blob["extra"] = extra
    path.write_text(json.dumps(blob, indent=2, default=str), encoding="utf-8")


def finding_card(f: dict[str, Any]) -> str:
    ident = f.get("id") or f.get("vector_id") or "?"
    cat = f.get("category") or f.get("classification")
    sev = f.get("severity")
    return (
        f"FINDING {ident}\n"
        f"Category: {cat}\n"
        f"Severity: {sev}\n"
        f"A transaction: {f.get('A') or f.get('transaction_correctness')}\n"
        f"B psbt maps:   {f.get('B') or f.get('psbt_semantic_correctness')}\n"
        f"C review:      {f.get('C') or f.get('review_correctness')}\n"
    )
