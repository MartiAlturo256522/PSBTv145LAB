"""Synthetic Paytaca-v145 campaign intents.

Materializes through ``ctlab.engine.generate`` (dialect paytaca-145 only).
Does not patch SeedCash. Hybrid NFT+FT always sets both amount and capability.
"""

from __future__ import annotations

import random
from typing import Any

from ctlab.engine import generate as engine_generate
from ctlab.lab import LAB_CAMPAIGN_VERSION
from ctlab.lab.intent import InputIntent, OutputIntent, TokenIntent, TransactionIntent
from ctlab.lab.maps import maps_vs_unsigned
from ctlab.protocol.hashes import sha256

M1_CARDINALITIES = ((1, 1), (1, 2), (2, 1), (2, 2), (2, 3), (3, 2), (6, 6))
MODES = ("NORMAL", "ADVERSARIAL", "CASH_TOKENS", "WYSIWYS", "MONSTER", "EXHAUSTIVE")
PAYEES = ("bob", "carol", "dave")
INPUT_SATS = 50_000
FEE_SATS = 2_000
DUST_SATS = 546


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _payee(i: int) -> str:
    return PAYEES[i % len(PAYEES)]


def _split_sats(total: int, n: int, min_sats: int = DUST_SATS) -> list[int]:
    if n <= 0:
        return []
    base, rem = divmod(total, n)
    amounts = [base] * n
    amounts[-1] += rem
    for i, amt in enumerate(amounts):
        if amt < min_sats:
            amounts[i] = min_sats
    return amounts


def _value_indexes(outputs: list[OutputIntent]) -> list[int]:
    return [
        i
        for i, o in enumerate(outputs)
        if o.role != "op_return" and o.script != "op_return"
    ]


def _fill_sats(inputs: list[InputIntent], outputs: list[OutputIntent]) -> None:
    remaining = sum(inp.sats for inp in inputs) - FEE_SATS
    idxs = _value_indexes(outputs)
    amounts = _split_sats(remaining, len(idxs))
    for i, amt in zip(idxs, amounts):
        outputs[i].sats = amt
    for i, o in enumerate(outputs):
        if i not in idxs:
            o.sats = 0


def _bch_inputs(n_in: int) -> list[InputIntent]:
    return [
        InputIntent(kind="bch", key=f"I{i}", owner="alice", sats=INPUT_SATS)
        for i in range(n_in)
    ]


def _op_return_out() -> OutputIntent:
    return OutputIntent(owner="bob", sats=0, role="op_return", script="op_return")


def _bch_outputs(
    n_out: int,
    *,
    payment_script: str = "p2pkh",
    opreturn_index: int | None = None,
    change_index: int | None = None,
) -> list[OutputIntent]:
    outs: list[OutputIntent] = []
    pay_i = 0
    for j in range(n_out):
        if opreturn_index is not None and j == opreturn_index:
            outs.append(_op_return_out())
            continue
        if change_index is not None and j == change_index:
            outs.append(OutputIntent(owner="alice", sats=0, role="change", script="p2pkh"))
            continue
        script = payment_script if pay_i == 0 else "p2pkh"
        outs.append(OutputIntent(owner=_payee(pay_i), sats=0, role="payment", script=script))
        pay_i += 1
    return outs


def _intent(
    id: str,
    inputs: list[InputIntent],
    outputs: list[OutputIntent],
    *,
    seed: int = 0,
    mode: str = "NORMAL",
    existing: list[dict[str, Any]] | None = None,
    description: str = "",
) -> TransactionIntent:
    _fill_sats(inputs, outputs)
    return TransactionIntent(
        id=id,
        seed=seed,
        inputs=inputs,
        outputs=outputs,
        existing=list(existing or []),
        mode=mode,
        description=description,
    )


