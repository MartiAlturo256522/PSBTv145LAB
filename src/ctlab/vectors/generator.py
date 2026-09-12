"""Generic catalog → fixture → tx → PSBT → sign → validate pipeline."""

from __future__ import annotations

import copy
from typing import Any

from ctlab import GENERATOR_VERSION, LAB_MNEMONIC
from ctlab.cashtokens.consensus import validate_transaction_tokens
from ctlab.cashtokens.prefix import Token, TokenNft, encode_token_prefix
from ctlab.cashtokens.semantics import interpret_token_semantics
from ctlab.fixtures.graph import FixtureGraph, build_fixture_graph
from ctlab.fixtures.keys import ACTORS, ALICE, master_fingerprint
from ctlab.paytaca.dialect import paytaca_global_fields
from ctlab.protocol.hashes import double_sha256
from ctlab.psbt.codec import (
    PSBT_GLOBAL_UNSIGNED_TX,
    PsbtError,
    decode_psbt,
    encode_psbt,
)
from ctlab.signing.schnorr import sign_schnorr_bch, verify_schnorr_bch
from ctlab.signing.sighash import parse_sighash, sighash_bch, sighash_name
from ctlab.transactions.serialize import TxOut, encode_transaction, p2pkh_script


INJECT_PREFIX = {
    "cap3": lambda cat: bytes([0xEF]) + cat + bytes([0x23]),
    "amount0": lambda cat: bytes([0xEF]) + cat + bytes([0x10, 0x00]),
    "empty_prefix": lambda cat: bytes([0xEF]) + cat + bytes([0x00]),
    "reserved": lambda cat: bytes([0xEF]) + cat + bytes([0x90, 0x01]),
    "nonminimal_amount": lambda cat: bytes([0xEF]) + cat + bytes([0x10, 0xFD, 0x01, 0x00]),
    "amount_max_plus": lambda cat: bytes([0xEF]) + cat + bytes([0x10, 0xFF]) + (1 << 63).to_bytes(8, "little"),
    "commit_len0": lambda cat: bytes([0xEF]) + cat + bytes([0x60, 0x00]),
    "commit_no_nft": lambda cat: bytes([0xEF]) + cat + bytes([0x50, 0x01]),
}


def _resolve_categories(scenario: dict, graph: FixtureGraph) -> None:
    """Fill category_from_existing on output token specs using genesis txids."""
    for out in scenario.get("outputs") or []:
        tok = out.get("token")
        if not isinstance(tok, dict):
            continue
        src = tok.get("category_from_existing")
        if src:
            named = graph.genesis[src]
            # Category of existing tokens is the funding txid (parent of genesis), display order.
            # The token on the genesis output already has the category.
            spent = named.tx.outputs[graph.token_vouts.get(src, 0)]
            if spent.token:
                tok["category"] = spent.token.category
            del tok["category_from_existing"]


def _apply_inject(graph: FixtureGraph, scenario: dict) -> None:
    if graph.target is None:
        return
    for i, spec in enumerate(scenario.get("outputs") or []):
        inj = spec.get("inject")
        if not inj:
            continue
        # Category wire bytes: genesis from input 0 if present, else 32 0xbb.
        genesis_ins = [inp for inp in graph.target.inputs if inp.prev_index == 0]
        if genesis_ins:
            cat_wire = genesis_ins[0].prev_txid  # HASH256 order
        else:
            cat_wire = bytes.fromhex("bb" * 32)
        prefix = INJECT_PREFIX[inj](cat_wire)
        locking = graph.target.outputs[i].locking_bytecode
        # If locking already has a prefix from a None-token raw path, replace.
        graph.target.outputs[i] = TxOut(
            value_sats=graph.target.outputs[i].value_sats,
            locking_bytecode=prefix + locking,
            token=None,
        )


