from ctlab.cashtokens.consensus import validate_transaction_tokens
from ctlab.cashtokens.prefix import Token, TokenNft
from ctlab.protocol.hashes import double_sha256


def _cat(label: bytes) -> tuple[bytes, str]:
    h = double_sha256(label)
    return h, h[::-1].hex()


def test_genesis_ft_ok():
    wire, display = _cat(b"parentA")
    r = validate_transaction_tokens(
        [{"prev_txid": wire, "prev_index": 0, "token": None}],
        [{"token": Token(category=display, amount=100)}],
    )
    assert r.ok


def test_ft_overspend():
    wire, display = _cat(b"parentB")
    r = validate_transaction_tokens(
        [{"prev_txid": wire, "prev_index": 1, "token": Token(category=display, amount=10)}],
        [{"token": Token(category=display, amount=11)}],
    )
    assert not r.ok
    assert r.code == "ft_overspend"


def test_clone_immutable():
    wire, display = _cat(b"parentC")
    nft = TokenNft("none", b"id")
    r = validate_transaction_tokens(
        [{"prev_txid": wire, "prev_index": 1, "token": Token(category=display, nft=nft)}],
        [
            {"token": Token(category=display, nft=nft)},
            {"token": Token(category=display, nft=nft)},
        ],
    )
    assert not r.ok


def test_mint_from_baton():
    wire, display = _cat(b"parentD")
    r = validate_transaction_tokens(
        [{"prev_txid": wire, "prev_index": 1, "token": Token(category=display, nft=TokenNft("minting", b""))}],
        [
            {"token": Token(category=display, nft=TokenNft("minting", b""))},
            {"token": Token(category=display, nft=TokenNft("none", b"a"))},
            {"token": Token(category=display, nft=TokenNft("none", b"b"))},
        ],
    )
    assert r.ok


def test_sighash_single_zeros_hashsequence():
    from ctlab.signing.sighash import SIGHASH_ALL, SIGHASH_FORKID, SIGHASH_SINGLE, sighash_bch
    from ctlab.transactions.serialize import Transaction, TxIn, TxOut, p2pkh_script

    script = p2pkh_script(b"\x11" * 20)
    spent = TxOut(value_sats=1000, locking_bytecode=script)
    tx = Transaction(
        inputs=[
            TxIn(prev_txid=b"\xaa" * 32, prev_index=1, sequence=1),
            TxIn(prev_txid=b"\xbb" * 32, prev_index=1, sequence=2),
        ],
        outputs=[
            TxOut(value_sats=400, locking_bytecode=script),
            TxOut(value_sats=400, locking_bytecode=script),
        ],
    )
    d_all, pre_all = sighash_bch(tx, 0, script, SIGHASH_ALL | SIGHASH_FORKID, [spent, spent])
    d_single, pre_single = sighash_bch(tx, 0, script, SIGHASH_SINGLE | SIGHASH_FORKID, [spent, spent])
    assert d_all != d_single
    # hashSequence occupies bytes [36:68] after version+hashPrevouts when UTXOS unset
    assert pre_single[36:68] == b"\x00" * 32
    assert pre_all[36:68] != b"\x00" * 32


def test_mutable_to_minting_invalid():
    wire, display = _cat(b"parentE")
    r = validate_transaction_tokens(
        [{"prev_txid": wire, "prev_index": 1, "token": Token(category=display, nft=TokenNft("mutable", b"x"))}],
        [{"token": Token(category=display, nft=TokenNft("minting", b"x"))}],
    )
    assert not r.ok
    assert r.code == "unsubstantiated_minting"