def m1_intents(seed: int = 0) -> list[TransactionIntent]:
    """Fixed BCH cardinality grid. Ids like M1-2-3-p2pkh-paychange."""
    out: list[TransactionIntent] = []
    idx = 0
    for n_in, n_out in M1_CARDINALITIES:
        # P2PKH: payment only, or payment(s)+change when n_out>=2.
        change_idx = n_out - 1 if n_out >= 2 else None
        tag = "p2pkh-paychange" if change_idx is not None else "p2pkh"
        out.append(
            _intent(
                f"M1-{n_in}-{n_out}-{tag}",
                _bch_inputs(n_in),
                _bch_outputs(n_out, payment_script="p2pkh", change_index=change_idx),
                seed=seed + idx,
                mode="NORMAL",
                description="BCH P2PKH payment" + ("+change" if change_idx is not None else " only"),
            )
        )
        idx += 1

        # P2SH20 on the first payment output.
        tag = "p2sh20-paychange" if change_idx is not None else "p2sh20"
        out.append(
            _intent(
                f"M1-{n_in}-{n_out}-{tag}",
                _bch_inputs(n_in),
                _bch_outputs(n_out, payment_script="p2sh20", change_index=change_idx),
                seed=seed + idx,
                mode="NORMAL",
                description="P2SH20 payment",
            )
        )
        idx += 1

        # OP_RETURN first, then payment; change only when n_out>=3.
        opreturn_change = n_out - 1 if n_out >= 3 else None
        tag = "opreturn-paychange" if opreturn_change is not None else "opreturn"
        out.append(
            _intent(
                f"M1-{n_in}-{n_out}-{tag}",
                _bch_inputs(n_in),
                _bch_outputs(n_out, opreturn_index=0, change_index=opreturn_change),
                seed=seed + idx,
                mode="NORMAL",
                description="OP_RETURN first then payment",
            )
        )
        idx += 1
    return out


def _existing_row(key: str, token: TokenIntent, *, owner: str = "alice", sats: int = INPUT_SATS, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": key,
        "owner": owner,
        "sats": sats,
        "token": token.to_engine_token(),
    }
    row.update(extra)
    return row


def m2_token_intents(seed: int = 0) -> list[TransactionIntent]:
    """Minimum CashTokens shapes: genesis FT/NFT/hybrid, transfer, mint, burn, split, mixed."""
    out: list[TransactionIntent] = []

    def add(intent: TransactionIntent) -> None:
        intent.seed = seed + len(out)
        intent.mode = "CASH_TOKENS"
        out.append(intent)

    # Genesis FT.
    add(
        _intent(
            "M2-genesis-ft",
            [InputIntent(kind="genesis_parent", key="GP", owner="alice", sats=INPUT_SATS)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="genesis",
                    token=TokenIntent(amount=1_000_000, genesis=True),
                    genesis_from=0,
                )
            ],
            description="genesis FT amount=1000000",
        )
    )

    # Genesis NFT immutable commitment=cafebabe.
    add(
        _intent(
            "M2-genesis-nft-immutable",
            [InputIntent(kind="genesis_parent", key="GP", owner="alice", sats=INPUT_SATS)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="genesis",
                    token=TokenIntent(
                        nft_capability="none",
                        commitment=bytes.fromhex("cafebabe"),
                        genesis=True,
                    ),
                    genesis_from=0,
                )
            ],
            description="genesis NFT immutable commitment=cafebabe",
        )
    )

    # Genesis hybrid minting + FT 5000 (both fields set; never elif).
    add(
        _intent(
            "M2-genesis-hybrid-minting",
            [InputIntent(kind="genesis_parent", key="GP", owner="alice", sats=INPUT_SATS)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="genesis",
                    token=TokenIntent(amount=5000, nft_capability="minting", genesis=True),
                    genesis_from=0,
                )
            ],
            description="genesis hybrid minting+FT 5000",
        )
    )

    # Post-genesis NFT transfer: existing key T, output category_from.
    nft = TokenIntent(nft_capability="none", commitment=bytes.fromhex("cafebabe"))
    add(
        _intent(
            "M2-nft-transfer",
            [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=nft)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(
                        nft_capability="none",
                        commitment=bytes.fromhex("cafebabe"),
                        category_from="T",
                    ),
                )
            ],
            description="post-genesis NFT transfer",
        )
    )

    # Mint 1 extra NFT, keep baton.
    baton = TokenIntent(nft_capability="minting")
    add(
        _intent(
            "M2-mint-keep-baton",
            [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=baton)],
            [
                OutputIntent(
                    owner="alice",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(nft_capability="minting", category_from="T"),
                ),
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(
                        nft_capability="none",
                        commitment=bytes.fromhex("01"),
                        category_from="T",
                    ),
                ),
            ],
            description="mint 1 extra NFT keep baton",
        )
    )

    # Burn NFT: 2 in 1 out, two NFT keys same category_group.
    n1 = TokenIntent(nft_capability="none", commitment=bytes.fromhex("aa"))
    n2 = TokenIntent(nft_capability="none", commitment=bytes.fromhex("bb"))
    add(
        _intent(
            "M2-burn-nft",
            [
                InputIntent(kind="token", key="N1", owner="alice", sats=INPUT_SATS, token=n1),
                InputIntent(kind="token", key="N2", owner="alice", sats=INPUT_SATS, token=n2),
            ],
            [OutputIntent(owner="bob", sats=0, role="burn")],
            existing=[
                _existing_row("N1", n1, category_group="G"),
                _existing_row("N2", n2, category_group="G"),
            ],
            description="burn two same-category NFTs (2 in 1 out)",
        )
    )

    # FT split across 2 outputs.
    ft = TokenIntent(amount=1_000_000)
    add(
        _intent(
            "M2-ft-split",
            [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=ft)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(amount=400_000, category_from="T"),
                ),
                OutputIntent(
                    owner="alice",
                    sats=0,
                    role="change",
                    token=TokenIntent(amount=600_000, category_from="T"),
                ),
            ],
            description="FT split 2 outputs",
        )
    )

    # Mixed BCH+token: token input + bch input, token out + change.
    mixed_ft = TokenIntent(amount=1_000_000)
    add(
        _intent(
            "M2-mixed-bch-token",
            [
                InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=mixed_ft),
                InputIntent(kind="bch", key="I1", owner="alice", sats=INPUT_SATS),
            ],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(amount=1_000_000, category_from="T"),
                ),
                OutputIntent(owner="alice", sats=0, role="change"),
            ],
            description="mixed BCH+token",
        )
    )
    return out


