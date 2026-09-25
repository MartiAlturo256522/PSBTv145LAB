"""Input/output flow for the viewer diagram.

Same shape as SeedCash's PSBT chart: inputs on the left, outputs on the
right, a line for what moves between them. A token category paints part of
its bar. Known categories keep the SeedCash colors (PUSD purple, MUSD blue).
"""

from __future__ import annotations

from ctlab.psbt.codec import PSBT_IN_NON_WITNESS_UTXO, PsbtError, decode_psbt
from ctlab.transactions.serialize import decode_transaction

PUSD = "2469acc5afa4b10cb5b5c04afb89c3a3ffd61c5da9c01e26d00951cae2a02544"
MUSD = "b38a33f750f84c5c169a6f23cb873e6e79605021585d4f3408789689ed87f366"
NAMED = {PUSD: ("#8048EA", "PUSD"), MUSD: ("#447DF7", "MUSD")}
PALETTE = (
    "#c45cff",
    "#3dcf8e",
    "#f4c15d",
    "#ff6b6b",
    "#ff9f43",
    "#54e1d2",
    "#e36bff",
    "#8bd450",
    "#ff5fa2",
    "#7eb6ff",
)


def _color(category: str | None) -> str | None:
    if not category:
        return None
    named = NAMED.get(category.lower())
    if named:
        return named[0]
    return PALETTE[int(category[:6], 16) % len(PALETTE)]


def _symbol(category: str | None) -> str | None:
    if not category:
        return None
    named = NAMED.get(category.lower())
    if named:
        return named[1]
    return category[:4] + "…" + category[-4:]


def _script_kind(script: bytes) -> str:
    if not script:
        return "?"
    if script[:1] == b"\x6a":
        return "OP_RETURN"
    if len(script) == 25 and script.startswith(b"\x76\xa9\x14") and script.endswith(b"\x88\xac"):
        return "P2PKH"
    if len(script) == 23 and script.startswith(b"\xa9\x14") and script.endswith(b"\x87"):
        return "P2SH"
    if len(script) == 35 and script.startswith(b"\xaa\x20") and script.endswith(b"\x87"):
        return "P2SH32"
    if script[:1] in (b"\x21", b"\x41") and script.endswith(b"\xac"):
        return "P2PK"
    return "script"


_CAP = {"none": "inmutable", "mutable": "mutable", "minting": "emisión"}


def _token_view(token) -> dict:
    if token is None or (token.nft is None and token.amount <= 0):
        return {"kind": "BCH", "category": None, "ft": 0, "capability": None, "commitment": None}
    has_nft = token.nft is not None
    ft = int(token.amount or 0)
    if has_nft and ft > 0:
        kind = "FT+NFT"
    elif has_nft:
        kind = "NFT"
    else:
        kind = "FT"
    commit = None
    cap = None
    if token.nft is not None:
        cap = token.nft.capability
        commit = token.nft.commitment.hex() if token.nft.commitment else ""
    return {
        "kind": kind,
        "category": token.category,
        "ft": ft,
        "capability": cap,
        "commitment": commit,
    }


def _ft_share(row: dict, ft_totals: dict[str, int]) -> int:
    """How much of the fungible supply of this category sits in this output.

    The bar never becomes entirely the token color: the rest is the BCH of
    the same UTXO. An NFT is drawn as its own chip, not as a fake percent.
    """
    if row["ft"] <= 0 or not row["category"]:
        return 0
    total = ft_totals.get(row["category"]) or 0
    if total <= 0:
        return 70
    share = row["ft"] / total
    return max(22, min(70, round(22 + 48 * share)))


