"""Reviewable compatibility patch for the external Python SeedCash receiver."""
from __future__ import annotations

from pathlib import Path


def _replace_once(source: str, old: str, new: str) -> str:
    if new in source:
        return source
    if source.count(old) != 1:
        raise ValueError("SeedCash source changed; expected patch location was not unique")
    return source.replace(old, new, 1)


def patch_parser(source: str) -> str:
    source = _replace_once(source,
        '''            psbt_version, version_pos = read_varint(value, 0)
            if version_pos != len(value):
                raise ValueError("invalid PSBT version")''',
        '''            # PSBT_GLOBAL_VERSION is a uint32 little-endian, not CompactSize.
            if len(value) != 4:
                raise ValueError("invalid PSBT version")
            psbt_version = int.from_bytes(value, "little")''')
    return _replace_once(source,
        '''    outputs = []
    for _ in range(output_count):''',
        '''    # Paytaca v145 has one extra separator after the complete input map set.
    if psbt_version == 145:
        if pos >= len(buf) or buf[pos] != 0:
            raise ValueError("missing v145 input separator")
        pos += 1

    outputs = []
    for _ in range(output_count):''')


def patch_decode_qr(source: str) -> str:
    return _replace_once(source,
        '''                return self.decoder.result_message().cbor''',
        '''                from seedcash.helpers.ur2.crypto_psbt import unwrap_psbt_cbor

                psbt = unwrap_psbt_cbor(self.decoder.result_message().cbor)
                if not psbt.startswith(b"psbt\\xff"):
                    raise ValueError("invalid PSBT magic")
                return psbt''')


def patch_crc(source: str) -> str:
    return _replace_once(source,
        "return n.to_bytes((bit_length(n) + 7) // 8, 'big')",
        "return n.to_bytes(4, 'big')")


def patch_bytewords(source: str) -> str:
    return _replace_once(source,
        "    # if checksum != body_checksum:\n    #     raise ValueError('Invalid Bytewords.')",
        "    if checksum != body_checksum:\n        raise ValueError('Invalid Bytewords.')")


def compatibility_files(source_root: Path) -> dict[Path, str]:
    """Build the complete patch without changing the receiver's files."""
    transforms = {
        "seedcash/models/psbt_parser.py": patch_parser,
        "seedcash/models/decode_qr.py": patch_decode_qr,
        "seedcash/helpers/ur2/crc32.py": patch_crc,
        "seedcash/helpers/ur2/bytewords.py": patch_bytewords,
    }
    result = {Path(name): transform((source_root / name).read_text())
              for name, transform in transforms.items()}
    helper = Path(__file__).resolve().parents[1] / "src/helpers/ur2/crypto_psbt.py"
    result[Path("seedcash/helpers/ur2/crypto_psbt.py")] = helper.read_text()
    return result