def _genesis_parent(key: str = "GP") -> InputIntent:
    return InputIntent(kind="genesis_parent", key=key, owner="alice", sats=INPUT_SATS)


def _extra_bch(n_in: int, start: int = 1) -> list[InputIntent]:
    return [
        InputIntent(kind="bch", key=f"I{i}", owner="alice", sats=INPUT_SATS)
        for i in range(start, n_in)
    ]


def _random_genesis_token(rng: random.Random) -> TokenIntent:
    kind = rng.choice(("FT", "NFT", "hybrid"))
    if kind == "FT":
        return TokenIntent(amount=1_000_000, genesis=True)
    if kind == "NFT":
        cap = rng.choice(("none", "mutable", "minting"))
        commit = bytes.fromhex("cafebabe") if cap == "none" else b""
        return TokenIntent(nft_capability=cap, commitment=commit, genesis=True)
    cap = rng.choice(("none", "mutable", "minting"))
    return TokenIntent(amount=5000, nft_capability=cap, commitment=b"", genesis=True)


def _normal_intent(rng: random.Random, index: int, seed: int) -> TransactionIntent:
    n_in = rng.choice(range(1, 7))
    n_out = rng.choice(range(1, 7))
    change_index = n_out - 1 if n_out >= 2 and rng.choice((False, True)) else None
    opreturn_index = None
    if n_out >= 2 and rng.choice((False, True)):
        opreturn_index = rng.randrange(n_out)
        if change_index is not None and opreturn_index == change_index:
            if n_out == 2:
                change_index = None
            else:
                opreturn_index = rng.randrange(n_out - 1)
    return _intent(
        f"CAMP-NORMAL-{index:04d}-{n_in}-{n_out}",
        _bch_inputs(n_in),
        _bch_outputs(n_out, opreturn_index=opreturn_index, change_index=change_index),
        seed=seed + index,
        mode="NORMAL",
        description="random P2PKH cardinality",
    )