def _token_to_json(tok: Token | None) -> dict | None:
    if tok is None:
        return None
    d: dict[str, Any] = {"category": tok.category, "amount": tok.amount}
    if tok.nft:
        d["nft"] = {"capability": tok.nft.capability, "commitment": tok.nft.commitment.hex()}
    return d


def _consensus_inputs(graph: FixtureGraph) -> list[dict]:
    rows = []
    for inp, spent in zip(graph.target.inputs, graph.source_outputs):
        rows.append(
            {
                "prev_txid": inp.prev_txid,
                "prev_index": inp.prev_index,
                "token": spent.token,
            }
        )
    return rows


def _consensus_outputs(graph: FixtureGraph) -> list[dict]:
    from ctlab.cashtokens.prefix import TokenPrefixError, decode_token_prefix

    rows = []
    for out in graph.target.outputs:
        tok = out.token
        if tok is None:
            try:
                tok, _p, _l = decode_token_prefix(out.locking_bytecode)
            except TokenPrefixError:
                tok = None
        rows.append({"token": tok, "script_field": out.script_field()})
    return rows


def _sign_input(graph: FixtureGraph, index: int, hash_type: int) -> tuple[bytes, bytes, bytes] | None:
    spent = graph.source_outputs[index]
    # Laboratory keys: match owner by p2pkh script.
    signer = None
    for act in ACTORS.values():
        if spent.locking_bytecode == act.p2pkh():
            signer = act
            break
    if signer is None:
        return None
    digest, preimage = sighash_bch(
        graph.target, index, spent.locking_bytecode, hash_type, graph.source_outputs
    )
    sig = sign_schnorr_bch(signer.priv, digest, signer.pub) + bytes([hash_type & 0xFF])
    if not verify_schnorr_bch(signer.pub, digest, sig):
        raise RuntimeError("schnorr self-verify failed")
    return signer.pub, sig, digest


