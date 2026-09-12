from ctlab.cashtokens.prefix import Token, TokenNft, decode_token_prefix, encode_token_prefix
from ctlab.psbt.codec import decode_psbt
from ctlab.vectors.catalog import build_catalog
from ctlab.vectors.generator import generate_vector


def test_prefix_roundtrip_grid():
    cat = "12" * 32
    for cap in ("none", "mutable", "minting"):
        for commit in (b"", b"\x01", b"\xcc" * 40):
            for amt in (0, 1, 252, 253, 65536):
                if cap is None and amt == 0:
                    continue
                t = Token(category=cat, amount=amt, nft=TokenNft(cap, commit))
                p = encode_token_prefix(t)
                d, pref, rest = decode_token_prefix(p)
                assert rest == b""
                assert pref == p
                assert d.amount == amt
                assert d.nft.capability == cap
                assert d.nft.commitment == commit
                assert d.category == cat


def test_psbt_roundtrip_valid_vectors():
    catalog = [s for s in build_catalog() if s["expected_psbt"] == "valid" and s["id"].startswith("GEN-0")]
    for sc in catalog[:8]:
        v = generate_vector(sc, dialect="bip174-v0", sign_state="unsigned")
        if not v.get("psbt_hex"):
            continue
        decoded = decode_psbt(bytes.fromhex(v["psbt_hex"]))
        assert decoded.unsigned_tx is not None
        assert decoded.serialize() == bytes.fromhex(v["psbt_hex"])


def test_psbt_roundtrip_paytaca_145():
    catalog = [s for s in build_catalog() if "paytaca-145" in (s.get("dialects") or []) and s["expected_psbt"] == "valid"]
    for sc in catalog:
        v = generate_vector(sc, dialect="paytaca-145", sign_state="unsigned")
        if not v.get("psbt_hex"):
            continue
        raw = bytes.fromhex(v["psbt_hex"])
        decoded = decode_psbt(raw)
        assert decoded.version == 145
        assert decoded.serialize() == raw
