"""Turn one row of psbtV145CashTokenScenarios.json into an engine config.

The document describes the tests. This module is the only place that decides
which inputs, outputs and token amounts make that description a BCH transaction.
"""

from __future__ import annotations

from typing import Any

OWNERS = ["alice", "bob", "carol", "dave", "change"]
SIGHASHES = ["ALL|FORKID", "ALL|FORKID|UTXOS", "0x01"]


def _num(key: str, label: str, value: int, mn: int = 0, mx: int | None = None) -> dict:
    item: dict[str, Any] = {"key": key, "label": label, "type": "number", "value": value, "min": mn}
    if mx is not None:
        item["max"] = mx
    return item


def _text(key: str, label: str, value: str) -> dict:
    return {"key": key, "label": label, "type": "text", "value": value}


def _sel(key: str, label: str, value: str, options: list[str]) -> dict:
    return {"key": key, "label": label, "type": "select", "value": value, "options": options}


def _bool(key: str, label: str, value: bool) -> dict:
    return {"key": key, "label": label, "type": "bool", "value": value}


def _common() -> list[dict]:
    return [
        _sel("sighash", "Sighash", "ALL|FORKID", SIGHASHES),
        _bool("emit_sighash", "Incluir sighash en el PSBT", True),
        _num("fragment_len", "Bytes por fragmento UR", 400, 20, 4000),
    ]


def _money(inp: int = 100_000, fee: int = 1_000) -> list[dict]:
    return [
        _num("input_sats", "Satoshis de cada entrada", inp, 546),
        _num("fee_sats", "Comisión (sats)", fee, 0),
    ]


def _ft_fields(amount: int = 1_000, send: int | None = None) -> list[dict]:
    rows = [_num("ft_amount", "Cantidad FT", amount, 1)]
    if send is not None:
        rows.append(_num("ft_send", "FT que se envían", send, 0))
    return rows


def _nft_fields(cap: str = "none", commit: str = "aa") -> list[dict]:
    return [
        _sel("capability", "Capacidad NFT", cap, ["none", "mutable", "minting"]),
        _text("commitment", "Commitment (hex o texto)", commit),
    ]


def _owner() -> list[dict]:
    return [_sel("owner_out", "Destino", "bob", OWNERS)]


def _nfield(value: int, label: str = "Cantidad N", mx: int = 100) -> dict:
    return _num("n", label, value, 1, mx)


def schema_for(slug: str) -> list[dict]:
    extra: list[dict] = []
    money = _money()
    if slug in {"p2pkh-1-to-2", "ft-transfer-with-change", "bch-change-separate-from-ft-change", "bch-and-ft-change-in-the-same-output"}:
        extra += [_num("payment_sats", "Satoshis del pago", 20_000, 546)]
    if slug in {"bch-consolidation-n-to-1", "ft-consolidation", "mass-multi-category-burn-cleanup"}:
        extra += [_nfield(3 if "mass" not in slug else 10, "Número de entradas")]
    if slug == "bch-distribution-1-to-n":
        extra += [_nfield(4, "Número de salidas", 40)]
    if slug in {"ft-splitting", "multiple-nft-minting", "mass-distribution-airdrop-100-ft-outputs"}:
        extra += [_nfield(100 if slug.startswith("mass-distribution") else 3, "Número de salidas")]
    if slug == "massive-consolidation-100-ft-inputs":
        extra += [_nfield(100, "Número de entradas FT")]
    if slug in {"multi-category-transfer-2-fts", "multi-category-transfer-with-change"}:
        extra += [_nfield(2, "Categorías FT", 8)]
    if slug == "ft-transfer-across-5-categories":
        extra += [_nfield(5, "Categorías FT", 12)]
    if slug == "multi-token-mesh-transaction":
        extra += [_nfield(10, "Categorías FT", 12), _num("n_nft", "NFTs", 5, 1, 8)]
    if slug == "token-coinjoin-mixer":
        extra += [_nfield(5, "Participantes", 5)]
    if slug in {
        "pure-ft-genesis-input-0", "ft-genesis-in-secondary-input", "exact-ft-transfer-1-1",
        "ft-transfer-with-change", "ft-consolidation", "ft-splitting", "partial-ft-burn-50-example",
        "minimum-partial-burn-1-ft", "total-ft-burn-100-burn", "maximum-ft-amount-2-63-1",
        "massive-consolidation-100-ft-inputs", "mass-distribution-airdrop-100-ft-outputs",
        "fungible-output-exceeds-input", "fungible-amount-overflow",
    } or slug.startswith("multi-category") or slug.startswith("ft-transfer") or "ft" in slug and "nft" not in slug:
        if slug == "maximum-ft-amount-2-63-1":
            extra += [_text("ft_amount_text", "Cantidad FT", "9223372036854775807")]
        else:
            send = 400 if "change" in slug or slug == "partial-ft-burn-50-example" else None
            if slug == "minimum-partial-burn-1-ft":
                extra += _ft_fields(2, 1)
            elif slug == "partial-ft-burn-50-example":
                extra += _ft_fields(100, 50)
            elif slug == "total-ft-burn-100-burn":
                extra += _ft_fields(100, 0)
            else:
                extra += _ft_fields(1_000 if slug != "massive-consolidation-100-ft-inputs" else 1, send)
    if any(k in slug for k in ("nft", "commitment", "mint", "genesis-none", "mutable", "immutable")) and slug not in {
        "pure-ft-genesis-input-0", "ft-genesis-in-secondary-input",
    }:
        cap = "mutable" if "mutable" in slug else "minting" if "minting" in slug else "none"
        commit = "aa" * 20 if "40-bytes" in slug or slug == "maximum-commitment-size-40-bytes" else "aa"
        if slug == "oversized-nft-commitment":
            commit = "bb" * 21
        extra += _nft_fields(cap, commit)
    if slug == "pure-op-return-data" or "op-return" in slug or slug == "op-return-interleaved-between-tokens":
        extra += [_text("op_return_hex", "Datos OP_RETURN (hex)", "636173682d746f6b656e")]
    if slug == "relative-timelock-csv":
        extra += [_num("csv_blocks", "Bloques CSV", 10, 1, 65535)]
    if slug == "absolute-timelock-cltv":
        extra += [_num("locktime", "Locktime (altura o tiempo)", 800_000, 1)]
    if slug == "exact-dust-limit-546-satoshis":
        money = _money(10_000, 546)
        extra += [_num("dust_sats", "Dust de la salida token", 546, 1)]
    if slug == "bch-overfunded-token-utxo":
        money = _money(200_000_000, 1_000)
        extra += [_num("token_sats", "Satoshis en la salida token", 100_000_000, 546)]
    if slug == "invalid-ur-transport-payload":
        extra += [_sel("ur_break", "Cómo romper el UR", "truncate", ["truncate", "cbor-wrap", "none"])]
    extra += _owner()
    # Drop duplicate keys, keep the first.
    seen: set[str] = set()
    rows: list[dict] = []
    for item in money + extra + _common():
        if item["key"] in seen:
            continue
        seen.add(item["key"])
        rows.append(item)
    return rows


