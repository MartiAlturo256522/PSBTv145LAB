"""Identity card for a generated lab fixture. Never infers format from a preset name."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from desktop.application.lab_contract import (
    FORMAT_ID,
    FORMAT_LABEL,
    FORMAT_VERSION,
    REFERENCE_COMMIT,
    REFERENCE_LABEL,
    WIRE_DIALECT,
)

LIVE_PAYTACA_BYTE_EQ = frozenset(
    {"GEN-04", "IO-2-3", "SCR-05", "POST-01", "MONSTER-01"}
)


def _script_kind(locking_hex: str, token: dict | None) -> str:
    raw = bytes.fromhex(locking_hex) if locking_hex else b""
    if raw.startswith(b"\xef"):
        rest = _locking_after_token_prefix(raw)
        kind = _script_kind(rest.hex(), None) if rest else "script"
        return kind if kind != "script" else "token+script"
    if raw[:1] == b"\x6a":
        return "op_return"
    if raw.startswith(b"\x76\xa9\x14") and raw.endswith(b"\x88\xac"):
        return "p2pkh"
    if raw.startswith(b"\xa9\x14") and raw.endswith(b"\x87"):
        return "p2sh20"
    if raw.startswith(b"\xaa\x20") and raw.endswith(b"\x87"):
        return "p2sh32"
    return "script"


def _locking_after_token_prefix(raw: bytes) -> bytes:
    if not raw.startswith(b"\xef") or len(raw) < 33:
        return raw
    i = 33  # 0xef + 32 category
    if i >= len(raw):
        return b""
    bitfield = raw[i]
    i += 1
    has_nft = bool(bitfield & 0x20)
    has_amt = bool(bitfield & 0x10)
    if has_nft:
        commit_len = bitfield & 0x0F
        if commit_len == 0x0F:
            # compact size — best-effort skip
            if i >= len(raw):
                return b""
            n = raw[i]
            i += 1
            if n < 0xFD:
                i += n
            else:
                return raw[i:]
        else:
            i += commit_len
    if has_amt:
        if i >= len(raw):
            return b""
        prefix = raw[i]
        i += 1
        if prefix < 0xFD:
            pass  # 1-byte amount already consumed as prefix when < 0xFD... actually amount encoding uses the first byte
            # libauth: 0x00-0xfc is the amount itself (one byte). already consumed.
        elif prefix == 0xFD:
            i += 2
        elif prefix == 0xFE:
            i += 4
        elif prefix == 0xFF:
            i += 8
    return raw[i:]


def _has_tokens(vector: dict[str, Any]) -> bool:
    for row in (vector.get("source_utxos") or []) + (vector.get("outputs") or []):
        if row.get("token"):
            return True
    return False


def _token_ops(vector: dict[str, Any]) -> list[str]:
    sem = vector.get("semantics") or {}
    ops: list[str] = []
    if not _has_tokens(vector):
        return ["none"]
    genesis = sem.get("genesis") or []
    real_genesis = [g for g in genesis if g.get("type") and g.get("type") != "empty"]
    if real_genesis:
        kinds = sorted({g.get("type") or "genesis" for g in real_genesis})
        ops.append("genesis:" + ",".join(kinds))
    if sem.get("mint"):
        ops.append(f"mint:{len(sem['mint'])}")
    if sem.get("transfers"):
        ops.append(f"transfer:{len(sem['transfers'])}")
    if sem.get("burns"):
        ops.append(f"burn:{len(sem['burns'])}")
    if sem.get("mutations"):
        ops.append(f"mutate:{len(sem['mutations'])}")
    return ops or ["cashtokens"]


def _scripts(vector: dict[str, Any]) -> list[str]:
    kinds: list[str] = []
    seen: set[str] = set()
    for o in vector.get("outputs") or []:
        k = _script_kind(o.get("locking_bytecode") or o.get("script_field") or "", o.get("token"))
        if k not in seen:
            seen.add(k)
            kinds.append(k)
    return kinds or ["unknown"]


def _unsigned_present(vector: dict[str, Any]) -> bool:
    hx = vector.get("unsigned_tx_hex") or ""
    if hx:
        return True
    psbt_hex = vector.get("psbt_hex") or ""
    if not psbt_hex:
        return False
    try:
        from ctlab.psbt.codec import PSBT_GLOBAL_UNSIGNED_TX, decode_psbt

        psbt = decode_psbt(bytes.fromhex(psbt_hex))
        return any(k[:1] == bytes([PSBT_GLOBAL_UNSIGNED_TX]) for k, _ in psbt.global_pairs)
    except Exception:
        return False


def _psbt_version(vector: dict[str, Any]) -> Optional[int]:
    hx = vector.get("psbt_hex") or ""
    if not hx:
        return None
    try:
        from ctlab.psbt.codec import decode_psbt

        return decode_psbt(bytes.fromhex(hx)).version
    except Exception:
        return None


def _paytaca_status(vector: dict[str, Any], *, version: Optional[int], psbt_ok: bool) -> tuple[str, str]:
    ident = vector.get("catalog_id") or vector.get("id") or ""
    dialect = vector.get("dialect")
    if dialect != WIRE_DIALECT or version != FORMAT_VERSION or not psbt_ok:
        return "mismatch", "PAYTACA FAIL"
    if ident in LIVE_PAYTACA_BYTE_EQ:
        return "match", "PAYTACA MATCH"
    return "wire", "PAYTACA v145 WIRE"


def _seedcash_status(vector: dict[str, Any], *, unsigned: bool, version: Optional[int]) -> tuple[str, str]:
    magic_ok = (vector.get("psbt_hex") or "").startswith("70736274ff")
    if unsigned and magic_ok and version == FORMAT_VERSION:
        return "parse", "SEEDCASH COMPATIBLE"
    if unsigned and magic_ok:
        return "partial", "SEEDCASH UNSIGNED-TX"
    return "no", "SEEDCASH INCOMPATIBLE"


@dataclass
class FixtureIdentity:
    format: str = FORMAT_LABEL
    format_id: str = FORMAT_ID
    reference: str = REFERENCE_LABEL
    reference_commit: str = REFERENCE_COMMIT
    wire_dialect: str = WIRE_DIALECT
    psbt_version: Optional[int] = None
    unsigned_tx_present: bool = False
    cashtokens: bool = False
    n_in: int = 0
    n_out: int = 0
    scripts: list[str] = field(default_factory=list)
    token_operations: list[str] = field(default_factory=list)
    paytaca_status: str = "unknown"
    paytaca_badge: str = "PAYTACA —"
    seedcash_status: str = "unknown"
    seedcash_badge: str = "SEEDCASH —"
    semantic_valid: bool = False
    semantic_reason: str = ""
    bch_tx_valid: bool = False
    psbt_valid: bool = False
    scenario_id: str = ""
    scenario_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def detail_lines(self) -> list[str]:
        return [
            f"PSBT format = {self.format}",
            f"unsigned transaction present = {'yes' if self.unsigned_tx_present else 'no'}",
            f"CashTokens = {'yes' if self.cashtokens else 'no'}",
            f"input count = {self.n_in}",
            f"output count = {self.n_out}",
            f"scripts = {', '.join(self.scripts) or '—'}",
            f"token operations = {', '.join(self.token_operations) or 'none'}",
            f"Paytaca compatibility = {self.paytaca_status}",
            f"SeedCash compatibility = {self.seedcash_status}",
            f"semantic validation = {'valid' if self.semantic_valid else 'invalid'}"
            + (f" ({self.semantic_reason})" if self.semantic_reason else ""),
        ]


def fixture_identity(vector: dict[str, Any], *, scenario_id: str = "", scenario_label: str = "") -> FixtureIdentity:
    outs = vector.get("outputs") or []
    ins = vector.get("source_utxos") or []
    unsigned = _unsigned_present(vector)
    version = _psbt_version(vector)
    cons_ok = vector.get("actual_consensus") == "valid" or vector.get("consensus_match") is True
    psbt_ok = vector.get("actual_psbt") == "valid"
    sem = vector.get("semantics") or {}
    sem_ok = bool(sem.get("valid", cons_ok))
    pay_status, pay_badge = _paytaca_status(vector, version=version, psbt_ok=psbt_ok)
    sc_status, sc_badge = _seedcash_status(vector, unsigned=unsigned, version=version)
    return FixtureIdentity(
        psbt_version=version,
        unsigned_tx_present=unsigned,
        cashtokens=_has_tokens(vector),
        n_in=len(ins),
        n_out=len(outs),
        scripts=_scripts(vector),
        token_operations=_token_ops(vector),
        paytaca_status=pay_status,
        paytaca_badge=pay_badge,
        seedcash_status=sc_status,
        seedcash_badge=sc_badge,
        semantic_valid=sem_ok,
        semantic_reason=str(sem.get("invalid_reason") or vector.get("actual_consensus_reason") or ""),
        bch_tx_valid=bool(cons_ok and unsigned),
        psbt_valid=bool(psbt_ok and version == FORMAT_VERSION),
        scenario_id=scenario_id or vector.get("catalog_id") or vector.get("id") or "",
        scenario_label=scenario_label,
    )
