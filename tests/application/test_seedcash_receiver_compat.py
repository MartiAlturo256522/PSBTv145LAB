"""LAB QR frames through the receiver's actual QR and parser code paths.

Snapshots retain the failing SeedCash code so regressions run without device
hardware or optional wallet libraries. Only the helper import namespace changes.
"""
from pathlib import Path
import sys
import types

import pytest
from application.psbt_service import validate_and_generate
from core.psbt.codec import decode_psbt
from helpers.ur_service import encode_ur
from helpers.ur2.ur import UR
from helpers.ur2.ur_encoder import UREncoder
from tools.seedcash_compat import patch_parser, patch_decode_qr

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/seedcash_receiver"


def load_source(name, source):
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(source, name, "exec"), module.__dict__)
    finally:
        del sys.modules[name]
    return module


def receiver(patched=True):
    parser_source = (FIXTURES / "parser_snapshot.py").read_text()
    qr_source = (FIXTURES / "qr_snapshot.py").read_text()
    if patched:
        parser_source = patch_parser(parser_source)
        qr_source = patch_decode_qr(qr_source)
    qr_source = qr_source.replace("from seedcash.helpers.ur2.crypto_psbt", "from helpers.ur2.crypto_psbt")
    return load_source("receiver_parser", parser_source), load_source("receiver_qr", qr_source)


def test_current_receiver_reproduces_reported_version_error():
    parser, _ = receiver(patched=False)
    raw = bytes.fromhex(validate_and_generate(catalog_id="IO-1-1")["psbt_hex"])
    with pytest.raises(ValueError, match="invalid PSBT version"):
        parser.parse_psbt(raw)


def test_current_receiver_forwards_cbor_instead_of_psbt():
    _, qr = receiver(patched=False)
    raw = validate_and_generate(catalog_id="IO-1-1")["psbt_hex"]
    decoder = qr.DecodeQR()
    for part in encode_ur(raw)["parts"]:
        decoder.add_data(part)
    assert not bytes(decoder.get_psbt()).startswith(b"psbt\xff")


@pytest.mark.parametrize("ident", ["IO-1-1", "IO-1-2", "IO-2-1", "IO-2-2", "IO-2-3", "IO-3-2", "GEN-01", "GEN-04", "GEN-05"])
@pytest.mark.parametrize("density", ["Low", "Maximum"])
def test_patched_receiver_qr_to_v145_parser(ident, density):
    parser, qr = receiver()
    raw = bytes.fromhex(validate_and_generate(catalog_id=ident)["psbt_hex"])
    decoder = qr.DecodeQR()
    for part in encode_ur(raw.hex(), density)["parts"]:
        decoder.add_data(part)
    received = bytes(decoder.get_psbt())
    assert received == raw
    parsed = parser.parse_psbt(received)
    lab = decode_psbt(raw)
    assert parsed["psbt_version"] == 145
    assert parsed["global"] == lab.global_pairs
    assert parsed["inputs"] == lab.inputs
    assert parsed["outputs"] == lab.outputs


def test_patched_receiver_still_accepts_legacy_raw_ur():
    parser, qr = receiver()
    raw = bytes.fromhex(validate_and_generate(catalog_id="IO-1-1")["psbt_hex"])
    encoder = UREncoder(UR("crypto-psbt", raw), 200)
    decoder = qr.DecodeQR()
    for _ in range(encoder.fountain_encoder.seq_len()):
        decoder.add_data(encoder.next_part())
    assert bytes(decoder.get_psbt()) == raw
    assert parser.parse_psbt(bytes(decoder.get_psbt()))["psbt_version"] == 145


def test_v145_separator_is_required():
    parser, _ = receiver()
    raw = bytes.fromhex(validate_and_generate(catalog_id="IO-1-1")["psbt_hex"])
    parsed = parser.parse_psbt(raw)
    offset = parsed["input_ends"]
    assert raw[offset] == 0
    with pytest.raises(ValueError, match="missing v145 input separator"):
        parser.parse_psbt(raw[:offset] + raw[offset + 1:])
