"""Three-axis security oracle: intent × generated vector × SeedCash × maps.

Axes are never collapsed into one boolean:
  A. transaction_correctness
  B. psbt_semantic_correctness
  C. review_correctness
"""

from __future__ import annotations

from typing import Any

from ctlab.engine import generate
from ctlab.fixtures.keys import ACTORS
from ctlab.lab.intent import OutputIntent, TokenIntent, TransactionIntent
from ctlab.lab.maps import maps_vs_unsigned
from ctlab.lab.seedcash_adapter import SIGNED_FOLLOWS_UNSIGNED_TX, capture
from ctlab.transactions.serialize import decode_transaction, p2sh20_script, p2sh32_script

SEVERITY_RANK = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

CLASSES = ("VALID", "MALFORMED", "AMBIGUOUS", "UNSUPPORTED", "SECURITY-SENSITIVE")


def _worse(a: str | None, b: str | None) -> str | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if SEVERITY_RANK.get(a, -1) >= SEVERITY_RANK.get(b, -1) else b


def _script_kind(script: bytes) -> str:
    if script.startswith(b"\x6a"):
        return "op_return"
    if script.startswith(b"\x76\xa9\x14") and script.endswith(b"\x88\xac") and len(script) == 25:
        return "p2pkh"
    if script.startswith(b"\xa9\x14") and script.endswith(b"\x87") and len(script) == 23:
        return "p2sh20"
    if script.startswith(b"\xaa\x20") and script.endswith(b"\x87") and len(script) == 34:
        return "p2sh32"
    return "bare" if script else "unknown"


def _expected_locking(out: OutputIntent) -> bytes | None:
    if out.malformed_script is not None:
        return out.malformed_script
    if out.script == "op_return":
        return None
    actor = ACTORS.get(out.owner)
    if actor is None:
        return None
    if out.script == "p2pkh":
        return actor.p2pkh()
    if out.script == "p2sh20":
        from ctlab.protocol.hashes import hash160

        return p2sh20_script(hash160(actor.p2pkh()))
    if out.script == "p2sh32":
        from ctlab.protocol.hashes import sha256

        return p2sh32_script(sha256(actor.p2pkh()))
    if out.script == "bare":
        return bytes([33]) + actor.pub + b"\xac"
    return actor.p2pkh()


def _norm_tok(td: dict[str, Any] | None) -> dict[str, Any] | None:
    if td is None:
        return None
    ft = td.get("ft")
    if ft is None:
        ft = td.get("amount", 0) or 0
    nft_cap = td.get("nft_cap")
    nft_commit = td.get("nft_commit")
    if td.get("nft"):
        nft_cap = td["nft"].get("capability")
        nft_commit = td["nft"].get("commitment") or ""
    return {
        "category": td.get("category"),
        "ft": int(ft or 0),
        "nft_cap": nft_cap,
        "nft_commit": nft_commit or None,
    }


def _intent_tok(tok: TokenIntent | None) -> dict[str, Any] | None:
    if tok is None:
        return None
    if not tok.is_ft() and not tok.is_nft() and not tok.genesis:
        return None
    return {
        "ft": int(tok.amount or 0),
        "nft_cap": tok.nft_capability,
        "nft_commit": tok.commitment.hex() if tok.commitment else None,
        "genesis": tok.genesis,
    }


def _tok_fields_match(intent_t: dict[str, Any] | None, actual: dict[str, Any] | None) -> bool:
    if intent_t is None:
        return actual is None or (not actual.get("ft") and not actual.get("nft_cap"))
    if actual is None:
        return not intent_t.get("ft") and not intent_t.get("nft_cap") and not intent_t.get("genesis")
    if int(intent_t.get("ft") or 0) != int(actual.get("ft") or 0):
        return False
    if intent_t.get("nft_cap") != actual.get("nft_cap"):
        return False
    want_c = intent_t.get("nft_commit") or None
    got_c = actual.get("nft_commit") or None
    if want_c != got_c:
        return False
    return True


def _lab_token(out: Any) -> dict[str, Any] | None:
    tok = out.token
    if tok is None:
        return None
    return {
        "category": tok.category,
        "ft": tok.amount,
        "nft_cap": tok.nft.capability if tok.nft else None,
        "nft_commit": tok.nft.commitment.hex() if tok.nft else None,
    }