def describe_psbt(psbt: bytes) -> dict:
    try:
        decoded = decode_psbt(psbt)
    except (PsbtError, Exception) as exc:
        return {"error": str(exc), "inputs": [], "outputs": [], "links": []}
    if not decoded.unsigned_tx:
        return {"error": "sin transacción sin firmar", "inputs": [], "outputs": [], "links": []}
    try:
        tx = decode_transaction(decoded.unsigned_tx)
    except Exception as exc:
        return {"error": str(exc), "inputs": [], "outputs": [], "links": []}

    inputs = []
    for i, inp in enumerate(tx.inputs):
        spent = None
        if i < len(decoded.inputs):
            for key, value in decoded.inputs[i]:
                if key[:1] == bytes([PSBT_IN_NON_WITNESS_UTXO]) and value:
                    try:
                        parent = decode_transaction(value)
                        if 0 <= inp.prev_index < len(parent.outputs):
                            spent = parent.outputs[inp.prev_index]
                    except Exception:
                        spent = None
                    break
        view = _token_view(spent.token if spent else None)
        inputs.append(
            {
                "i": i,
                "sats": None if spent is None else spent.value_sats,
                "script": _script_kind(spent.locking_bytecode if spent else b""),
                "prev_index": inp.prev_index,
                **view,
            }
        )

    outputs = []
    for i, out in enumerate(tx.outputs):
        view = _token_view(out.token)
        outputs.append(
            {
                "i": i,
                "sats": out.value_sats,
                "script": _script_kind(out.locking_bytecode),
                "prev_index": None,
                **view,
            }
        )

    def ft_totals(rows: list[dict]) -> dict[str, int]:
        totals: dict[str, int] = {}
        for row in rows:
            if row["ft"] and row["category"]:
                totals[row["category"]] = totals.get(row["category"], 0) + row["ft"]
        return totals

    in_totals = ft_totals(inputs)
    out_totals = ft_totals(outputs)
    for row, totals in ((inputs, in_totals), (outputs, out_totals)):
        for item in row:
            item["ft_share"] = _ft_share(item, totals)
            item["color"] = _color(item["category"])
            item["label"] = _symbol(item["category"])
            item["nft_label"] = None if not item["capability"] else "NFT " + _CAP.get(item["capability"], item["capability"])

    def _nft_text(src: dict, dst: dict, genesis: bool) -> str:
        src_cap = _CAP.get(src.get("capability") or "", src.get("capability") or "")
        dst_cap = _CAP.get(dst.get("capability") or "", dst.get("capability") or "")
        if genesis:
            body = "génesis NFT " + dst_cap
        elif src.get("capability") and dst.get("capability") and src.get("capability") != dst.get("capability"):
            body = f"NFT {src_cap} → {dst_cap}"
        else:
            body = "NFT " + (dst_cap or src_cap)
        if src.get("commitment") is not None and dst.get("commitment") is not None and src.get("commitment") != dst.get("commitment"):
            body += " · commitment"
        return body

    links = []
    inputs_by_cat: dict[str, list[dict]] = {}
    outputs_by_cat: dict[str, list[dict]] = {}
    for row in inputs:
        if row["category"]:
            inputs_by_cat.setdefault(row["category"], []).append(row)
    for row in outputs:
        if row["category"]:
            outputs_by_cat.setdefault(row["category"], []).append(row)

    def _pair_nft(sources: list[dict], dests: list[dict]) -> list[tuple[dict, dict]]:
        nft_in = [row for row in sources if row["capability"]]
        nft_out = [row for row in dests if row["capability"]]
        if not nft_in or not nft_out:
            return []
        if len(nft_in) == 1 or len(nft_out) == 1:
            return [(src, dst) for src in nft_in for dst in nft_out]
        used: set[int] = set()
        pairs = []
        for src in nft_in:
            match = next(
                (dst for dst in nft_out if dst["i"] not in used and dst.get("commitment") == src.get("commitment")),
                None,
            )
            if match is None and len(nft_in) == len(nft_out):
                match = next((dst for dst in nft_out if dst["i"] not in used), None)
            if match is not None:
                used.add(match["i"])
                pairs.append((src, match))
        return pairs

    for category, sources in inputs_by_cat.items():
        dests = outputs_by_cat.get(category, [])
        color = _color(category)
        for src, dst in _pair_nft(sources, dests):
            links.append({"from": src["i"], "to": dst["i"], "kind": _nft_text(src, dst, False), "color": color, "genesis": False})
        ft_in = [row for row in sources if row["ft"] > 0]
        ft_out = [row for row in dests if row["ft"] > 0]
        if len(ft_in) == 1:
            for dst in ft_out:
                links.append({"from": ft_in[0]["i"], "to": dst["i"], "kind": f"{dst['ft']} FT", "color": color, "genesis": False})
        else:
            for src in ft_in:
                for dst in ft_out:
                    links.append({"from": src["i"], "to": dst["i"], "kind": "FT", "color": color, "genesis": False})

    genesis_sources = [row for row in inputs if row["prev_index"] == 0] or inputs[:1]
    for dst in outputs:
        if not dst["category"] or dst["category"] in inputs_by_cat:
            continue
        color = _color(dst["category"])
        src = genesis_sources[0]
        if dst["capability"]:
            links.append({"from": src["i"], "to": dst["i"], "kind": _nft_text(src, dst, True), "color": color, "genesis": True})
        if dst["ft"] > 0:
            links.append({"from": src["i"], "to": dst["i"], "kind": f"génesis {dst['ft']} FT", "color": color, "genesis": True})

    bch_out = [row for row in outputs if row["kind"] == "BCH" and row["script"] != "OP_RETURN"]
    if bch_out and len(inputs) * len(bch_out) <= 12:
        for src in inputs:
            for dst in bch_out:
                links.append({"from": src["i"], "to": dst["i"], "kind": "BCH", "color": "#8ea0b5", "genesis": False})

    in_sats = [row["sats"] for row in inputs if row["sats"] is not None]
    out_sats = sum(row["sats"] for row in outputs)
    fee = None
    if len(in_sats) == len(inputs):
        fee = sum(in_sats) - out_sats
    return {"inputs": inputs, "outputs": outputs, "links": links, "fee": fee}