def apply_overrides(schema: list[dict], overrides: dict | None) -> tuple[list[dict], dict]:
    overrides = overrides or {}
    filled = []
    values: dict[str, Any] = {}
    for item in schema:
        item = dict(item)
        if item["key"] in overrides and overrides[item["key"]] is not None and overrides[item["key"]] != "":
            raw = overrides[item["key"]]
            if item["type"] == "number":
                item["value"] = int(raw)
            elif item["type"] == "bool":
                item["value"] = raw if isinstance(raw, bool) else str(raw).lower() in {"1", "true", "yes", "on"}
            else:
                item["value"] = str(raw)
        values[item["key"]] = item["value"]
        filled.append(item)
    return filled, values


def _need(out_sats: int, label: str) -> None:
    if out_sats < 546:
        raise ValueError(f"{label} queda en {out_sats} sats. Sube la entrada o baja la comisión.")


def _ft(n: int) -> dict:
    return {"nft": None, "amount": int(n)}


def _nft(cap: str, commit: str, amount: int = 0) -> dict:
    return {"nft": {"capability": cap, "commitment": commit}, "amount": int(amount)}


def _from(key: str, token: dict) -> dict:
    token = dict(token)
    token["category_from_existing"] = key
    return token


def _out(owner: str, sats: int, token: dict | None = None, genesis_from: int | None = None, script: str = "p2pkh", data_hex: str | None = None) -> dict:
    row: dict[str, Any] = {"owner": owner, "sats": int(sats), "script": script}
    if token is not None:
        row["token"] = token
    if genesis_from is not None:
        row["genesis_from"] = genesis_from
    if data_hex is not None:
        row["data_hex"] = data_hex
    return row


def _bch(key: str, owner: str, sats: int, vout: int = 1, script: str = "p2pkh", redeem_hex: str | None = None, sequence: int = 0xFFFFFFFF) -> dict:
    row: dict[str, Any] = {
        "kind": "bch", "key": key, "owner": owner, "sats": int(sats), "vout": vout, "script": script,
        "sequence": sequence,
    }
    if redeem_hex:
        row["redeem_hex"] = redeem_hex
    return row


def _genesis(key: str, owner: str, sats: int, script: str = "p2pkh", redeem_hex: str | None = None, sequence: int = 0xFFFFFFFF) -> dict:
    row: dict[str, Any] = {
        "kind": "genesis_parent", "key": key, "owner": owner, "sats": int(sats), "script": script,
        "sequence": sequence,
    }
    if redeem_hex:
        row["redeem_hex"] = redeem_hex
    return row


def _token_in(key: str, owner: str = "alice") -> dict:
    return {"kind": "token", "key": key, "owner": owner}


def _existing(key: str, sats: int, token: dict, owner: str = "alice", script: str = "p2pkh", redeem_hex: str | None = None, group: str | None = None) -> dict:
    row: dict[str, Any] = {"key": key, "owner": owner, "sats": int(sats), "token": token, "script": script}
    if redeem_hex:
        row["redeem_hex"] = redeem_hex
    if group:
        row["category_group"] = group
    return row


def _base(scenario: dict, params: dict, inputs: list, outputs: list, existing: list | None = None, **extra: Any) -> dict:
    validity = scenario.get("validity") or ""
    if validity in {"valid-consensus", "valid-consensus-but-unsafe"}:
        expected = "valid"
    else:
        expected = "invalid"
    cfg = {
        "id": f"DOC-{scenario.get('id')}",
        "group": scenario.get("domain") or "document",
        "title": scenario.get("title") or "",
        "description": scenario.get("description") or "",
        "expected_consensus": extra.pop("expected_consensus", expected),
        "expected_psbt": extra.pop("expected_psbt", "valid"),
        "dialect": "paytaca-145",
        "sign_state": extra.pop("sign_state", "unsigned"),
        "sighash": params.get("sighash") or "ALL|FORKID",
        "emit_sighash": bool(params.get("emit_sighash", True)),
        "inputs": inputs,
        "outputs": outputs,
        "existing": existing or [],
        "tx_version": 2,
    }
    cfg.update(extra)
    return cfg


def _script_num(n: int) -> bytes:
    n = int(n)
    if n == 0:
        return b"\x00"
    if 1 <= n <= 16:
        return bytes([0x50 + n])
    value = abs(n)
    body = bytearray()
    while value:
        body.append(value & 0xFF)
        value >>= 8
    if body[-1] & 0x80:
        body.append(0x80 if n < 0 else 0x00)
    elif n < 0:
        body[-1] |= 0x80
    return bytes([len(body)]) + bytes(body)


def _csv_redeem(blocks: int, pubkey: bytes) -> str:
    return (_script_num(blocks) + bytes([0xB2, 0x75, 33]) + pubkey + bytes([0xAC])).hex()


