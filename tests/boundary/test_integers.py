"""Integer / CompactSize boundaries for amounts and lengths."""

import pytest

from ctlab.cashtokens.prefix import MAX_FT_AMOUNT, Token, TokenNft, TokenPrefixError, encode_token_prefix
from ctlab.protocol.compact_size import CompactSizeError, encode_compact_size


@pytest.mark.parametrize(
    "n,hex_prefix",
    [
        (0, "00"),
        (1, "01"),
        (127, "7f"),
        (128, "80"),
        (252, "fc"),
        (253, "fdfd00"),
        (255, "fdff00"),
        (256, "fd0001"),
        (65535, "fdffff"),
        (65536, "fe00000100"),
    ],
)
def test_compact_size_canonical(n, hex_prefix):
    assert encode_compact_size(n).hex() == hex_prefix


def test_compact_size_rejects_negative():
    with pytest.raises(CompactSizeError):
        encode_compact_size(-1)


def test_ft_amount_max_encodes():
    cat = "aa" + "00" * 30 + "bb"
    p = encode_token_prefix(Token(category=cat, amount=MAX_FT_AMOUNT))
    assert p[0] == 0xEF
    assert p[1:33] == bytes.fromhex(cat)[::-1]


def test_ft_amount_max_plus_rejected():
    cat = "aa" + "00" * 30 + "bb"
    with pytest.raises(TokenPrefixError):
        encode_token_prefix(Token(category=cat, amount=MAX_FT_AMOUNT + 1))


def test_commitment_40_encodes_41_also_encodes():
    cat = "aa" + "00" * 30 + "bb"
    p40 = encode_token_prefix(Token(category=cat, nft=TokenNft("none", b"\xcc" * 40)))
    p41 = encode_token_prefix(Token(category=cat, nft=TokenNft("none", b"\xcc" * 41)))
    assert p40[0] == 0xEF and p41[0] == 0xEF
    # Consensus cap is 40; encode is not the gate (matches libauth).