def _axis_a(intent: TransactionIntent, vector: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any]:
    diffs: list[str] = []
    unsigned_hex = vector.get("unsigned_tx_hex") or ""
    tx = decode_transaction(bytes.fromhex(unsigned_hex)) if unsigned_hex else None
    model = (sc.get("model") or {}) if sc.get("ok") else {}

    vin_ok = tx is not None and len(tx.inputs) == intent.n_in
    vout_ok = tx is not None and len(tx.outputs) == intent.n_out
    if not vin_ok:
        diffs.append(f"vin intent={intent.n_in} unsigned={None if tx is None else len(tx.inputs)}")
    if not vout_ok:
        diffs.append(f"vout intent={intent.n_out} unsigned={None if tx is None else len(tx.outputs)}")

    sats_ok = True
    scripts_ok = True
    tokens_ok = True
    if tx is not None:
        src = vector.get("source_utxos") or []
        for i, inp in enumerate(intent.inputs):
            got = src[i]["value_sats"] if i < len(src) else None
            if got != inp.sats:
                sats_ok = False
                diffs.append(f"vin{i} sats intent={inp.sats} utxo={got}")
            if i < len(tx.inputs) and inp.kind == "genesis_parent" and tx.inputs[i].prev_index != 0:
                diffs.append(f"vin{i} genesis_parent prev_index={tx.inputs[i].prev_index}")
                tokens_ok = False
        for i, out in enumerate(intent.outputs):
            if i >= len(tx.outputs):
                sats_ok = False
                continue
            actual = tx.outputs[i]
            if actual.value_sats != out.sats:
                sats_ok = False
                diffs.append(f"vout{i} sats intent={out.sats} unsigned={actual.value_sats}")
            want_lock = _expected_locking(out)
            got_kind = _script_kind(actual.locking_bytecode)
            if out.script != "op_return" and want_lock is not None and actual.locking_bytecode != want_lock:
                scripts_ok = False
                diffs.append(f"vout{i} script intent={out.script} unsigned={got_kind}")
            elif out.script == "op_return" and got_kind != "op_return":
                scripts_ok = False
                diffs.append(f"vout{i} expected op_return got={got_kind}")
            elif out.script != "op_return" and got_kind != out.script and out.script not in ("unknown", "bare"):
                scripts_ok = False
                diffs.append(f"vout{i} script kind intent={out.script} unsigned={got_kind}")
            if not _tok_fields_match(_intent_tok(out.token), _lab_token(actual)):
                tokens_ok = False
                diffs.append(f"vout{i} token intent!=unsigned")

    model_match = True
    if sc.get("ok") and tx is not None:
        if model.get("vin") != len(tx.inputs) or model.get("vout") != len(tx.outputs):
            model_match = False
            diffs.append("seedcash model vin/vout != unsigned_tx")
        for i, out in enumerate(tx.outputs):
            m = (model.get("outputs") or [None] * (i + 1))[i] if i < len(model.get("outputs") or []) else None
            if m is None:
                model_match = False
                diffs.append(f"vout{i} missing from seedcash model")
                continue
            if m.get("sats") != out.value_sats:
                model_match = False
                diffs.append(f"vout{i} model sats={m.get('sats')} unsigned={out.value_sats}")
            if (m.get("script_pubkey") or "") != out.locking_bytecode.hex():
                model_match = False
                diffs.append(f"vout{i} model script != unsigned locking")
            mt = _norm_tok(m.get("token"))
            ut = _norm_tok(_lab_token(out))
            if mt is None and ut is None:
                pass
            elif mt is None or ut is None or mt.get("ft") != ut.get("ft") or mt.get("nft_cap") != ut.get("nft_cap") or (mt.get("nft_commit") or None) != (ut.get("nft_commit") or None) or mt.get("category") != ut.get("category"):
                model_match = False
                diffs.append(f"vout{i} model token != unsigned")
        for i, src in enumerate(vector.get("source_utxos") or []):
            m = (model.get("inputs") or [None] * (i + 1))[i] if i < len(model.get("inputs") or []) else None
            if m is None:
                continue
            if m.get("sats") != src.get("value_sats"):
                model_match = False
                diffs.append(f"vin{i} model sats={m.get('sats')} utxo={src.get('value_sats')}")
    elif not sc.get("ok"):
        model_match = False
        diffs.append(f"seedcash capture failed: {sc.get('error')}")

    ok = bool(vin_ok and vout_ok and sats_ok and scripts_ok and tokens_ok and model_match and tx is not None)
    return {
        "ok": ok,
        "vin_match": bool(vin_ok),
        "vout_match": bool(vout_ok),
        "sats_match": bool(sats_ok),
        "scripts_match": bool(scripts_ok),
        "tokens_match": bool(tokens_ok),
        "model_matches_unsigned": bool(model_match),
        "diffs": diffs,
        "severity": None if ok else "HIGH",
        "class": "VALID" if ok else ("MALFORMED" if tx is None else "AMBIGUOUS"),
    }


