"""Deterministic transfer presets shared by desktop and regression tests."""
from typing import Any

def bch_io(ident: str, n_in: int, n_out: int, *, change: bool = False) -> dict[str, Any]:
    """Construct deterministic BCH payment/change configurations."""
    inputs = [
        {"kind": "bch", "key": chr(ord("A") + i), "owner": "alice", "sats": 50_000}
        for i in range(n_in)
    ]
    outputs: list[dict[str, Any]] = []
    owners = ["bob", "carol", "dave", "alice"]
    remaining = 50_000 * n_in - 2000
    for i in range(n_out):
        owner = "alice" if (change and i == n_out - 1) else owners[i % 3]
        sat = remaining // (n_out - i) if i < n_out - 1 else remaining
        remaining -= sat
        outputs.append({"owner": owner, "sats": max(sat, 546)})
    return {
        "id": ident,
        "dialect": "paytaca-145",
        "sign_state": "unsigned",
        "inputs": inputs,
        "outputs": outputs,
    }

