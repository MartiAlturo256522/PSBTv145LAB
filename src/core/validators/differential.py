"""Standalone validation using local Python receiver and wire references.

These checks do not claim verification against a running external device.
"""

from __future__ import annotations

from typing import Any


def try_seedcash_parse(psbt_bytes: bytes) -> dict[str, Any]:
    try:
        from core.receiver.psbt_parser import PSBTParser, parse_token_script
    except Exception as e:
        return {"status": "error", "reason": f"local receiver not importable: {e}"}
    try:
        parser = PSBTParser(bytearray(psbt_bytes))
        nfts = list(parser.nft_categories)
        fts = list(parser.token_categories)
        return {
            "status": "decoded",
            "source": "core.receiver.psbt_parser",
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


def try_prefix_reference(token_spec: dict) -> dict[str, Any]:
    """Encode with the independent Python CHIP specification reference."""
    from core.validators.prefix_reference import encode_prefix_wire, ui_category_to_wire

    try:
        nft = token_spec.get("nft")
        prefix = encode_prefix_wire(
            ui_category_to_wire(token_spec["category_ui_hex"]),
            amount=token_spec.get("amount", 0),
            nft_capability=nft.get("capability", "none") if nft else None,
            commitment=bytes.fromhex(nft.get("commitment_hex", "")) if nft else b"",
        )
        return {"status": "ok", "prefix_hex": prefix.hex(), "source": "python-chip-reference"}
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "error", "reason": str(exc), "source": "python-chip-reference"}


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
    from core.validators.paytaca_reference import parse_psbt, serialize_paytaca

    reference = {"status": "SKIPPED", "reason": "no v145 PSBT"}
    if psbt_hex and vector.get("dialect") == "paytaca-145":
        try:
            raw = bytes.fromhex(psbt_hex)
            parsed = parse_psbt(raw, extra_input_separator=True)
            encoded = serialize_paytaca(parsed["global"], parsed["inputs"], parsed["outputs"])
            matched = bool(parsed["ok"] and encoded == raw)
            reference = {"status": "PASS" if matched else "FAIL", "source": "python-wire-reference"}
        except ValueError as exc:
            reference = {"status": "REJECTED", "reason": str(exc), "source": "python-wire-reference"}
    bchn = try_bchn()
    our = "valid" if vector.get("actual_consensus") == "valid" else vector.get("actual_consensus")
    self_ok = bool(vector.get("consensus_match") and vector.get("psbt_match"))
    independent_ran = any(
        x.get("status") in ("decoded", "PASS")
        for x in (bchn, seedcash)
    )
    if vector.get("error"):
        status = "ERROR"
    elif (not self_ok or reference["status"] == "FAIL"
          or (reference["status"] == "REJECTED" and vector.get("actual_psbt") == "valid")
          or seedcash["status"] == "error"):
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
        "python_reference": reference["status"],
        "python_reference_detail": reference,
        "bchn": bchn["status"],
        "paytaca": paytaca_status,
        "our_parser": our,
        "seedcash": seedcash["status"],
        "seedcash_detail": seedcash,
        "status": status,
        "validation_scope": "local-python",
        "external_device_verified": False,
        "self_consistent": self_ok,
        "notes": [
            reference.get("reason"),
            bchn.get("reason"),
            vector.get("actual_consensus_reason"),
            vector.get("actual_psbt_error"),
            None if independent_ran else "no independent oracle ran; SKIPPED is not PASS",
        ],
    }
