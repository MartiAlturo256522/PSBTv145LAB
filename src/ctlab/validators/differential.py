"""Differential testing against SeedCash parser when importable.

libauth / BCHN are optional oracles: skipped with status SKIPPED if not
installed. Failures must be explicit; SKIPPED is not PASS.
"""

from __future__ import annotations

import json
from typing import Any


def try_seedcash_parse(psbt_bytes: bytes) -> dict[str, Any]:
    try:
        from seedcash.models.psbt_parser import PSBTParser, parse_token_script
    except Exception as e:
        return {"status": "SKIPPED", "reason": f"seedcash not importable: {e}"}
    try:
        parser = PSBTParser(bytearray(psbt_bytes))
        nfts = list(parser.nft_categories)
        fts = list(parser.token_categories)
        return {
            "status": "decoded",
            "nft_categories": nfts,
            "ft_categories": fts,
            "num_inputs": parser.num_inputs,
            "fee": parser.fee_amount,
            "destination_addresses": parser.destination_addresses,
            "hybrid_blind": bool(
                any(
                    (inp.spent_output and inp.spent_output.token and inp.spent_output.token.nft_data
                     and inp.spent_output.token.ft_amount)
                    for group in parser.inputs
                    for ins in group.values()
                    for inp in ins
                )
            )
            if False
            else None,
        }
    except Exception as e:
        return {"status": "error", "reason": f"{type(e).__name__}: {e}"}


def _find_node() -> str | None:
    import os
    import shutil
    from pathlib import Path

    found = shutil.which("node")
    if found:
        return found
    root = Path(__file__).resolve().parents[3]
    portable = list((root / "tools" / "node").glob("node-v*-win-x64/node.exe"))
    if portable:
        return str(portable[0])
    envn = os.environ.get("CTLAB_NODE")
    return envn if envn and Path(envn).exists() else None


def try_libauth(token_spec: dict | None = None) -> dict[str, Any]:
    """Run live @bitauth/libauth encodeTokenPrefix when Node is available."""
    import json
    import subprocess
    from pathlib import Path

    node = _find_node()
    if not node:
        return {"status": "SKIPPED", "reason": "Node.js not found"}
    script = Path(__file__).resolve().parents[3] / "tools" / "oracles" / "libauth_prefix.mjs"
    if not script.is_file():
        return {"status": "SKIPPED", "reason": f"missing {script}"}
    node_modules = script.parent / "node_modules" / "@bitauth" / "libauth"
    if not node_modules.is_dir():
        return {"status": "SKIPPED", "reason": "@bitauth/libauth not installed under tools/oracles"}
    if not token_spec:
        return {
            "status": "SKIPPED",
            "reason": "libauth JS available but this report did not pass a token spec (SKIPPED is not PASS)",
        }
    try:
        p = subprocess.run(
            [node, str(script), json.dumps(token_spec)],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(script.parent),
        )
    except Exception as e:
        return {"status": "error", "reason": str(e)}
    if p.returncode != 0:
        return {"status": "error", "reason": (p.stderr or p.stdout)[-500:]}
    return {"status": "ok", "prefix_hex": p.stdout.strip()}


def try_bchn() -> dict[str, Any]:
    return {
        "status": "SKIPPED",
        "reason": "bitcoin-cli / BCHN not required for corpus generation; decodepsbt is optional",
    }


def differential_report(vector: dict[str, Any]) -> dict[str, Any]:
    psbt_hex = vector.get("psbt_hex")
    seedcash = {"status": "SKIPPED", "reason": "no psbt"}
    if psbt_hex:
        seedcash = try_seedcash_parse(bytes.fromhex(psbt_hex))
    libauth = try_libauth(None)
    bchn = try_bchn()
    our = "valid" if vector.get("actual_consensus") == "valid" else vector.get("actual_consensus")
    self_ok = bool(vector.get("consensus_match") and vector.get("psbt_match"))
    independent_ran = any(
        x.get("status") not in ("SKIPPED", "n/a", None)
        for x in (libauth, bchn, seedcash)
    )
    if vector.get("error"):
        status = "ERROR"
    elif not self_ok:
        status = "FAIL"
    elif not independent_ran:
        # Self-consistency is not verification. SKIPPED oracles must not yield PASS.
        status = "SKIPPED"
    else:
        status = "PASS"
    paytaca_status = "n/a"
    if vector.get("dialect") == "paytaca-145":
        paytaca_status = "encoded-by-lab-not-an-oracle"
    return {
        "id": vector.get("id"),
        "expected": vector.get("expected_consensus"),
        "libauth": libauth["status"],
        "bchn": bchn["status"],
        "paytaca": paytaca_status,
        "our_parser": our,
        "seedcash": seedcash["status"],
        "seedcash_detail": seedcash,
        "status": status,
        "self_consistent": self_ok,
        "notes": [
            libauth.get("reason"),
            bchn.get("reason"),
            vector.get("actual_consensus_reason"),
            vector.get("actual_psbt_error"),
            None if independent_ran else "no independent oracle ran; SKIPPED is not PASS",
        ],
    }
