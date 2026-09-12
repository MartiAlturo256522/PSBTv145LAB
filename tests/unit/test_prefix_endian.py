"""Non-palindrome category: prove HASH256/P2P reverse on the wire.

CHIP official hex vectors use 0xbb×32 (palindrome) and cannot catch a
missing reverse. This is still an in-repo check against CHIP text, not
live libauth JS.
"""

from pathlib import Path
import sys

from ctlab.cashtokens.prefix import Token, encode_token_prefix

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "audits" / "libauth"))
from chip_prefix import encode_prefix_wire, ui_category_to_wire  # noqa: E402

UI = "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"


def test_non_palindrome_category_reversed_on_wire():
    assert UI != UI[::-1]
    p = encode_token_prefix(Token(category=UI, amount=1))
    wire = bytes.fromhex(UI)[::-1]
    assert p == bytes([0xEF]) + wire + bytes([0x10, 0x01])
    assert p[1:33] != bytes.fromhex(UI)


def test_chip_transcription_matches_lab_encoder():
    lab = encode_token_prefix(Token(category=UI, amount=1))
    chip = encode_prefix_wire(ui_category_to_wire(UI), amount=1)
    assert lab == chip
