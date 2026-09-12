"""CHIP-2022-02 official token-prefix encoding vectors (category all 0xbb)."""

from ctlab.cashtokens.prefix import Token, TokenNft, TokenPrefixError, decode_token_prefix, encode_token_prefix

CAT = "bb" * 32
CAT_WIRE = "bb" * 32  # palindrome


def _tok(amount=0, cap=None, commit=b""):
    nft = TokenNft(cap, commit) if cap is not None else None
    return Token(category=CAT, amount=amount, nft=nft)


def test_ft_1():
    p = encode_token_prefix(_tok(1))
    assert p.hex() == "ef" + CAT_WIRE + "1001"


def test_ft_252():
    p = encode_token_prefix(_tok(252))
    assert p.hex() == "ef" + CAT_WIRE + "10fc"


def test_ft_253():
    p = encode_token_prefix(_tok(253))
    assert p.hex() == "ef" + CAT_WIRE + "10fdfd00"


def test_immutable_empty():
    p = encode_token_prefix(_tok(0, "none", b""))
    assert p.hex() == "ef" + CAT_WIRE + "20"


def test_immutable_1byte():
    p = encode_token_prefix(_tok(0, "none", b"\xcc"))
    assert p.hex() == "ef" + CAT_WIRE + "6001cc"


def test_hybrid_empty_nft_1ft():
    p = encode_token_prefix(_tok(1, "none", b""))
    assert p.hex() == "ef" + CAT_WIRE + "3001"


def test_roundtrip():
    t = _tok(65536, "mutable", b"\xcc" * 10)
    p = encode_token_prefix(t)
    dec, prefix, rest = decode_token_prefix(p + b"\x76\xa9")
    assert rest == b"\x76\xa9"
    assert dec.amount == 65536
    assert dec.nft.capability == "mutable"
    assert dec.nft.commitment == b"\xcc" * 10
    assert prefix == p


def test_reject_empty():
    raw = bytes.fromhex("ef" + CAT_WIRE + "00")
    try:
        decode_token_prefix(raw)
        assert False
    except TokenPrefixError as e:
        assert e.code == "no_tokens"


def test_reject_amount_zero():
    raw = bytes.fromhex("ef" + CAT_WIRE + "1000")
    try:
        decode_token_prefix(raw)
        assert False
    except TokenPrefixError as e:
        assert e.code == "zero_amount"


def test_reject_reserved():
    raw = bytes.fromhex("ef" + CAT_WIRE + "9001")
    try:
        decode_token_prefix(raw)
        assert False
    except TokenPrefixError as e:
        assert e.code == "reserved_bit"


def test_reject_capability_3():
    raw = bytes.fromhex("ef" + CAT_WIRE + "23")
    try:
        decode_token_prefix(raw)
        assert False
    except TokenPrefixError as e:
        assert e.code == "invalid_capability"


def test_no_prefix():
    tok, p, rest = decode_token_prefix(b"\x76\xa9\x14" + b"\x00" * 20 + b"\x88\xac")
    assert tok is None
    assert rest[0] == 0x76
