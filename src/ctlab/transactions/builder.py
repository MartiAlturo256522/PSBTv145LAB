from __future__ import annotations

from ctlab.cashtokens.prefix import Token
from ctlab.transactions.serialize import Transaction, TxIn, TxOut


class TxBuilder:
    def __init__(self, version: int = 2, locktime: int = 0):
        self.version = version
        self.locktime = locktime
        self.inputs: list[TxIn] = []
        self.outputs: list[TxOut] = []

    def add_input(
        self,
        prev_txid: bytes,
        prev_index: int,
        script_sig: bytes = b"",
        sequence: int = 0xFFFFFFFF,
        spent_output: TxOut | None = None,
    ) -> "TxBuilder":
        self.inputs.append(
            TxIn(
                prev_txid=prev_txid,
                prev_index=prev_index,
                script_sig=script_sig,
                sequence=sequence,
                spent_output=spent_output,
            )
        )
        return self

    def add_output(self, value_sats: int, locking_bytecode: bytes, token: Token | None = None) -> "TxBuilder":
        self.outputs.append(TxOut(value_sats=value_sats, locking_bytecode=locking_bytecode, token=token))
        return self

    def build(self) -> Transaction:
        return Transaction(
            version=self.version,
            inputs=list(self.inputs),
            outputs=list(self.outputs),
            locktime=self.locktime,
        )
