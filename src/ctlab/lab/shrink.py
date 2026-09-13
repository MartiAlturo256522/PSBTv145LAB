"""Greedy shrink of a failing TransactionIntent.

Reduce inputs, reduce outputs, drop OP_RETURN, drop extra token outputs
until ``maps_vs_unsigned`` or an optional oracle still fails. Returns
``intent.to_json()`` of the minimal surviving intent.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from ctlab.engine import generate
from ctlab.lab.intent import TransactionIntent
from ctlab.lab.maps import maps_vs_unsigned

Oracle = Callable[..., Any]
Predicate = Callable[[TransactionIntent, dict[str, Any]], bool]


def _generate(intent: TransactionIntent) -> dict[str, Any] | None:
    try:
        return generate(intent.to_engine_config(), dialect="paytaca-145", sign="unsigned")
    except Exception:
        return None


def _oracle_fails(oracle: Oracle, intent: TransactionIntent, vec: dict[str, Any]) -> bool:
    try:
        try:
            result = oracle(intent, vec)
        except TypeError:
            result = oracle(vec)
    except Exception:
        return False
    if result is False:
        return True
    if result is True:
        return False
    if isinstance(result, str):
        return result.upper() in {"FAIL", "FAILED", "ERROR", "HIGH", "CRITICAL"}
    if isinstance(result, dict):
        if result.get("ok") is False:
            return True
        if result.get("ok") is True:
            return False
        status = str(result.get("status") or result.get("result") or "").upper()
        if status in {"FAIL", "FAILED", "ERROR"}:
            return True
        sev = str(result.get("severity") or "").upper()
        if sev in {"HIGH", "CRITICAL", "ERROR"}:
            return True
    return False


def still_fails(
    intent: TransactionIntent,
    vec: dict[str, Any] | None,
    oracle: Oracle | None = None,
    predicate: Predicate | None = None,
) -> bool:
    if vec is None:
        return False
    if predicate is not None:
        try:
            return bool(predicate(intent, vec))
        except Exception:
            return False
    hex_ = vec.get("psbt_hex") or ""
    if not hex_:
        return False
    try:
        cons = maps_vs_unsigned(bytes.fromhex(hex_))
    except Exception:
        return True
    maps_fail = not cons.get("ok")
    if oracle is not None:
        return maps_fail or _oracle_fails(oracle, intent, vec)
    return maps_fail


def _is_op_return(out: Any) -> bool:
    return out.role == "op_return" or out.script == "op_return"


def _is_token_out(out: Any) -> bool:
    tok = out.token
    if tok is None:
        return False
    return bool(tok.is_ft() or tok.is_nft() or tok.genesis)


def _reductions(intent: TransactionIntent) -> list[TransactionIntent]:
    """Simple greedy candidates: fewer ins, fewer outs, drop OP_RETURN, drop extra tokens."""
    cands: list[TransactionIntent] = []
    if intent.n_in > 1:
        cands.append(
            intent.clone(
                inputs=list(intent.inputs[:-1]),
                mutations=list(intent.mutations) + ["shrink_drop_input"],
            )
        )
    if intent.n_out > 1:
        cands.append(
            intent.clone(
                outputs=list(intent.outputs[:-1]),
                mutations=list(intent.mutations) + ["shrink_drop_output"],
            )
        )
    kept = [o for o in intent.outputs if not _is_op_return(o)]
    if kept and len(kept) < intent.n_out:
        cands.append(
            intent.clone(
                outputs=kept,
                mutations=list(intent.mutations) + ["shrink_drop_op_return"],
            )
        )
    if sum(1 for o in intent.outputs if _is_token_out(o)) > 1:
        seen = False
        new_outs = []
        for o in intent.outputs:
            if _is_token_out(o):
                if seen:
                    new_outs.append(replace(o, token=None, genesis_from=None))
                else:
                    new_outs.append(o)
                    seen = True
            else:
                new_outs.append(o)
        cands.append(
            intent.clone(
                outputs=new_outs,
                mutations=list(intent.mutations) + ["shrink_drop_extra_tokens"],
            )
        )
    return cands


def shrink(
    intent: TransactionIntent,
    oracle: Oracle | None = None,
    save_path: str | Path | None = None,
    predicate: Predicate | None = None,
) -> dict[str, Any]:
    """Shrink a failing intent; save ``to_json()`` if ``save_path`` is set."""
    current = intent
    vec = _generate(current)
    if not still_fails(current, vec, oracle=oracle, predicate=predicate):
        result = current.to_json()
        if save_path:
            Path(save_path).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return result

    improved = True
    while improved:
        improved = False
        for cand in _reductions(current):
            if cand.n_in < 1 or cand.n_out < 1:
                continue
            v = _generate(cand)
            if still_fails(cand, v, oracle=oracle, predicate=predicate):
                current = cand
                improved = True
                break

    result = current.to_json()
    if save_path:
        Path(save_path).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result