def _cash_tokens_intent(rng: random.Random, index: int, seed: int) -> TransactionIntent:
    kind = rng.choice(("genesis", "ft", "nft", "hybrid", "split", "mint", "mixed"))
    n_in = rng.choice(range(1, 7))
    n_out = rng.choice(range(1, 7))
    if kind == "genesis":
        n_in = max(n_in, 1)
        n_out = max(n_out, 1)
        inputs = [_genesis_parent(), *_extra_bch(n_in)]
        tok = _random_genesis_token(rng)
        change = n_out >= 2 and rng.choice((False, True))
        outputs: list[OutputIntent] = [
            OutputIntent(
                owner="bob",
                sats=0,
                role="genesis",
                token=tok,
                genesis_from=0,
            )
        ]
        for j in range(1, n_out):
            if change and j == n_out - 1:
                outputs.append(OutputIntent(owner="alice", sats=0, role="change"))
            else:
                outputs.append(OutputIntent(owner=_payee(j - 1), sats=0, role="payment"))
        return _intent(
            f"CAMP-CASH_TOKENS-{index:04d}-genesis",
            inputs,
            outputs,
            seed=seed + index,
            mode="CASH_TOKENS",
            description="campaign genesis mix",
        )
    if kind == "nft":
        nft = TokenIntent(nft_capability="none", commitment=bytes.fromhex("cafebabe"))
        return _intent(
            f"CAMP-CASH_TOKENS-{index:04d}-nft",
            [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=nft)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(
                        nft_capability="none",
                        commitment=bytes.fromhex("cafebabe"),
                        category_from="T",
                    ),
                )
            ],
            seed=seed + index,
            mode="CASH_TOKENS",
            description="campaign NFT transfer",
        )
    if kind == "hybrid":
        hyb = TokenIntent(amount=5000, nft_capability="none", commitment=bytes.fromhex("01"))
        return _intent(
            f"CAMP-CASH_TOKENS-{index:04d}-hybrid",
            [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=hyb)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(
                        amount=5000,
                        nft_capability="none",
                        commitment=bytes.fromhex("01"),
                        category_from="T",
                    ),
                )
            ],
            seed=seed + index,
            mode="CASH_TOKENS",
            description="campaign hybrid transfer",
        )
    if kind == "split":
        ft = TokenIntent(amount=1_000_000)
        return _intent(
            f"CAMP-CASH_TOKENS-{index:04d}-split",
            [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=ft)],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(amount=400_000, category_from="T"),
                ),
                OutputIntent(
                    owner="alice",
                    sats=0,
                    role="change",
                    token=TokenIntent(amount=600_000, category_from="T"),
                ),
            ],
            seed=seed + index,
            mode="CASH_TOKENS",
            description="campaign FT split",
        )
    if kind == "mint":
        baton = TokenIntent(nft_capability="minting")
        return _intent(
            f"CAMP-CASH_TOKENS-{index:04d}-mint",
            [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=baton)],
            [
                OutputIntent(
                    owner="alice",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(nft_capability="minting", category_from="T"),
                ),
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(
                        nft_capability="none",
                        commitment=bytes.fromhex("01"),
                        category_from="T",
                    ),
                ),
            ],
            seed=seed + index,
            mode="CASH_TOKENS",
            description="campaign mint keep baton",
        )
    if kind == "mixed":
        ft = TokenIntent(amount=1_000_000)
        return _intent(
            f"CAMP-CASH_TOKENS-{index:04d}-mixed",
            [
                InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=ft),
                InputIntent(kind="bch", key="I1", owner="alice", sats=INPUT_SATS),
            ],
            [
                OutputIntent(
                    owner="bob",
                    sats=0,
                    role="token_transfer",
                    token=TokenIntent(amount=1_000_000, category_from="T"),
                ),
                OutputIntent(owner="alice", sats=0, role="change"),
            ],
            seed=seed + index,
            mode="CASH_TOKENS",
            description="campaign mixed BCH+token",
        )
    ft = TokenIntent(amount=1_000_000)
    return _intent(
        f"CAMP-CASH_TOKENS-{index:04d}-ft",
        [InputIntent(kind="token", key="T", owner="alice", sats=INPUT_SATS, token=ft)],
        [
            OutputIntent(
                owner="bob",
                sats=0,
                role="token_transfer",
                token=TokenIntent(amount=1_000_000, category_from="T"),
            )
        ],
        seed=seed + index,
        mode="CASH_TOKENS",
        description="campaign FT transfer",
    )


def _wysiwys_intent(rng: random.Random, index: int, seed: int) -> TransactionIntent:
    kind = rng.choice(("opreturn-first", "change-first", "token-first"))
    n_in = rng.choice(range(1, 7))
    n_out = rng.choice(range(2, 7))
    if kind == "opreturn-first":
        change_index = n_out - 1 if n_out >= 3 else None
        return _intent(
            f"CAMP-WYSIWYS-{index:04d}-opreturn",
            _bch_inputs(n_in),
            _bch_outputs(n_out, opreturn_index=0, change_index=change_index),
            seed=seed + index,
            mode="WYSIWYS",
            description="OP_RETURN at index 0",
        )
    if kind == "change-first":
        return _intent(
            f"CAMP-WYSIWYS-{index:04d}-change",
            _bch_inputs(n_in),
            _bch_outputs(n_out, change_index=0),
            seed=seed + index,
            mode="WYSIWYS",
            description="change first",
        )
    inputs = [_genesis_parent(), *_extra_bch(n_in)]
    tok = _random_genesis_token(rng)
    outputs = [
        OutputIntent(owner="bob", sats=0, role="genesis", token=tok, genesis_from=0)
    ]
    for j in range(1, n_out):
        if j == n_out - 1:
            outputs.append(OutputIntent(owner="alice", sats=0, role="change"))
        else:
            outputs.append(OutputIntent(owner=_payee(j - 1), sats=0, role="payment"))
    return _intent(
        f"CAMP-WYSIWYS-{index:04d}-token",
        inputs,
        outputs,
        seed=seed + index,
        mode="WYSIWYS",
        description="token first",
    )


