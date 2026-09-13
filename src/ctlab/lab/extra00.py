"""Paytaca InputMap extra 0x00 regression family.

Paytaca PSBT v145 writes one extra 0x00 after input maps (psbt.js L1261)
and skips it on deserialize (L1273). A BIP-174 walker treats that byte as
an empty first output map and drops the last real map when n_out > 1.

This is a Paytaca BCH extension of PSBT v2, not BIP-174.
"""

from __future__ import annotations

from typing import Any

from ctlab.engine import generate
from ctlab.lab.intent import InputIntent, OutputIntent, TokenIntent, TransactionIntent
from ctlab.lab.maps import maps_vs_unsigned, walk_naive_no_skip, walk_paytaca_v145

FIRST_KINDS = ("token", "op_return", "p2sh", "p2pkh")
LAST_KINDS = ("token", "op_return")


def _make_output(kind: str, *, owner: str, sats: int) -> OutputIntent:
    k = kind.lower().replace("-", "_")
    if k in ("token", "cashtoken", "ft"):
        return OutputIntent(
            owner=owner,
            sats=max(sats, 546),
            role="token_transfer",
            script="p2pkh",
            token=TokenIntent(amount=9, genesis=True),
            genesis_from=0,
        )
    if k in ("op_return", "opreturn"):
        return OutputIntent(owner=owner, sats=0, role="op_return", script="op_return")
    if k in ("p2sh", "p2sh20"):
        return OutputIntent(owner=owner, sats=max(sats, 546), role="payment", script="p2sh20")
    if k == "p2sh32":
        return OutputIntent(owner=owner, sats=max(sats, 546), role="payment", script="p2sh32")
    return OutputIntent(owner=owner, sats=max(sats, 546), role="payment", script="p2pkh")


def _outputs(n_out: int, first: str, last: str) -> list[OutputIntent]:
    if n_out <= 1:
        return [_make_output(first, owner="bob", sats=1000)]
    outs = [_make_output(first, owner="bob", sats=1000)]
    for i in range(n_out - 2):
        outs.append(_make_output("p2pkh", owner="carol", sats=1000 + i))
    outs.append(_make_output(last, owner="alice", sats=2000))
    return outs


def extra00_cases(seed: int) -> list[tuple[int, str, str]]:
    cases: list[tuple[int, str, str]] = []
    for n_out in (1, 2, 3):
        if n_out == 1:
            for first in FIRST_KINDS:
                cases.append((1, first, first))
        else:
            for first in FIRST_KINDS:
                for last in LAST_KINDS:
                    cases.append((n_out, first, last))
    return cases


def extra00_family(seed: int) -> list[dict[str, Any]]:
    """Generate 1/2/3-output extra-00 cases; record Paytaca vs naive shift."""
    family: list[dict[str, Any]] = []
    for i, (n_out, first, last) in enumerate(extra00_cases(seed)):
        ident = f"E00-n{n_out}-first-{first}-last-{last}"
        intent = TransactionIntent(
            id=ident,
            seed=int(seed) + i,
            mode="NORMAL",
            description=f"extra00 n_out={n_out} first={first} last={last}",
            inputs=[InputIntent(kind="genesis_parent", key="A", owner="alice", sats=100_000)],
            outputs=_outputs(n_out, first, last),
        )
        rec: dict[str, Any] = {
            "id": ident,
            "seed": intent.seed,
            "n_in": intent.n_in,
            "n_out": n_out,
            "first": first,
            "last": last,
            "first_kind": first,
            "last_kind": last,
        }
        try:
            vec = generate(intent.to_engine_config(), dialect="paytaca-145", sign="unsigned")
            hex_ = vec.get("psbt_hex") or ""
            rec["psbt_hex"] = hex_
            raw = bytes.fromhex(hex_) if hex_ else b""
            pay = walk_paytaca_v145(raw)
            naive = walk_naive_no_skip(raw)
            cons = maps_vs_unsigned(raw)
            rec.update(
                {
                    "extra_input_sep": pay.get("extra_input_sep"),
                    "paytaca_output_types": pay.get("output_types"),
                    "naive_output_types": naive.get("output_types"),
                    "naive_first_map_empty": naive.get("first_map_empty"),
                    "naive_shift": cons.get("naive_shift"),
                    "naive_last_map_dropped": cons.get("naive_last_map_dropped"),
                    "shift": cons.get("naive_shift"),
                    "last_map_dropped": cons.get("naive_last_map_dropped"),
                    "paytaca": {
                        "n_in": pay.get("n_in"),
                        "n_out": pay.get("n_out"),
                        "extra_input_sep": pay.get("extra_input_sep"),
                        "output_types": pay.get("output_types"),
                        "leftover": pay.get("leftover"),
                    },
                    "naive": {
                        "n_in": naive.get("n_in"),
                        "n_out": naive.get("n_out"),
                        "first_map_empty": naive.get("first_map_empty"),
                        "output_types": naive.get("output_types"),
                        "output_map_lens": naive.get("output_map_lens"),
                        "leftover": naive.get("leftover"),
                    },
                    "maps_vs_unsigned": cons,
                }
            )
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["psbt_hex"] = rec.get("psbt_hex")
            rec["naive_first_map_empty"] = False
            rec["naive_shift"] = False
            rec["naive_last_map_dropped"] = False
            rec["paytaca_output_types"] = []
        family.append(rec)
    return family
