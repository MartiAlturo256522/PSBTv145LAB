"""BCH sighash combinatorial intents. Unusual combinations are generated, then classified."""

from __future__ import annotations

from ctlab.lab.intent import InputIntent, OutputIntent, TransactionIntent

SIGHASHES = (
    "ALL|FORKID",
    "NONE|FORKID",
    "SINGLE|FORKID",
    "ALL|FORKID|ANYONECANPAY",
    "NONE|FORKID|ANYONECANPAY",
    "SINGLE|FORKID|ANYONECANPAY",
    "ALL|FORKID|UTXOS",
)


def sighash_intents(seed: int = 0) -> list[TransactionIntent]:
    out: list[TransactionIntent] = []
    for i, sh in enumerate(SIGHASHES):
        out.append(
            TransactionIntent(
                id=f"SIGHASH-{sh.replace('|', '-')}",
                seed=seed + i,
                mode="NORMAL",
                sighash=sh,
                description=f"1/1 P2PKH with {sh}",
                inputs=[InputIntent(kind="bch", key="A", owner="alice", sats=50_000)],
                outputs=[OutputIntent(owner="bob", sats=48_000, role="payment", script="p2pkh")],
            )
        )
    return out
