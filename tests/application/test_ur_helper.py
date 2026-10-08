import pytest

from core.engine import generate
from helpers.ur_service import decode_ur_parts, encode_ur


@pytest.mark.parametrize("density,maximum,count", [("Low", 30, 9), ("Medium", 65, 4), ("High", 120, 3)])
def test_seedcash_density_fragment_counts(density, maximum, count):
    # 255 PSBT bytes plus the two-byte CBOR bstr header.
    raw = (b"psbt\xff" + bytes(range(250))).hex()
    result = encode_ur(raw, density)
    assert result["maxFragment"] == maximum
    assert result["fragmentsLength"] == count
    assert result["parts"][0].startswith(f"ur:crypto-psbt/1-{count}/")
    assert decode_ur_parts(result["parts"][:count]) == raw


def test_single_part_roundtrip():
    # UR transports bytes independently of the PSBT parser.
    raw = "70736274ff00"
    ur = encode_ur(raw, "Maximum")
    assert ur["single"]
    assert decode_ur_parts(ur["parts"]) == raw


def test_shuffled_multipart_and_duplicate_frames():
    raw = generate("MONSTER-01", dialect="paytaca-145")["psbt_hex"]
    ur = encode_ur(raw, "Low")
    count = ur["fragmentsLength"]
    assert count > 1
    parts = list(reversed(ur["parts"][:count]))
    assert decode_ur_parts([parts[0], *parts]) == raw


def test_incomplete_multipart_is_rejected():
    raw = generate("MONSTER-01", dialect="paytaca-145")["psbt_hex"]
    with pytest.raises(ValueError, match="incomplete"):
        decode_ur_parts(encode_ur(raw, "Low")["parts"][:1])


@pytest.mark.parametrize("parts", [[], ["ur:bytes/abcd"], ["ur:crypto-psbt/invalid"]])
def test_invalid_ur_is_rejected(parts):
    with pytest.raises(ValueError):
        decode_ur_parts(parts)


def test_invalid_psbt_is_rejected():
    with pytest.raises(ValueError, match="magic"):
        encode_ur("00")


def test_bytewords_crc_keeps_leading_zero():
    import zlib
    from helpers.ur2.bytewords import Bytewords, Bytewords_Style_minimal
    from helpers.ur2.crc32 import crc32n

    payload = b"62"
    expected = zlib.crc32(payload).to_bytes(4, "big")
    assert expected[0] == 0
    assert crc32n(payload) == expected
    encoded = Bytewords.encode(Bytewords_Style_minimal, payload)
    assert bytes(Bytewords.decode(Bytewords_Style_minimal, encoded)) == payload


def test_bytewords_rejects_corrupted_checksum():
    from helpers.ur2.bytewords import Bytewords, Bytewords_Style_minimal

    encoded = Bytewords.encode(Bytewords_Style_minimal, b"payload")
    altered = encoded[:-2] + ("ae" if encoded[-2:] != "ae" else "ad")
    with pytest.raises(ValueError, match="Invalid Bytewords"):
        Bytewords.decode(Bytewords_Style_minimal, altered)


@pytest.mark.parametrize("density", ["Low", "Medium", "High", "Maximum"])
def test_scanned_qr_preserves_v145_and_builds_transaction(density):
    from application.psbt_service import validate_and_generate
    from core.receiver.qr_decoder import DecodeQR, DecodeQRStatus
    from core.receiver.psbt_parser import PSBTParser

    raw = bytes.fromhex(validate_and_generate(catalog_id="IO-1-1")["psbt_hex"])
    scanner = DecodeQR()
    for part in encode_ur(raw.hex(), density)["parts"]:
        status = scanner.add_data(part.upper().encode("ascii"))
        if status == DecodeQRStatus.COMPLETE:
            break
    assert status == DecodeQRStatus.COMPLETE
    assert scanner.get_psbt() == raw
    parsed = PSBTParser(scanner.get_psbt())
    assert parsed.parsed["psbt_version"] == 145
    assert dict(parsed.parsed["global"])[b"\xfb"] == b"\x91\x00\x00\x00"
    assert parsed.input_count == parsed.output_count == 1


@pytest.mark.parametrize("version_bytes", [b"\x91", b"\x91\x00\x00", b"\x91\x00\x00\x00\x00"])
def test_compactsize_psbt_version_is_rejected(version_bytes):
    from core.psbt.codec import decode_psbt, PsbtError
    from core.receiver.psbt_parser import parse_psbt

    raw = b"psbt\xff\x01\xfb" + bytes([len(version_bytes)]) + version_bytes + b"\x00"
    with pytest.raises(PsbtError, match="four-byte"):
        decode_psbt(raw)
    with pytest.raises(ValueError, match="invalid PSBT version"):
        parse_psbt(raw)