def _axis_b(maps_info: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any]:
    diffs = list(maps_info.get("diffs") or [])
    naive_shift = bool(maps_info.get("naive_shift"))
    last_dropped = bool(maps_info.get("naive_last_map_dropped"))
    paytaca_ok = bool(maps_info.get("ok"))
    sc_maps = (sc.get("maps") or {}) if sc.get("ok") else {}
    if sc_maps.get("first_output_map_empty") and not naive_shift:
        diffs.append("seedcash empty first out-map without maps.naive_shift")
    signed_unchanged = SIGNED_FOLLOWS_UNSIGNED_TX
    # Paytaca-aligned maps matching unsigned_tx is semantic correctness.
    # Naive extra-00 shift is interop: it does not change signed tx today.
    if paytaca_ok:
        axis_ok = True
        if naive_shift:
            cls = "UNSUPPORTED"
            tag = "INTEROP"
            sev = "LOW"
        else:
            cls = "VALID"
            tag = None
            sev = None
    else:
        axis_ok = False
        cls = "AMBIGUOUS"
        tag = None
        sev = "HIGH" if not signed_unchanged else "LOW"
        if not signed_unchanged:
            tag = None
        else:
            tag = "INTEROP"
    if last_dropped:
        diffs.append("naive_last_map_dropped")
    return {
        "ok": axis_ok,
        "paytaca_maps_match_unsigned": paytaca_ok,
        "naive_shift": naive_shift,
        "naive_last_map_dropped": last_dropped,
        "extra_input_sep": bool(maps_info.get("extra_input_sep")),
        "version": maps_info.get("version"),
        "n_in": maps_info.get("n_in"),
        "n_out": maps_info.get("n_out"),
        "signed_semantics_unchanged": signed_unchanged,
        "tag": tag,
        "diffs": diffs,
        "severity": sev,
        "class": cls,
    }


def _axis_c(intent: TransactionIntent, sc: dict[str, Any]) -> dict[str, Any]:
    expected = intent.expected_review()
    diffs: list[str] = []
    if not sc.get("ok"):
        return {
            "ok": False,
            "ui_route_actual": None,
            "ui_route_expected": expected["ui_route"],
            "diffs": [f"capture failed: {sc.get('error')}"],
            "severity": "MEDIUM",
            "class": "MALFORMED",
            "user_would_sign": False,
        }

    actual_route = sc.get("ui_route")
    shown = sc.get("shown_address_amounts") or []
    pairing_mismatch = any(not row.get("address_matches_output") for row in shown)
    token_outs = sc.get("token_outs") or 0
    token_ins = sc.get("token_ins") or 0
    genesis_blind = bool(
        expected.get("genesis")
        and token_outs
        and token_ins == 0
        and actual_route == "BCH_ONLY"
    )
    if actual_route != expected["ui_route"]:
        diffs.append(f"ui_route actual={actual_route} expected={expected['ui_route']}")
    if genesis_blind:
        diffs.append("genesis BCH_ONLY when tokens present")
    if pairing_mismatch:
        diffs.append("displayed address/amount belongs to a different output (SCR-05)")

    hybrid_ft_omitted = bool(sc.get("hybrid_ft_omitted"))
    if expected.get("hybrid") and hybrid_ft_omitted:
        diffs.append("hybrid FT omitted from FT bucket")
    elif hybrid_ft_omitted:
        diffs.append("hybrid FT omitted from FT bucket")

    change_as_payment = False
    dests = (sc.get("model") or {}).get("destination_addresses") or []
    model_outs = (sc.get("model") or {}).get("outputs") or []
    addressed = [i for i, o in enumerate(model_outs) if o.get("address")]
    for dest_i, out_i in enumerate(addressed):
        if out_i in expected.get("change", []) and dest_i < len(dests):
            change_as_payment = True
            break
    if not change_as_payment and expected.get("change") and actual_route == "BCH_ONLY" and len(dests) > 1:
        # Dest list is every addressed output, including change.
        change_as_payment = True
    if change_as_payment:
        diffs.append("change listed as payment/destination")

    nft_in = sc.get("nft_in_count") if sc.get("nft_in_count") is not None else sc.get("nft_in") or 0
    nft_out = sc.get("nft_out_count") if sc.get("nft_out_count") is not None else sc.get("nft_out") or 0
    warnings = sc.get("nft_warnings") or {}
    burn_silent = nft_in > nft_out and not any(w == "burning" for w in warnings.values())
    if any(o.role == "burn" for o in intent.outputs) and not any(w == "burning" for w in warnings.values()):
        burn_silent = True
    if burn_silent:
        diffs.append("burn warning silent")

    user_would_sign = True  # SeedCash does not refuse genesis / map-shift / hybrid
    tokens_in_signed_hidden = genesis_blind or hybrid_ft_omitted or (
        token_outs > 0 and actual_route == "BCH_ONLY" and expected["ui_route"] != "BCH_ONLY"
    )

    sev: str | None = None
    cls = "VALID"
    if pairing_mismatch and user_would_sign:
        sev = "CRITICAL"
        cls = "SECURITY-SENSITIVE"
    elif tokens_in_signed_hidden and user_would_sign:
        sev = "HIGH"
        cls = "SECURITY-SENSITIVE"
    elif burn_silent:
        sev = "HIGH"
        cls = "SECURITY-SENSITIVE"
    elif change_as_payment:
        sev = _worse(sev, "LOW") or "LOW"
        cls = "AMBIGUOUS"
    elif actual_route != expected["ui_route"]:
        sev = _worse(sev, "MEDIUM") or "MEDIUM"
        cls = "AMBIGUOUS"

    review_ok = not (
        pairing_mismatch
        or genesis_blind
        or hybrid_ft_omitted
        or change_as_payment
        or burn_silent
        or actual_route != expected["ui_route"]
    )
    return {
        "ok": review_ok,
        "ui_route_actual": actual_route,
        "ui_route_expected": expected["ui_route"],
        "genesis_blind": genesis_blind,
        "address_amount_mismatch": pairing_mismatch,
        "hybrid_ft_omitted": hybrid_ft_omitted,
        "change_listed_as_payment": change_as_payment,
        "burn_warning_silent": burn_silent,
        "shown_address_amounts": shown,
        "nft_warnings": warnings,
        "user_would_sign": user_would_sign,
        "diffs": diffs,
        "severity": sev,
        "class": cls,
    }