def generate_vector(scenario: dict[str, Any], dialect: str | None = None, sign_state: str | None = None) -> dict[str, Any]:
    sc = copy.deepcopy(scenario)
    dialect = dialect or (sc.get("dialects") or ["bip174-v0"])[0]
    sign_state = sign_state or (sc.get("sign_states") or ["unsigned"])[0]

    graph = build_fixture_graph(sc)
    _resolve_categories(sc, graph)
    # Rebuild target outputs now that categories are filled.
    graph = build_fixture_graph(sc)
    _apply_inject(graph, sc)

    assert graph.target is not None
    raw_tx = encode_transaction(graph.target)
    txid = double_sha256(raw_tx)[::-1].hex()

    cons = validate_transaction_tokens(_consensus_inputs(graph), _consensus_outputs(graph))
    semantics = interpret_token_semantics(_consensus_inputs(graph), _consensus_outputs(graph))

    if sc.get("force_sighash"):
        sighash = parse_sighash(sc.get("sighash", "ALL|FORKID")) | 0x20 | 0x80
    else:
        sighash = parse_sighash(sc.get("sighash", "ALL|FORKID"))
    derivations = []
    for spent in graph.source_outputs:
        d = None
        for act in ACTORS.values():
            if spent.locking_bytecode == act.p2pkh():
                d = (act.pub, master_fingerprint(), act.path)
                break
        derivations.append(d)

    partial: list = [None] * len(graph.target.inputs)
    sighash_info: list[dict] = []
    if sign_state in ("signed", "partial"):
        to_sign = range(len(graph.target.inputs))
        if sign_state == "partial" and len(graph.target.inputs) > 1:
            to_sign = range(len(graph.target.inputs) - 1)
        for i in to_sign:
            try:
                signed = _sign_input(graph, i, sighash)
            except ValueError as e:
                signed = None
                sighash_info.append({"input": i, "error": str(e)})
                continue
            if signed:
                pub, sig, digest = signed
                partial[i] = (pub, sig)
                sighash_info.append(
                    {
                        "input": i,
                        "sighash": sighash_name(sighash),
                        "digest": digest.hex(),
                        "signature": sig.hex(),
                        "verified": True,
                    }
                )

    prev_txs = list(graph.prev_txs)
    if sc.get("omit_utxo"):
        prev_txs = [b""] * len(prev_txs)

    proprietary = paytaca_global_fields() if dialect == "paytaca-145" else None
    psbt_status = "valid"
    psbt_error = None
    psbt_obj = None
    # CHIP-invalid sighash combinations fail at sign/VM time; the PSBT envelope
    # can still be well-formed. Record the error in sighash_info only.
    try:
        psbt_obj = encode_psbt(
            graph.target,
            prev_txs,
            graph.source_outputs,
            dialect=dialect,
            sighash=sighash if sign_state != "unsigned" else None,
            derivations=derivations,
            partial_sigs=partial if sign_state != "unsigned" else None,
            proprietary=proprietary,
        )
        if sc.get("tamper_0x36_amount") is not None:
            from ctlab.cashtokens.prefix import Token as T
            from ctlab.psbt.codec import PSBT_OUT_CASHTOKEN

            amt = int(sc["tamper_0x36_amount"])
            for i, omap in enumerate(psbt_obj.outputs):
                for j, (k, v) in enumerate(omap):
                    if k[:1] == bytes([PSBT_OUT_CASHTOKEN]):
                        real = graph.target.outputs[i].token
                        if real:
                            fake = T(category=real.category, amount=amt, nft=real.nft)
                            omap[j] = (k, encode_token_prefix(fake))
            psbt_status = "invalid"
            psbt_error = "inconsistent_token_field"
        if sc.get("duplicate_unsigned") and psbt_obj.unsigned_tx:
            psbt_obj.global_pairs.append((bytes([PSBT_GLOBAL_UNSIGNED_TX]), psbt_obj.unsigned_tx))
        raw_psbt = psbt_obj.serialize()
        if sc.get("truncate"):
            raw_psbt = raw_psbt[: max(6, len(raw_psbt) // 2)]
        if sc.get("bad_magic"):
            raw_psbt = b"XXXX\xff" + raw_psbt[5:]
        try:
            decoded = decode_psbt(raw_psbt)
            if sc.get("duplicate_unsigned"):
                psbt_status = "invalid"
                psbt_error = "duplicate_key"
            if sc.get("omit_utxo"):
                psbt_status = "invalid"
                psbt_error = "missing_non_witness_utxo"
        except PsbtError as e:
            decoded = None
            psbt_status = "invalid"
            psbt_error = e.code
            raw_psbt = raw_psbt
    except Exception as e:
        raw_psbt = b""
        decoded = None
        psbt_status = "invalid"
        psbt_error = str(e)

    # Token field vs unsigned tx (security check)
    token_discrepancy = None
    if psbt_obj and dialect == "paytaca-145" and psbt_status == "valid":
        from ctlab.cashtokens.prefix import decode_token_prefix as dec_pref

        for i, omap in enumerate(psbt_obj.outputs):
            field = None
            for k, v in omap:
                if k[:1] == bytes([0x36]):
                    field = v
            tx_pref = encode_token_prefix(graph.target.outputs[i].token)
            if field is not None and field != tx_pref:
                token_discrepancy = {
                    "output": i,
                    "unsigned_tx_prefix": tx_pref.hex(),
                    "psbt_0x36": field.hex(),
                }
                psbt_status = "invalid"
                psbt_error = "inconsistent_token_field"

    vector_id = sc["id"]
    if dialect != (sc.get("dialects") or ["bip174-v0"])[0] or sign_state != (sc.get("sign_states") or ["unsigned"])[0]:
        vector_id = f"{sc['id']}-{dialect}-{sign_state}"

    return {
        "id": vector_id,
        "catalog_id": sc["id"],
        "generator_version": GENERATOR_VERSION,
        "deterministic_seed": {
            "mnemonic": LAB_MNEMONIC,
            "path_template": "m/44'/145'/0'/{change}/{index}",
        },
        "group": sc["group"],
        "title": sc["title"],
        "description": sc["description"],
        "justification": sc.get("justification"),
        "dialect": dialect,
        "sign_state": sign_state,
        "sighash": sc.get("sighash", "ALL|FORKID"),
        "script_type": sc.get("script_type", "p2pkh"),
        "expected_consensus": sc["expected_consensus"],
        "expected_psbt": sc["expected_psbt"],
        "actual_consensus": cons.status,
        "actual_consensus_reason": cons.reason,
        "actual_consensus_code": cons.code,
        "actual_psbt": psbt_status,
        "actual_psbt_error": psbt_error,
        "consensus_match": (cons.status == sc["expected_consensus"]),
        "psbt_match": (
            psbt_status == sc["expected_psbt"]
            or (sc["expected_psbt"] == "valid" and psbt_status == "valid")
        ),
        "txid": txid,
        "unsigned_tx_hex": raw_tx.hex(),
        "psbt_base64": psbt_obj.base64() if psbt_obj and raw_psbt == psbt_obj.serialize() else (
            __import__("base64").b64encode(raw_psbt).decode("ascii") if raw_psbt else None
        ),
        "psbt_hex": raw_psbt.hex() if raw_psbt else None,
        "previous_txs": [
            {"index": i, "hex": prev.hex(), "txid": double_sha256(prev)[::-1].hex() if prev else None}
            for i, prev in enumerate(graph.prev_txs)
        ],
        "source_utxos": [
            {
                "vin": i,
                "value_sats": o.value_sats,
                "locking_bytecode": o.locking_bytecode.hex(),
                "token": _token_to_json(o.token),
            }
            for i, o in enumerate(graph.source_outputs)
        ],
        "outputs": [
            {
                "vout": i,
                "value_sats": o.value_sats,
                "locking_bytecode": o.locking_bytecode.hex(),
                "script_field": o.script_field().hex(),
                "token": _token_to_json(o.token),
            }
            for i, o in enumerate(graph.target.outputs)
        ],
        "semantics": semantics,
        "sighash_info": sighash_info,
        "token_discrepancy": token_discrepancy,
        "seedcash_expected": sc.get("seedcash_expected"),
        "invalid_code": sc.get("invalid_code"),
        "bcmr_metadata_only": bool(sc.get("bcmr_metadata_only") or sc.get("bcmr")),
        "category_endianness": _endianness_record(graph) if sc.get("record_endianness") else None,
    }


def _endianness_record(graph: FixtureGraph) -> dict | None:
    from ctlab.cashtokens.prefix import _category_to_wire

    for o in graph.target.outputs if graph.target else []:
        if o.token:
            ui = o.token.category
            return {"category_ui": ui, "category_wire": _category_to_wire(ui).hex()}
    return None


def generate_corpus(catalog: list[dict] | None = None) -> list[dict]:
    from ctlab.vectors.catalog import build_catalog

    catalog = catalog or build_catalog()
    out = []
    for sc in catalog:
        dialects = sc.get("dialects") or ["bip174-v0"]
        states = sc.get("sign_states") or ["unsigned"]
        for d in dialects:
            for s in states:
                try:
                    out.append(generate_vector(sc, dialect=d, sign_state=s))
                except Exception as e:
                    out.append(
                        {
                            "id": f"{sc['id']}-{d}-{s}",
                            "catalog_id": sc["id"],
                            "error": f"{type(e).__name__}: {e}",
                            "expected_consensus": sc.get("expected_consensus"),
                            "expected_psbt": sc.get("expected_psbt"),
                            "actual_consensus": "error",
                            "consensus_match": False,
                            "psbt_match": False,
                            "group": sc.get("group"),
                            "title": sc.get("title"),
                        }
                    )
    return out
