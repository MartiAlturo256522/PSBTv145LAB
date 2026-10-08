"""Installed receiver works with no external SeedCash source tree or imports."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from application.psbt_service import validate_and_generate
from core.receiver.psbt_parser import PSBTParser
from core.receiver.qr_decoder import DecodeQR, DecodeQRStatus
from helpers.ur_service import encode_ur


@pytest.mark.parametrize("ident", ["IO-1-1", "IO-1-2", "IO-2-1", "IO-2-2", "IO-2-3", "IO-3-2", "GEN-01", "GEN-04", "GEN-05"])
def test_local_qr_receiver_builds_complete_model(ident):
    vector = validate_and_generate(catalog_id=ident)
    receiver = DecodeQR()
    for part in encode_ur(vector["psbt_hex"], "Low")["parts"]:
        if receiver.add_data(part) == DecodeQRStatus.COMPLETE:
            break
    assert receiver.get_psbt().hex() == vector["psbt_hex"]
    parser = PSBTParser(receiver.get_psbt())
    assert parser.input_count == len(vector["source_utxos"])
    assert parser.output_count == len(vector["outputs"])
    assert parser.fee_amount == sum(row["value_sats"] for row in vector["source_utxos"]) - sum(row["value_sats"] for row in vector["outputs"])


def test_installed_project_with_external_imports_blocked(tmp_path):
    script = '''
import importlib.abc, json, sys
class BlockExternal(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "seedcash" or fullname.startswith("seedcash."):
            raise AssertionError("external project import: " + fullname)
sys.meta_path.insert(0, BlockExternal())
from application.psbt_service import validate_and_generate
from core.receiver.psbt_parser import PSBTParser
from core.receiver.qr_decoder import DecodeQR, DecodeQRStatus
from helpers.ur_service import encode_ur
rows = []
for ident in ["IO-1-1", "IO-2-3", "GEN-01", "GEN-04", "GEN-05"]:
    vector = validate_and_generate(catalog_id=ident)
    receiver = DecodeQR()
    for part in encode_ur(vector["psbt_hex"])["parts"]:
        if receiver.add_data(part) == DecodeQRStatus.COMPLETE:
            break
    assert receiver.get_psbt().hex() == vector["psbt_hex"]
    parser = PSBTParser(receiver.get_psbt())
    rows.append([parser.input_count, parser.output_count])
assert not any(name == "seedcash" or name.startswith("seedcash.") for name in sys.modules)
print(json.dumps(rows))
'''
    result = subprocess.run([sys.executable, "-I", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)) == 5
