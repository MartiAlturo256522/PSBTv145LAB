"""Generate local receiver probe results without an external SeedCash checkout."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from application.psbt_service import validate_and_generate
from core.receiver.psbt_parser import PSBTParser
from core.receiver.qr_decoder import DecodeQR, DecodeQRStatus
from helpers.ur_service import encode_ur


def probe():
    rows = []
    for ident in ["IO-1-1", "IO-2-3", "GEN-01", "GEN-04", "GEN-05"]:
        vector = validate_and_generate(catalog_id=ident)
        qr = DecodeQR()
        for part in encode_ur(vector["psbt_hex"])["parts"]:
            if qr.add_data(part) == DecodeQRStatus.COMPLETE:
                break
        received = bytes(qr.get_psbt())
        assert received.hex() == vector["psbt_hex"]
        parser = PSBTParser(received)
        rows.append({"id": ident, "source": "core.receiver", "inputs": parser.num_inputs,
                     "outputs": len(parser.tx.outputs), "fee": parser.fee_amount})
    return rows


if __name__ == "__main__":
    Path(__file__).with_suffix(".json").write_text(json.dumps(probe(), indent=2) + "\n")