def _adversarial_intent(rng: random.Random, index: int, seed: int) -> TransactionIntent:
    n_extra = rng.randint(1, 4)
    n_out = 2 + n_extra
    n_in = rng.randint(1, 4)
    inputs = [_genesis_parent(), *_extra_bch(n_in)]
    tok = _random_genesis_token(rng)
    outputs = [
        _op_return_out(),
        OutputIntent(owner="bob", sats=0, role="genesis", token=tok, genesis_from=0),
    ]
    for j in range(2, n_out):
        if j == n_out - 1:
            outputs.append(OutputIntent(owner="alice", sats=0, role="change"))
        else:
            outputs.append(OutputIntent(owner=_payee(j - 2), sats=0, role="payment"))
    return _intent(
        f"CAMP-ADVERSARIAL-{index:04d}-{n_in}-{n_out}",
        inputs,
        outputs,
        seed=seed + index,
        mode="ADVERSARIAL",
        description="OP_RETURN first + token payment; extra outputs",
    )


def _monster_intent(rng: random.Random, index: int, seed: int) -> TransactionIntent:
    n_in = rng.randint(6, 10)
    n_out = rng.randint(6, 10)
    use_token = rng.choice((False, True))
    use_opreturn = rng.choice((False, True))
    p2sh = rng.choice((False, True))
    opreturn_index = 0 if use_opreturn else None
    change_index = n_out - 1
    if use_token:
        inputs: list[InputIntent] = [_genesis_parent(), *_extra_bch(n_in)]
        tok = _random_genesis_token(rng)
        outputs: list[OutputIntent] = []
        pay_i = 0
        token_placed = False
        for j in range(n_out):
            if opreturn_index is not None and j == opreturn_index:
                outputs.append(_op_return_out())
                continue
            if j == change_index:
                outputs.append(OutputIntent(owner="alice", sats=0, role="change"))
                continue
            if not token_placed:
                outputs.append(
                    OutputIntent(
                        owner="bob",
                        sats=0,
                        role="genesis",
                        script="p2sh20" if p2sh else "p2pkh",
                        token=tok,
                        genesis_from=0,
                    )
                )
                token_placed = True
                pay_i += 1
                continue
            outputs.append(
                OutputIntent(owner=_payee(pay_i), sats=0, role="payment", script="p2pkh")
            )
            pay_i += 1
        return _intent(
            f"CAMP-MONSTER-{index:04d}-{n_in}-{n_out}",
            inputs,
            outputs,
            seed=seed + index,
            mode="MONSTER",
            description="6-10 in/out mixed token",
        )
    payment_script = "p2sh20" if p2sh else "p2pkh"
    return _intent(
        f"CAMP-MONSTER-{index:04d}-{n_in}-{n_out}",
        _bch_inputs(n_in),
        _bch_outputs(
            n_out,
            payment_script=payment_script,
            opreturn_index=opreturn_index,
            change_index=change_index,
        ),
        seed=seed + index,
        mode="MONSTER",
        description="6-10 in/out mixed BCH",
    )


def campaign_intents(count: int, seed: int, mode: str) -> list[TransactionIntent]:
    """Deterministic campaign: same seed+count+mode+LAB_CAMPAIGN_VERSION => same ids/configs."""
    mode_u = str(mode).upper()
    if mode_u not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    rng = _rng(seed)
    if mode_u == "EXHAUSTIVE":
        base = m1_intents(seed) + m2_token_intents(seed)
        if count <= 0:
            return []
        out: list[TransactionIntent] = []
        for i in range(count):
            src = base[i % len(base)]
            out.append(
                src.clone(
                    id=f"EXH-{i:04d}-{src.id}",
                    seed=seed + i,
                    mode="EXHAUSTIVE",
                )
            )
        return out
    builders = {
        "NORMAL": _normal_intent,
        "CASH_TOKENS": _cash_tokens_intent,
        "WYSIWYS": _wysiwys_intent,
        "ADVERSARIAL": _adversarial_intent,
        "MONSTER": _monster_intent,
    }
    build = builders[mode_u]
    return [build(rng, i, seed) for i in range(count)]


def materialize(intent: TransactionIntent) -> dict[str, Any]:
    vec = engine_generate(
        intent.to_engine_config(),
        dialect="paytaca-145",
        sign="unsigned",
        seed=intent.seed,
    )
    raw_hex = vec.get("psbt_hex") or ""
    raw = bytes.fromhex(raw_hex) if raw_hex else b""
    vec["intent"] = intent.to_json()
    vec["lab_campaign_version"] = LAB_CAMPAIGN_VERSION
    vec["psbt_sha256"] = sha256(raw).hex()
    vec["maps"] = maps_vs_unsigned(raw) if raw else {}
    return vec