def _overall_class(a: dict[str, Any], b: dict[str, Any], c: dict[str, Any], sc_ok: bool) -> str:
    for axis in (c, a, b):
        if axis.get("class") == "SECURITY-SENSITIVE":
            return "SECURITY-SENSITIVE"
    if not sc_ok or a.get("class") == "MALFORMED" or c.get("class") == "MALFORMED":
        return "MALFORMED"
    if c.get("class") == "AMBIGUOUS" or a.get("class") == "AMBIGUOUS":
        return "AMBIGUOUS"
    if b.get("class") == "UNSUPPORTED" and b.get("tag") == "INTEROP" and a.get("ok") and c.get("ok"):
        return "VALID"
    if b.get("class") == "UNSUPPORTED":
        return "UNSUPPORTED"
    return "VALID"


def evaluate(intent: TransactionIntent, vector: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare intent + generate(intent.to_engine_config()) vs SeedCash vs maps."""
    if vector is None:
        vector = generate(intent.to_engine_config())
    raw_hex = vector.get("psbt_hex") or ""
    raw = bytes.fromhex(raw_hex) if raw_hex else b""
    sc = capture(raw) if raw else {"ok": False, "error": "no psbt_hex"}
    maps_info = maps_vs_unsigned(raw) if raw else {"ok": False, "diffs": ["no_psbt"], "naive_shift": False}

    a = _axis_a(intent, vector, sc)
    b = _axis_b(maps_info, sc)
    c = _axis_c(intent, sc)
    for axis in (a, b, c):
        axis["status"] = "pass" if axis.get("ok") else "fail"

    sev = None
    for axis in (a, b, c):
        sev = _worse(sev, axis.get("severity"))
    if sev is None:
        sev = "INFO"

    sc_ok = bool(sc.get("ok"))
    paytaca_agrees = bool(maps_info.get("ok"))
    unsigned_agrees = bool(a.get("model_matches_unsigned"))
    signed_would_match = bool(SIGNED_FOLLOWS_UNSIGNED_TX and unsigned_agrees and a.get("ok"))
    reachable = sc_ok
    only_unsupported = (
        b.get("class") == "UNSUPPORTED"
        and a.get("ok")
        and c.get("ok")
        and not c.get("user_would_sign", True)
    )
    # Map-shift interop is reached and signed; not an unsupported-reject.
    if b.get("tag") == "INTEROP" and sc_ok:
        only_unsupported = False

    overall = _overall_class(a, b, c, sc_ok)
    return {
        "id": intent.id,
        "txid": vector.get("txid"),
        "dialect": vector.get("dialect"),
        "transaction_correctness": a,
        "psbt_semantic_correctness": b,
        "review_correctness": c,
        "A": a,
        "B": b,
        "C": c,
        "severity": sev,
        "class": overall,
        "classification": overall,
        "false_positive_defense": {
            "reproducible": True,
            "paytaca_agrees": paytaca_agrees,
            "unsigned_agrees": unsigned_agrees,
            "signed_would_match": signed_would_match,
            "reachable": reachable,
            "only_unsupported": only_unsupported,
        },
        "seedcash_ok": sc_ok,
        "seedcash_ui_route": sc.get("ui_route"),
        "ur": sc.get("ur"),
    }