def _cltv_redeem(locktime: int, pubkey: bytes) -> str:
    return (_script_num(locktime) + bytes([0xB1, 0x75, 33]) + pubkey + bytes([0xAC])).hex()


def _multisig(pubs: list[bytes]) -> str:
    body = bytes([0x52])
    for pub in pubs:
        body += bytes([len(pub)]) + pub
    body += bytes([0x50 + len(pubs), 0xAE])
    return body.hex()


def _pubkey(owner: str) -> bytes:
    from ctlab.fixtures.keys import ACTORS

    return ACTORS[owner].pub


def _ft_amount(params: dict, default: int = 1000) -> int:
    if params.get("ft_amount_text"):
        return int(str(params["ft_amount_text"]).strip())
    return int(params.get("ft_amount") or default)


def compile_config(scenario: dict, params: dict) -> tuple[dict, str]:
    slug = scenario["slug"]
    note = ""
    owner = params.get("owner_out") or "bob"
    inp = int(params.get("input_sats") or 100_000)
    fee = int(params.get("fee_sats") or 0)
    cap = params.get("capability") or "none"
    commit = params.get("commitment") if params.get("commitment") is not None else "aa"
    n = max(1, int(params.get("n") or 1))

    if slug == "p2pkh-1-to-1":
        out = inp - fee
        _need(out, "La salida")
        return _base(scenario, params, [_bch("A", "alice", inp, 1)], [_out(owner, out)]), note

    if slug == "p2pkh-1-to-2":
        pay = int(params.get("payment_sats") or 20_000)
        change = inp - fee - pay
        _need(pay, "El pago")
        _need(change, "El cambio")
        return _base(scenario, params, [_bch("A", "alice", inp, 1)], [_out(owner, pay), _out("change", change)]), note

    if slug == "bch-consolidation-n-to-1":
        out = n * inp - fee
        _need(out, "La salida")
        inputs = [_bch(chr(ord("A") + i), "alice", inp, 1) for i in range(n)]
        return _base(scenario, params, inputs, [_out(owner, out)]), note

    if slug == "bch-distribution-1-to-n":
        if n < 2:
            raise ValueError("Una distribución necesita al menos 2 salidas.")
        total = inp - fee
        if total < 546 * n:
            raise ValueError("No hay sats suficientes para tantas salidas de 546.")
        share, rem = divmod(total, n)
        outputs = []
        for i in range(n):
            sats = share + (rem if i == n - 1 else 0)
            outputs.append(_out(OWNERS[i % len(OWNERS)], sats))
        return _base(scenario, params, [_bch("A", "alice", inp, 1)], outputs), note

    if slug == "standard-p2sh-spend":
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_bch("A", "alice", inp, 1, script="p2sh20")],
            [_out(owner, out)],
        ), "El redeem es el P2PKH de alice y viaja en el PSBT."

    if slug == "p2sh-32-spend":
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_bch("A", "alice", inp, 1, script="p2sh32")],
            [_out(owner, out)],
        ), "P2SH32 usa HASH256 (SHA256d) del redeem, no un solo SHA256."

    if slug == "pure-op-return-data":
        pay = inp - fee
        _need(pay, "La salida")
        data = params.get("op_return_hex") or ""
        return _base(
            scenario, params,
            [_bch("A", "alice", inp, 1)],
            [_out(owner, pay), _out("bob", 0, script="op_return", data_hex=data)],
        ), note

    if slug == "relative-timelock-csv":
        blocks = int(params.get("csv_blocks") or 10)
        redeem = _csv_redeem(blocks, _pubkey("alice"))
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_bch("A", "alice", inp, 1, script="p2sh20", redeem_hex=redeem, sequence=blocks)],
            [_out(owner, out)],
        ), "La secuencia de la entrada es el CSV. El script no se ejecuta aquí; el redeem sí va en el PSBT."

    if slug == "absolute-timelock-cltv":
        lock = int(params.get("locktime") or 800_000)
        redeem = _cltv_redeem(lock, _pubkey("alice"))
        out = inp - fee
        _need(out, "La salida")
        cfg = _base(
            scenario, params,
            [_bch("A", "alice", inp, 1, script="p2sh20", redeem_hex=redeem, sequence=0xFFFFFFFE)],
            [_out(owner, out)],
            locktime=lock,
        )
        return cfg, "nLockTime de la transacción y OP_CHECKLOCKTIMEVERIFY usan el mismo valor."

    if slug == "pure-ft-genesis-input-0":
        amt = _ft_amount(params)
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [_out(owner, out, _ft(amt), genesis_from=0)],
        ), note

    if slug == "ft-genesis-in-secondary-input":
        amt = _ft_amount(params)
        half = inp
        out_tok = half - 1_000
        change = half - fee
        _need(out_tok, "La salida token")
        _need(change, "El cambio")
        return _base(
            scenario, params,
            [_bch("Z", "alice", half, 1), _genesis("A", "alice", half)],
            [_out("bob", out_tok), _out(owner, change, _ft(amt), genesis_from=1)],
        ), "La génesis es la entrada 1. La entrada 0 es BCH en vout 1 y no crea categoría."

    if slug in {
        "immutable-nft-genesis-none", "immutable-nft-genesis-with-commitment",
        "mutable-nft-genesis-mutable", "minting-nft-genesis-minting",
    }:
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [_out(owner, out, _nft(cap, commit), genesis_from=0)],
        ), note

    if slug in {
        "mixed-genesis-ft-immutable-nft", "mixed-genesis-ft-mutable-nft", "mixed-genesis-ft-minting-nft",
    }:
        amt = _ft_amount(params, 500)
        a = max(2_000, (inp - fee) // 3)
        b = max(2_000, (inp - fee) // 3)
        change = inp - fee - a - b
        _need(change, "El cambio")
        nft_cap = {"mixed-genesis-ft-immutable-nft": "none", "mixed-genesis-ft-mutable-nft": "mutable", "mixed-genesis-ft-minting-nft": "minting"}[slug]
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [
                _out(owner, a, _nft(nft_cap, commit), genesis_from=0),
                _out("carol", b, _ft(amt), genesis_from=0),
                _out("change", change),
            ],
        ), note

    if slug == "double-genesis-in-one-psbt":
        amt = _ft_amount(params, 50)
        each = inp
        pay = 2_000
        change = each * 2 - fee - pay * 2
        _need(change, "El cambio")
        return _base(
            scenario, params,
            [_genesis("A", "alice", each), _genesis("B", "alice", each)],
            [
                _out(owner, pay, _nft("none", commit), genesis_from=0),
                _out("carol", pay, _ft(amt), genesis_from=1),
                _out("change", change),
            ],
        ), note

    if slug in {"exact-ft-transfer-1-1", "psbt-with-complete-utxo-context"}:
        amt = _ft_amount(params)
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_token_in("T")],
            [_out(owner, out, _from("T", _ft(amt)))],
            [_existing("T", inp, _ft(amt))],
        ), "La entrada token lleva la transacción padre completa (non_witness_utxo)."

    if slug == "ft-transfer-with-change":
        amt = _ft_amount(params, 1_000)
        send = int(params.get("ft_send") or max(1, amt // 2))
        if send > amt:
            raise ValueError("No se pueden enviar más FT de los que entran.")
        pay = int(params.get("payment_sats") or max(546, (inp - fee) // 2))
        change = inp - fee - pay
        _need(pay, "El pago")
        _need(change, "El cambio")
        outputs = [_out(owner, pay, _from("T", _ft(send)))]
        if amt - send > 0:
            outputs.append(_out("change", change, _from("T", _ft(amt - send))))
        else:
            outputs.append(_out("change", change))
        return _base(scenario, params, [_token_in("T")], outputs, [_existing("T", inp, _ft(amt))]), note

    if slug == "ft-consolidation":
        amt = _ft_amount(params, 10)
        out = n * inp - fee
        _need(out, "La salida")
        existing = [_existing(f"T{i}", inp, _ft(amt), group="same") for i in range(n)]
        inputs = [_token_in(f"T{i}") for i in range(n)]
        return _base(scenario, params, inputs, [_out(owner, out, _from("T0", _ft(amt * n)))], existing), note

    if slug == "ft-splitting":
        amt = _ft_amount(params, n)
        if amt < n:
            raise ValueError("La cantidad FT tiene que alcanzar para una unidad por salida.")
        if inp - fee < 546 * n:
            raise ValueError("Faltan sats para tantas salidas.")
        share_ft, rem_ft = divmod(amt, n)
        share_s, rem_s = divmod(inp - fee, n)
        existing = [_existing("T", inp, _ft(amt))]
        outputs = []
        for i in range(n):
            outputs.append(_out(
                OWNERS[i % len(OWNERS)],
                share_s + (rem_s if i == n - 1 else 0),
                _from("T", _ft(share_ft + (rem_ft if i == n - 1 else 0))),
            ))
        return _base(scenario, params, [_token_in("T")], outputs, existing), note

    if slug in {"multi-category-transfer-2-fts", "multi-category-transfer-with-change", "ft-transfer-across-5-categories"}:
        amt = _ft_amount(params, 100)
        cats = n
        change_bch = "change" in slug
        pay = max(546, (inp - fee) // 2) if change_bch else inp - fee
        if change_bch:
            _need(inp - fee - pay, "El cambio")
        existing = [_existing(f"C{i}", inp, _ft(amt)) for i in range(cats)]
        inputs = [_token_in(f"C{i}") for i in range(cats)]
        if change_bch:
            inputs.append(_bch("Z", "alice", inp, 1))
        outputs = [_out(OWNERS[i % 3], pay if not change_bch else max(546, pay // cats), _from(f"C{i}", _ft(amt))) for i in range(cats)]
        spent = sum(x["sats"] for x in existing) + (inp if change_bch else 0)
        spent_out = sum(o["sats"] for o in outputs)
        change = spent - fee - spent_out
        if change < 0:
            raise ValueError("Las salidas superan las entradas. Baja el pago o sube los sats.")
        if change >= 546:
            outputs.append(_out("change", change))
        elif change != 0:
            outputs[-1]["sats"] += change
        return _base(scenario, params, inputs, outputs, existing), note

    if slug == "bch-and-ft-change-in-the-same-output":
        amt = _ft_amount(params, 80)
        send = int(params.get("ft_send") or max(1, amt // 2))
        if send > amt:
            raise ValueError("No se pueden enviar más FT de los que entran.")
        pay = int(params.get("payment_sats") or max(546, (inp - fee) // 3))
        change = inp - fee - pay
        _need(pay, "El pago")
        _need(change, "El cambio")
        outputs = [_out(owner, pay, _from("T", _ft(send)))]
        change_tok = _ft(amt - send) if amt > send else None
        outputs.append(_out("change", change, _from("T", change_tok) if change_tok else None))
        return _base(scenario, params, [_token_in("T")], outputs, [_existing("T", inp, _ft(amt))]), "El cambio de BCH y el cambio de FT van en la misma salida."

    if slug == "bch-change-separate-from-ft-change":
        amt = _ft_amount(params, 80)
        send = int(params.get("ft_send") or max(1, amt // 2))
        pay = int(params.get("payment_sats") or 20_000)
        change = inp - fee - pay
        _need(pay, "El pago")
        _need(change, "El cambio BCH")
        outputs = [_out(owner, pay, _from("T", _ft(send))), _out("change", change)]
        if amt > send:
            # FT change rides on its own output, funded by moving sats off the BCH change.
            ft_out = 2_000
            if change - ft_out < 546:
                raise ValueError("No caben dos cambios. Sube la entrada.")
            outputs = [
                _out(owner, pay, _from("T", _ft(send))),
                _out("alice", ft_out, _from("T", _ft(amt - send))),
                _out("change", change - ft_out),
            ]
        return _base(scenario, params, [_token_in("T")], outputs, [_existing("T", inp, _ft(amt))]), note

    if slug in {"immutable-nft-transfer-none", "commitment-update-mutable-nft", "downgrade-mutable-nft-to-immutable"}:
        out = inp - fee
        _need(out, "La salida")
        src_cap = "mutable" if slug != "immutable-nft-transfer-none" else "none"
        dst_cap = "none" if slug == "downgrade-mutable-nft-to-immutable" else src_cap
        src_commit = "aa" if slug != "commitment-update-mutable-nft" else "aa"
        dst_commit = commit if slug == "commitment-update-mutable-nft" else src_commit
        if slug == "downgrade-mutable-nft-to-immutable":
            dst_commit = src_commit
        return _base(
            scenario, params,
            [_token_in("N")],
            [_out(owner, out, _from("N", _nft(dst_cap, dst_commit)))],
            [_existing("N", inp, _nft(src_cap, src_commit))],
        ), note

    if slug in {"simple-mint-of-1-nft-minting", "mint-mutable-nft", "multiple-nft-minting", "combined-ft-nft-minting", "mint-fts-from-minting-nft"}:
        minted = n if slug == "multiple-nft-minting" else 1
        amt = _ft_amount(params, 25) if slug in {"combined-ft-nft-minting", "mint-fts-from-minting-nft"} else 0
        baton_sats = 2_000
        each = 2_000
        need = baton_sats + each * minted
        if slug == "mint-fts-from-minting-nft":
            need = baton_sats + each
        if inp - fee < need + 546:
            raise ValueError("La entrada no cubre el baton y las piezas minteadas.")
        change = inp - fee - need
        existing = [_existing("M", inp, _nft("minting", ""))]
        outputs = [_out("alice", baton_sats, _from("M", _nft("minting", "", amt if slug == "combined-ft-nft-minting" else 0)))]
        if slug == "mint-fts-from-minting-nft":
            outputs.append(_out(owner, each, _from("M", _ft(amt))))
        else:
            mint_cap = "mutable" if slug == "mint-mutable-nft" else "none"
            for i in range(minted):
                piece = commit if minted == 1 else f"{commit}{i:02x}"
                outputs.append(_out(OWNERS[i % 3], each, _from("M", _nft(mint_cap, piece))))
        if change >= 546:
            outputs.append(_out("change", change))
        else:
            outputs[0]["sats"] += change
        return _base(scenario, params, [_token_in("M")], outputs, existing), note

    if slug == "minting-capability-splitting":
        # Consensus-invalid: one minting NFT cannot become two.
        out_each = max(546, (inp - fee) // 2)
        if out_each * 2 > inp - fee:
            out_each = max(546, (inp // 2) - 1)
        return _base(
            scenario, params,
            [_token_in("M")],
            [
                _out(owner, out_each, _from("M", _nft("minting", commit))),
                _out("carol", inp - fee - out_each, _from("M", _nft("minting", "bb"))),
            ],
            [_existing("M", inp, _nft("minting", ""))],
            expected_consensus="invalid",
        ), "Este caso es inválido a propósito: la autoridad de mint no se puede duplicar."

    if slug == "transfer-of-multiple-distinct-nfts":
        keys = ["N0", "N1", "N2"]
        out = inp - fee // 3
        _need(out, "Cada salida")
        if 3 * out + (fee % 3) > 3 * inp:
            raise ValueError("Comisión demasiado alta.")
        existing = [_existing(k, inp, _nft("none", f"c{i}")) for i, k in enumerate(keys)]
        inputs = [_token_in(k) for k in keys]
        outputs = [_out(OWNERS[i % 3], inp - (fee if i == 0 else 0), _from(k, _nft("none", f"c{i}"))) for i, k in enumerate(keys)]
        # fee only on first output; fix if first went below dust
        if outputs[0]["sats"] < 546:
            raise ValueError("La comisión se come la primera salida.")
        return _base(scenario, params, inputs, outputs, existing), note

    if slug == "hybrid-nft-ft-bch-output":
        amt = _ft_amount(params, 40)
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_token_in("H")],
            [_out(owner, out, _from("H", _nft("none", commit, amt)))],
            [_existing("H", inp, _nft("none", commit, amt))],
        ), note

    if slug == "commitment-swap-between-nfts":
        out = inp - max(0, fee // 2)
        _need(out, "Cada salida")
        existing = [
            _existing("A", inp, _nft("mutable", "aa"), group="swap"),
            _existing("B", inp, _nft("mutable", "bb"), group="swap"),
        ]
        # Two mutable NFTs of one category exchange commitments. Count stays 2.
        outputs = [
            _out(owner, out, _from("A", _nft("mutable", "bb"))),
            _out("carol", inp * 2 - fee - out, _from("A", _nft("mutable", "aa"))),
        ]
        _need(outputs[1]["sats"], "La segunda salida")
        return _base(scenario, params, [_token_in("A"), _token_in("B")], outputs, existing), note

    if slug in {"partial-ft-burn-50-example", "minimum-partial-burn-1-ft", "total-ft-burn-100-burn"}:
        amt = _ft_amount(params, 100)
        send = int(params.get("ft_send") if params.get("ft_send") is not None else 0)
        out = inp - fee
        _need(out, "La salida")
        token = _from("T", _ft(send)) if send > 0 else None
        outputs = [_out(owner, out, token)]
        return _base(scenario, params, [_token_in("T")], outputs, [_existing("T", inp, _ft(amt))]), "Quemar es no devolver los FT. Consenso lo permite."

    if slug in {"immutable-nft-burn-none", "mutable-nft-burn-mutable", "destroy-minting-capability"}:
        src = {"immutable-nft-burn-none": "none", "mutable-nft-burn-mutable": "mutable", "destroy-minting-capability": "minting"}[slug]
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_token_in("N")],
            [_out(owner, out)],
            [_existing("N", inp, _nft(src, commit if src != "minting" else ""))],
        ), "El NFT de entrada no se copia a ninguna salida."

    if slug == "selective-multi-category-burn":
        out_tok = max(546, (inp - fee) // 2)
        change = inp * 2 - fee - out_tok
        _need(change, "El cambio")
        existing = [_existing("K", inp, _ft(10)), _existing("B", inp, _ft(10))]
        return _base(
            scenario, params,
            [_token_in("K"), _token_in("B")],
            [_out(owner, out_tok, _from("K", _ft(10))), _out("change", change)],
            existing,
        ), "Se conserva K y se quema B."

    if slug == "mixed-burn-nft-burn-ft-preservation":
        amt = _ft_amount(params, 30)
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_token_in("H")],
            [_out(owner, out, _from("H", _ft(amt)))],
            [_existing("H", inp, _nft("none", commit, amt))],
        ), note

    if slug == "ft-burn-with-nft-preservation":
        amt = _ft_amount(params, 30)
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_token_in("H")],
            [_out(owner, out, _from("H", _nft("none", commit, 0)))],
            [_existing("H", inp, _nft("none", commit, amt))],
        ), note

    if slug == "mass-multi-category-burn-cleanup":
        out = n * inp - fee
        _need(out, "La salida")
        existing = [_existing(f"J{i}", inp, _ft(1)) for i in range(n)]
        inputs = [_token_in(f"J{i}") for i in range(n)]
        return _base(scenario, params, inputs, [_out(owner, out)], existing), "Ningún token de entrada se reenvía."

    if slug == "utxo-vout-0-non-genesis-existing-token":
        amt = _ft_amount(params, 7)
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_token_in("T")],
            [_out(owner, out, _from("T", _ft(amt)))],
            [_existing("T", inp, _ft(amt))],
            token_bearing_vout0=True,
        ), "El UTXO ya tiene token y está en vout 0: se transfiere, no se usa la categoría nueva."

    if slug == "utxo-vout-0-non-genesis-pure-bch":
        out = inp - fee
        _need(out, "La salida")
        return _base(scenario, params, [_bch("A", "alice", inp, 0)], [_out(owner, out)]), "vout 0 sin tokens de salida. La génesis queda sin usar."

    if slug == "mixed-genesis-neutral-vout-0-utxo":
        amt = _ft_amount(params, 9)
        pay = 2_000
        change = inp * 2 - fee - pay
        _need(change, "El cambio")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp), _bch("Z", "alice", inp, 0)],
            [_out(owner, pay, _ft(amt), genesis_from=0), _out("change", change)],
        ), note

    if slug == "op-return-in-output-0-with-tokens-in-output-1":
        amt = _ft_amount(params, 12)
        out = inp - fee
        _need(out, "La salida token")
        data = params.get("op_return_hex") or "00"
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [
                _out("bob", 0, script="op_return", data_hex=data),
                _out(owner, out, _ft(amt), genesis_from=0),
            ],
        ), note

    if slug == "op-return-interleaved-between-tokens":
        data = params.get("op_return_hex") or "00"
        a = 3_000
        b = 3_000
        change = inp * 2 - fee - a - b
        _need(change, "El cambio")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp), _genesis("B", "alice", inp)],
            [
                _out(owner, a, _nft("none", "aa"), genesis_from=0),
                _out("bob", 0, script="op_return", data_hex=data),
                _out("carol", b, _ft(5), genesis_from=1),
                _out("change", change),
            ],
        ), note

    if slug == "non-contiguous-token-outputs":
        amt = _ft_amount(params, 4)
        t1, mid, t2 = 3_000, 3_000, 3_000
        change = inp - fee - t1 - mid - t2
        _need(change, "El cambio")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [
                _out(owner, t1, _ft(amt), genesis_from=0),
                _out("carol", mid),
                _out("dave", t2, _nft("none", commit), genesis_from=0),
                _out("change", change),
            ],
        ), note

    if slug == "consolidation-of-mixed-vout-utxos":
        # vout 0 pure bch, vout 1 token, vout 5 pure bch
        out = inp * 3 - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [
                _bch("A", "alice", inp, 0),
                _token_in("T"),
                _bch("C", "alice", inp, 5),
            ],
            [_out(owner, out, _from("T", _ft(3)))],
            [_existing("T", inp, _ft(3))],
        ), note

    if slug == "p2sh-multisig-2-of-3-with-nft-mutation":
        redeem = _multisig([_pubkey("alice"), _pubkey("bob"), _pubkey("carol")])
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_token_in("N")],
            [_out(owner, out, _from("N", _nft("mutable", commit or "bb")))],
            [_existing("N", inp, _nft("mutable", "aa"), script="p2sh20", redeem_hex=redeem)],
        ), "Redeem 2-de-3. El laboratorio deja el PSBT sin firmar: SeedCash solo añadiría una firma."

    if slug == "asynchronous-multi-user-signing":
        amt = 15
        people = ["alice", "bob", "carol"]
        out_each = inp - fee
        _need(out_each, "Cada salida")
        existing = [_existing(f"P{i}", inp, _ft(amt), owner=who) for i, who in enumerate(people)]
        inputs = [_token_in(f"P{i}", who) for i, who in enumerate(people)]
        outputs = [_out(OWNERS[(i + 1) % 3], out_each, _from(f"P{i}", _ft(amt))) for i in range(3)]
        # fee removed three times; fix the last output
        outputs[-1]["sats"] = inp * 3 - fee - outputs[0]["sats"] - outputs[1]["sats"]
        _need(outputs[-1]["sats"], "La última salida")
        return _base(scenario, params, inputs, outputs, existing), "Tres dueños distintos. El PSBT va sin firmas para que cada uno añada la suya."

    if slug == "token-coinjoin-mixer":
        amt = 20
        people = OWNERS[:n]
        if len(people) < 2:
            raise ValueError("Un coinjoin necesita al menos 2.")
        out_sats = inp - (fee // n)
        existing = [_existing(f"J{i}", inp, _ft(amt), owner=who, group="join") for i, who in enumerate(people)]
        inputs = [_token_in(f"J{i}", who) for i, who in enumerate(people)]
        # rotate recipients
        outputs = []
        for i, who in enumerate(people):
            dest = people[(i + 1) % len(people)]
            outputs.append(_out(dest, inp, _from("J0", _ft(amt))))
        outputs[-1]["sats"] = n * inp - fee - inp * (n - 1)
        _need(outputs[-1]["sats"], "La última salida")
        return _base(scenario, params, inputs, outputs, existing), note

    if slug == "exact-dust-limit-546-satoshis":
        dust = int(params.get("dust_sats") or 546)
        change = inp - fee - dust
        _need(change, "El cambio")
        if dust < 1:
            raise ValueError("El dust tiene que ser positivo.")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [_out(owner, dust, _nft("none", commit), genesis_from=0), _out("change", change)],
        ), note

    if slug == "bch-overfunded-token-utxo":
        tok = int(params.get("token_sats") or 100_000_000)
        change = inp - fee - tok
        _need(tok, "La salida token")
        _need(change, "El cambio")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [_out(owner, tok, _ft(_ft_amount(params, 1)), genesis_from=0), _out("change", change)],
        ), note

    if slug == "maximum-commitment-size-40-bytes":
        raw = (commit or "aa").encode() if not all(c in "0123456789abcdefABCDEF" for c in (commit or "")) or len(commit or "") % 2 else bytes.fromhex(commit)
        if len(raw) > 40:
            raw = raw[:40]
        raw = raw.ljust(40, b"\x11")
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [_out(owner, out, _nft("none", raw.hex()), genesis_from=0)],
        ), note

    if slug == "maximum-ft-amount-2-63-1":
        amt = _ft_amount(params, 9223372036854775807)
        out = inp - fee
        _need(out, "La salida")
        return _base(
            scenario, params,
            [_genesis("A", "alice", inp)],
            [_out(owner, out, _ft(amt), genesis_from=0)],
        ), note

    if slug == "massive-consolidation-100-ft-inputs":
        amt = _ft_amount(params, 1)
        out = n * inp - fee
        _need(out, "La salida")
        existing = [_existing(f"T{i}", inp, _ft(amt), group="pile") for i in range(n)]
        inputs = [_token_in(f"T{i}") for i in range(n)]
        return _base(scenario, params, inputs, [_out(owner, out, _from("T0", _ft(amt * n)))], existing), note

    if slug == "mass-distribution-airdrop-100-ft-outputs":
        amt = _ft_amount(params, max(n, 100))
        if amt < n:
            raise ValueError("Hacen falta al menos tantos FT como salidas.")
        if inp - fee < 546 * n:
            raise ValueError(f"Hacen falta al menos {546 * n + fee} sats de entrada.")
        share_ft, rem_ft = divmod(amt, n)
        share_s, rem_s = divmod(inp - fee, n)
        outputs = []
        for i in range(n):
            outputs.append(_out(
                OWNERS[i % len(OWNERS)],
                share_s + (rem_s if i == n - 1 else 0),
                _from("T", _ft(share_ft + (rem_ft if i == n - 1 else 0))),
            ))
        return _base(scenario, params, [_token_in("T")], outputs, [_existing("T", inp, _ft(amt))]), note

    if slug == "multi-token-mesh-transaction":
        n_nft = int(params.get("n_nft") or 5)
        utxo = inp
        existing = [_existing(f"F{i}", utxo, _ft(10)) for i in range(n)]
        existing += [_existing(f"N{i}", utxo, _nft("none", f"{i:02x}")) for i in range(n_nft)]
        inputs = [_token_in(row["key"]) for row in existing]
        outputs = []
        for i in range(n):
            outputs.append(_out(OWNERS[i % 3], utxo - 400, _from(f"F{i}", _ft(10))))
        for i in range(n_nft):
            outputs.append(_out(OWNERS[i % 3], utxo - 400, _from(f"N{i}", _nft("none", f"{i:02x}"))))
        spent = utxo * (n + n_nft)
        used = sum(o["sats"] for o in outputs)
        change = spent - fee - used
        if change < 0:
            raise ValueError("Sube los sats de entrada o baja N.")
        if change >= 546:
            outputs.append(_out("change", change))
        else:
            outputs[-1]["sats"] += change
        return _base(scenario, params, inputs, outputs, existing), note

    if slug == "mega-exotic-all-in-one-transaction":
        data = params.get("op_return_hex") or "6d656761"
        utxo = 20_000
        gen = inp
        existing = [
            _existing("B", utxo, _nft("minting", "")),
            _existing("C", utxo, _ft(1000)),
            _existing("I", utxo, _nft("none", "ii", 50)),
            _existing("D", utxo, _ft(100)),
            _existing("E", utxo, _nft("mutable", "old")),
        ]
        inputs = [
            _genesis("A", "alice", gen),
            _token_in("B"), _token_in("C"), _token_in("I"), _token_in("D"), _token_in("E"),
        ]
        outputs = [
            _out("bob", 2_000, _nft("minting", "a1"), genesis_from=0),
            _out("alice", 2_000, _from("B", _nft("minting", ""))),
            _out("carol", 2_000, _from("B", _nft("none", "minted"))),
            _out(owner, 8_000, _from("C", _ft(1000))),
            _out("dave", 8_000, _from("I", _nft("none", "ii", 50))),
            _out("bob", 2_000, _from("D", _ft(50))),
            _out("carol", 2_000, _from("E", _nft("mutable", "new"))),
            _out("bob", 0, script="op_return", data_hex=data),
        ]
        spent = gen + utxo * 5
        used = sum(o["sats"] for o in outputs)
        change = spent - fee - used
        _need(change, "El cambio")
        outputs.append(_out("change", change))
        return _base(scenario, params, inputs, outputs, existing), note

    # Negatives fall through to a small valid shape plus a mutation flag.
    return _compile_negative(scenario, params, slug, owner, inp, fee, cap, commit), ""


