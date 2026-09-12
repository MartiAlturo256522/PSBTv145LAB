"""Deterministic self-contained transaction graphs.

No mainnet. Every previous transaction is synthesized so a PSBT is
self-contained (NON_WITNESS_UTXO can be attached).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ctlab.cashtokens.prefix import Token, TokenNft
from ctlab.fixtures.keys import ACTORS, Actor
from ctlab.protocol.hashes import double_sha256, hash160, sha256
from ctlab.transactions.serialize import Transaction, TxOut, encode_transaction, locking_script, p2pkh_script


def _dummy_prevout(tag: bytes) -> bytes:
    return double_sha256(b"ctlab-prevout|" + tag)


@dataclass
class NamedTx:
    name: str
    tx: Transaction
    raw: bytes
    txid_internal: bytes
    txid_hex: str


@dataclass
class FixtureGraph:
    funding: dict[str, NamedTx] = field(default_factory=dict)
    genesis: dict[str, NamedTx] = field(default_factory=dict)
    extras: dict[str, NamedTx] = field(default_factory=dict)
    token_vouts: dict[str, int] = field(default_factory=dict)
    target: Optional[Transaction] = None
    source_outputs: list[TxOut] = field(default_factory=list)
    prev_txs: list[bytes] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _funding_tx(tag: str, owner: Actor, sats: int = 100_000, seed: int | None = None) -> NamedTx:
    """A synthetic parent whose vout=0 can be a genesis input."""
    tx = Transaction(
        version=2,
        inputs=[
            __import__("ctlab.transactions.serialize", fromlist=["TxIn"]).TxIn(
                prev_txid=_dummy_prevout(tag.encode() + (f"|{seed}".encode() if seed is not None else b"")),
                prev_index=0,
                script_sig=b"\x00",
                sequence=0xFFFFFFFF,
            )
        ],
        outputs=[TxOut(value_sats=sats, locking_bytecode=owner.p2pkh(), token=None)],
        locktime=0,
    )
    raw = encode_transaction(tx)
    return NamedTx(
        name=tag,
        tx=tx,
        raw=raw,
        txid_internal=double_sha256(raw),
        txid_hex=double_sha256(raw)[::-1].hex(),
    )


def _token_from_spec(spec: dict[str, Any], genesis_category: str | None) -> Optional[Token]:
    if not spec:
        return None
    cat = spec.get("category") or genesis_category
    if cat is None:
        return None
    nft = None
    if "nft" in spec and spec["nft"] is not None:
        n = spec["nft"]
        commit = n.get("commitment", "")
        if isinstance(commit, bytes):
            commit_b = commit
        elif not commit:
            commit_b = b""
        elif len(commit) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in commit):
            commit_b = bytes.fromhex(commit)
        else:
            commit_b = commit.encode("utf-8")
        nft = TokenNft(capability=n.get("capability", "none"), commitment=commit_b)
    amount = int(spec.get("amount", 0) or 0)
    if nft is None and amount <= 0:
        return None
    return Token(category=cat, amount=amount, nft=nft)


def _script_for(owner_name: str, script_type: str = "p2pkh") -> bytes:
    if script_type == "op_return":
        return locking_script("op_return", b"ctlab")
    actor = ACTORS[owner_name]
    if script_type == "p2pkh":
        return actor.p2pkh()
    if script_type == "p2sh20":
        redeem = actor.p2pkh()
        return locking_script("p2sh20", hash160(redeem))
    if script_type == "p2sh32":
        redeem = actor.p2pkh()
        return locking_script("p2sh32", sha256(redeem))
    if script_type == "bare":
        # P2PK compressed
        return bytes([33]) + actor.pub + b"\xac"
    return actor.p2pkh()


def _redeem_for(owner_name: str, script_type: str) -> bytes | None:
    if script_type in ("p2sh20", "p2sh32"):
        return ACTORS[owner_name].p2pkh()
    return None


def build_fixture_graph(scenario: dict[str, Any]) -> FixtureGraph:
    """Build funding + optional pre-genesis token UTXOs + target tx.

    Scenario keys:
      inputs: list of {kind, owner, sats, token?, category_key?, script?}
        kind: genesis_parent | token | bch
      outputs: list of {owner, sats, token?, genesis_from?, script?}
      existing: optional list of pre-created token UTXOs
                {key, owner, sats, token: {amount, nft}}
                The category is the funding txid of that key (vout=0 genesis).
    """
    g = FixtureGraph()
    seed = scenario.get("_seed")
    existing = list(scenario.get("existing") or [])
    # Public API: category_group / share_category_with. Internal alias:
    # _same_category_clone means every existing UTXO shares one category.
    grouped: dict[str, list[dict]] = {}
    leftover: list[dict] = []
    if scenario.get("_same_category_clone") and existing:
        grouped["_auto"] = list(existing)
        existing = []
    else:
        by_key = {spec["key"]: spec for spec in existing}
        claimed: set[str] = set()
        for spec in existing:
            gname = spec.get("category_group")
            share = spec.get("share_category_with")
            if share:
                gname = gname or by_key.get(share, {}).get("category_group") or share
            if not gname:
                continue
            bucket = grouped.setdefault(str(gname), [])
            if share and share in by_key and by_key[share]["key"] not in claimed:
                bucket.append(by_key[share])
                claimed.add(share)
            if spec["key"] not in claimed:
                bucket.append(spec)
                claimed.add(spec["key"])
        leftover = [s for s in existing if s["key"] not in claimed]
        existing = leftover
    for spec in existing:
        key = spec["key"]
        owner = ACTORS[spec.get("owner", "alice")]
        fund = _funding_tx(f"fund-{key}", owner, spec.get("parent_sats", 50_000), seed=seed)
        g.funding[key] = fund
        token = _token_from_spec(spec.get("token") or {}, fund.txid_hex)
        # Default: vout=0 dummy BCH so spending the token (vout=1) is NOT a
        # new genesis. GEN-15 sets token_bearing_vout0 to put tokens at vout=0.
        tok_out = TxOut(
            value_sats=spec.get("sats", 10_000),
            locking_bytecode=_script_for(spec.get("owner", "alice"), spec.get("script", "p2pkh")),
            token=token,
        )
        if scenario.get("token_bearing_vout0"):
            dummy = None
        else:
            dummy = TxOut(value_sats=546, locking_bytecode=owner.p2pkh(), token=None)
        gen = Transaction(
            version=2,
            inputs=[
                __import__("ctlab.transactions.serialize", fromlist=["TxIn"]).TxIn(
                    prev_txid=fund.txid_internal,
                    prev_index=0,
                    script_sig=b"\x51",
                    sequence=0xFFFFFFFF,
                    spent_output=fund.tx.outputs[0],
                )
            ],
            outputs=[tok_out] if dummy is None else [dummy, tok_out],
        )
        raw = encode_transaction(gen)
        g.genesis[key] = NamedTx(
            name=key,
            tx=gen,
            raw=raw,
            txid_internal=double_sha256(raw),
            txid_hex=double_sha256(raw)[::-1].hex(),
        )
        g.token_vouts[key] = 0 if dummy is None else 1
    for same_group in grouped.values():
        if len(same_group) < 1:
            continue
        primary = same_group[0]
        owner = ACTORS[primary.get("owner", "alice")]
        fund = _funding_tx(f"fund-{primary['key']}", owner, primary.get("parent_sats", 50_000), seed=seed)
        g.funding[primary["key"]] = fund
        outs = [TxOut(value_sats=546, locking_bytecode=owner.p2pkh(), token=None)]
        for spec in same_group:
            token = _token_from_spec(spec.get("token") or {}, fund.txid_hex)
            outs.append(
                TxOut(
                    value_sats=spec.get("sats", 10_000),
                    locking_bytecode=_script_for(spec.get("owner", "alice"), spec.get("script", "p2pkh")),
                    token=token,
                )
            )
        gen = Transaction(
            version=2,
            inputs=[
                __import__("ctlab.transactions.serialize", fromlist=["TxIn"]).TxIn(
                    prev_txid=fund.txid_internal,
                    prev_index=0,
                    script_sig=b"\x51",
                    sequence=0xFFFFFFFF,
                    spent_output=fund.tx.outputs[0],
                )
            ],
            outputs=outs,
        )
        raw = encode_transaction(gen)
        named = NamedTx(
            name=primary["key"],
            tx=gen,
            raw=raw,
            txid_internal=double_sha256(raw),
            txid_hex=double_sha256(raw)[::-1].hex(),
        )
        for i, spec in enumerate(same_group):
            g.genesis[spec["key"]] = named
            g.token_vouts[spec["key"]] = i + 1

    from ctlab.transactions.serialize import TxIn

    target_ins: list[TxIn] = []
    source_outs: list[TxOut] = []
    prev_txs: list[bytes] = []

    for i, spec in enumerate(scenario.get("inputs") or []):
        kind = spec.get("kind", "bch")
        owner = ACTORS[spec.get("owner", "alice")]
        sats = spec.get("sats", 100_000)
        script_type = spec.get("script", scenario.get("script_type", "p2pkh"))
        if kind == "genesis_parent":
            tag = spec.get("key", f"gp{i}")
            fund = g.funding.get(tag) or _funding_tx(f"gp-{tag}", owner, sats, seed=seed)
            g.funding[tag] = fund
            spent = fund.tx.outputs[0]
            target_ins.append(
                TxIn(
                    prev_txid=fund.txid_internal,
                    prev_index=0,
                    script_sig=b"",
                    sequence=spec.get("sequence", 0xFFFFFFFF),
                    spent_output=spent,
                )
            )
            source_outs.append(spent)
            prev_txs.append(fund.raw)
        elif kind == "token":
            key = spec["key"]
            named = g.genesis[key]
            vout = spec.get("vout", g.token_vouts.get(key, 0))
            spent = named.tx.outputs[vout]
            target_ins.append(
                TxIn(
                    prev_txid=named.txid_internal,
                    prev_index=vout,
                    script_sig=b"",
                    sequence=spec.get("sequence", 0xFFFFFFFF),
                    spent_output=spent,
                )
            )
            source_outs.append(spent)
            prev_txs.append(named.raw)
        else:
            tag = spec.get("key", f"bch{i}")
            fund = _funding_tx(f"bch-{tag}", owner, sats, seed=seed)
            g.extras[tag] = fund
            spent = fund.tx.outputs[0]
            # For non-genesis BCH we spend vout 0 of a dummy; if kind is bch_v1, spend a second output.
            vout = spec.get("vout", 0)
            if vout != 0:
                # rebuild funding with two outputs so vout=1 is not genesis
                extra = TxOut(value_sats=sats, locking_bytecode=owner.p2pkh(), token=None)
                fund.tx.outputs = [TxOut(value_sats=546, locking_bytecode=owner.p2pkh()), extra]
                fund.raw = encode_transaction(fund.tx)
                fund.txid_internal = double_sha256(fund.raw)
                fund.txid_hex = fund.txid_internal[::-1].hex()
                spent = fund.tx.outputs[vout]
            target_ins.append(
                TxIn(
                    prev_txid=fund.txid_internal,
                    prev_index=vout,
                    script_sig=b"",
                    sequence=spec.get("sequence", 0xFFFFFFFF),
                    spent_output=spent,
                )
            )
            source_outs.append(spent)
            prev_txs.append(fund.raw)

    target_outs: list[TxOut] = []
    for spec in scenario.get("outputs") or []:
        owner_name = spec.get("owner", "bob")
        script_type = spec.get("script", scenario.get("script_type", "p2pkh"))
        token_spec = spec.get("token")
        genesis_from = spec.get("genesis_from")
        genesis_cat = None
        if genesis_from is not None:
            genesis_cat = target_ins[genesis_from].prev_txid[::-1].hex()
        token = _token_from_spec(token_spec, genesis_cat) if token_spec is not None else None
        if spec.get("raw_prefix"):
            # Negative encoding: inject raw prefix || locking
            locking = _script_for(owner_name, script_type)
            raw_prefix = bytes.fromhex(spec["raw_prefix"])
            # Store as locking_bytecode already containing prefix; token None
            # The serializer would re-encode token. Use a special path:
            target_outs.append(
                TxOut(
                    value_sats=spec.get("sats", 1000),
                    locking_bytecode=raw_prefix + locking,
                    token=None,
                )
            )
            continue
        target_outs.append(
            TxOut(
                value_sats=spec.get("sats", 1000),
                locking_bytecode=_script_for(owner_name, script_type),
                token=token,
                redeem_script=_redeem_for(owner_name, script_type),
            )
        )

    g.target = Transaction(
        version=scenario.get("tx_version", 2),
        inputs=target_ins,
        outputs=target_outs,
        locktime=scenario.get("locktime", 0),
    )
    g.source_outputs = source_outs
    g.prev_txs = prev_txs
    return g
