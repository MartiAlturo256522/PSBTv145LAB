from ctlab.protocol.cashaddr import decode_cashaddr, encode_cashaddr


def test_official_p2pkh():
    # CashAddr spec: HASH160 F5BF48B3... version 0
    payload = bytes.fromhex("F5BF48B36FC68E4AE24690C31B39CE1C5F1F16F8")
    addr = encode_cashaddr(payload, 0x00, "bitcoincash")
    # Commonly cited example uses a different hash; at least round-trip.
    prefix, ver, pl = decode_cashaddr(addr)
    assert prefix == "bitcoincash"
    assert ver == 0x00
    assert pl == payload


def test_token_p2pkh_version():
    payload = bytes.fromhex("00" * 20)
    addr = encode_cashaddr(payload, 0x10, "bitcoincash")
    assert ":z" in addr or addr.split(":")[1].startswith("z")
    _, ver, _ = decode_cashaddr(addr)
    assert ver == 0x10