def _compile_negative(scenario: dict, params: dict, slug: str, owner: str, inp: int, fee: int, cap: str, commit: str) -> tuple[dict, str]:
    out = max(546, inp - fee)
    if out + fee > inp:
        out = inp - fee
    _need(out, "La salida") if out >= 546 else None
    simple_in = [_bch("A", "alice", inp, 1)]
    simple_out = [_out(owner, inp - fee if inp - fee >= 546 else inp)]
    if simple_out[0]["sats"] > inp:
        raise ValueError("Comisión negativa.")
    flags: dict[str, Any] = {}
    note = ""
    if slug == "invalid-psbt-magic":
        flags["bad_magic"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "truncated-psbt-map":
        flags["truncate"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "missing-unsigned-transaction":
        flags["omit_unsigned"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "mismatched-section-counts":
        flags["bad_counts"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "ambiguous-duplicate-input-context":
        flags["duplicate_utxo"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "missing-input-sighash":
        params = dict(params)
        params["emit_sighash"] = False
        note = "Sin PSBT_IN_SIGHASH_TYPE. SeedCash, si llega a firmar, usa 0x41 por defecto."
    elif slug == "unsupported-or-non-forkid-sighash":
        params = dict(params)
        params["sighash"] = "0x01"
        params["emit_sighash"] = True
        note = "Sighash ALL sin FORKID. SeedCash debe negarse a firmar."
    elif slug == "mixed-input-sighashes":
        simple_in = [_bch("A", "alice", inp, 1), _bch("B", "alice", inp, 1)]
        total = inp * 2 - fee
        simple_out = [_out(owner, total)]
        flags["sighashes"] = ["ALL|FORKID", "ALL|FORKID|UTXOS"]
        note = "La primera entrada pide 0x41 y la segunda 0x61."
    elif slug == "missing-key-origin":
        flags["omit_bip32"] = True
    elif slug == "wrong-key-origin-fingerprint":
        flags["wrong_fingerprint"] = True
    elif slug == "parent-transaction-hash-mismatch":
        flags["parent_mismatch"] = True
    elif slug == "parent-output-index-out-of-range":
        flags["vout_oob"] = True
    elif slug == "token-input-without-complete-parent":
        simple_in = [_token_in("T")]
        simple_out = [_out(owner, inp - fee, _from("T", _ft(5)))]
        flags["existing"] = [_existing("T", inp, _ft(5))]
        flags["omit_utxo"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "token-state-parent-mismatch":
        simple_in = [_token_in("T")]
        simple_out = [_out(owner, inp - fee, _from("T", _ft(5)))]
        flags["existing"] = [_existing("T", inp, _ft(5))]
        flags["tamper_0x36_amount"] = 1
        flags["expected_psbt"] = "invalid"
    elif slug == "malformed-token-prefix":
        simple_in = [_genesis("A", "alice", inp)]
        simple_out = [_out(owner, inp - fee, script="p2pkh")]
        simple_out[0]["inject"] = "reserved"
        flags["expected_consensus"] = "invalid"
    elif slug == "oversized-nft-commitment":
        simple_in = [_genesis("A", "alice", inp)]
        simple_out = [_out(owner, inp - fee, _nft("none", "ab" * 21), genesis_from=0)]
        flags["expected_consensus"] = "invalid"
    elif slug == "fungible-amount-overflow":
        simple_in = [_genesis("A", "alice", inp)]
        simple_out = [_out(owner, inp - fee, genesis_from=0)]
        simple_out[0]["inject"] = "amount_max_plus"
        flags["expected_consensus"] = "invalid"
        note = "El prefijo lleva amount 2^63. El encoder de prefijo válido no deja pasar ese número; el caso usa el inyector."
    elif slug == "fungible-output-exceeds-input":
        simple_in = [_token_in("T")]
        simple_out = [_out(owner, inp - fee, _from("T", _ft(11)))]
        flags["existing"] = [_existing("T", inp, _ft(10))]
        flags["expected_consensus"] = "invalid"
    elif slug == "duplicated-minting-authority":
        simple_in = [_token_in("M")]
        half = max(546, (inp - fee) // 2)
        simple_out = [
            _out(owner, half, _from("M", _nft("minting", ""))),
            _out("carol", inp - fee - half, _from("M", _nft("minting", "x"))),
        ]
        flags["existing"] = [_existing("M", inp, _nft("minting", ""))]
        flags["expected_consensus"] = "invalid"
    elif slug == "unapproved-implicit-token-burn":
        simple_in = [_token_in("T")]
        simple_out = [_out(owner, inp - fee)]
        flags["existing"] = [_existing("T", inp, _ft(10))]
        flags["expected_consensus"] = "valid"
        note = "Consenso válido, pero quema FT sin decirlo. La cartera debería frenarlo."
    elif slug == "returned-psbt-unsigned-transaction-changed":
        flags["sign_state"] = "signed"
        flags["tamper_unsigned"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "returned-psbt-wrong-signature":
        flags["sign_state"] = "signed"
        flags["tamper_signature"] = True
        flags["expected_psbt"] = "invalid"
    elif slug == "incomplete-multisig-return":
        redeem = _multisig([_pubkey("alice"), _pubkey("bob"), _pubkey("carol")])
        simple_in = [_bch("A", "alice", inp, 1, script="p2sh20", redeem_hex=redeem)]
        note = "PSBT 2-de-3 sin las dos firmas. No está listo para difundir."
    elif slug == "signer-returns-no-signatures":
        note = "El UR es el PSBT sin firmas, que es lo que devolvería un firmante que no firma."
    elif slug == "network-mismatch":
        note = "Un PSBT BCH no lleva un byte de red. Este UR es el de laboratorio; la cartera tiene que saber que no es mainnet."
    elif slug == "invalid-ur-transport-payload":
        note = "El parámetro ur_break altera el transporte, no la transacción."
    else:
        note = "No hay una plantilla específica; se muestra un P2PKH de control."

    existing = flags.pop("existing", None)
    cfg = _base(scenario, params, simple_in, simple_out, existing, **{k: v for k, v in flags.items() if k in {
        "expected_consensus", "expected_psbt", "sign_state", "locktime",
    }})
    for key, value in flags.items():
        if key not in cfg:
            cfg[key] = value
    return cfg, note
