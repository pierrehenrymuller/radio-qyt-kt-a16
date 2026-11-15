"""5-tone screen (CPS Signal > 5 TONE, captures/5tone-written.img)."""

import pytest

from kta16 import fivetone as ft


def cps_default():
    d = bytearray(b"\xff" * 0x4000)
    d[0x2000:0x2004] = bytes.fromhex("bd 64 ad fb")
    d[0x2100:0x2104] = bytes.fromhex("07 04 04 04")
    d[0x2200:0x2204] = bytes.fromhex("b7 f9 09 1a")
    d[0x2300:0x2304] = bytes.fromhex("01 00 01 01")
    d[0x2400:0x2403] = bytes.fromhex("08 0a 0e")
    d[0x2500:0x2510] = bytes.fromhex("01 02 03 04 05 03 04 05 06 07 05 06 07 08 09 00")
    d[0x25F0:0x25FC] = bytes.fromhex("14 14 14 00 ff ff ff ff 00 01 06 3b")
    return d


def test_decode_cps_default():
    d = cps_default()
    assert ft.get_tones(d, 0)[:4] == [1981, 1124, 1197, 1275]
    assert ft.get_standard_params(d, 0) == (100, "A", "E")
    assert ft.get_encode(d, 1) == ("12345", "34567", "56789", "CCIR1")
    assert ft.delays_ms(d) == (200, 200, 200, 0)
    assert ft.decode_settings(d) == ("CCIR1", {1}, {2, 3})


def test_set_tone_writes_split_tables_and_coefficient():
    d = bytearray(b"\xff" * 0x4000)
    ft.set_tone(d, 0, 0, 1981)
    assert (d[0x2000], d[0x2100], d[0x2200], d[0x2300]) == (0xBD, 0x07, 0xB7, 0x01)


def test_set_encode_round_trip():
    d = bytearray(b"\xff" * 0x4000)
    ft.set_encode(d, 2, ("0A1B2", "", "FFFFF", "MODAT"))
    assert ft.get_encode(d, 2) == ("0A1B2", "", "FFFFF", "MODAT")


@pytest.mark.parametrize(
    "frames",
    [("1234", "", "", "CCIR1"), ("12G45", "", "", "CCIR1"), ("12345", "", "", "XX")],
)
def test_set_encode_rejects(frames):
    with pytest.raises(ValueError):
        ft.set_encode(bytearray(0x4000), 1, frames)


@pytest.mark.parametrize("s,i,hz", [(15, 0, 1000), (0, 16, 1000), (0, 0, 299)])
def test_set_tone_rejects(s, i, hz):
    with pytest.raises(ValueError):
        ft.set_tone(bytearray(0x4000), s, i, hz)


def test_default_tables_match_cps_write_on_real_radio():
    d = bytearray(b"\xff" * 0x4000)
    ft.install_default_tables(d)
    assert len(ft.DEFAULT_TABLES) == 0x3F0
    assert ft.get_tones(d, 0)[:4] == [1981, 1124, 1197, 1275]  # CCIR1
    assert d[0x23F0] == 0xFF and d[0x2400] == 0xFF  # nothing beyond 0x23EF


def test_set_delays_and_decode_settings():
    d = bytearray(b"\xff" * 0x4000)
    ft.set_delays_ms(d, 200, 200, 200, 0)
    ft.set_decode_settings(d, "CCIR1", {1}, {2, 3}, reset_raw=0x3B)
    assert bytes(d[0x25F0:0x25F4]) == bytes([20, 20, 20, 0])
    assert bytes(d[0x25F8:0x25FC]) == bytes([0, 1, 6, 0x3B])
    assert ft.decode_settings(d) == ("CCIR1", {1}, {2, 3})
    with pytest.raises(ValueError):
        ft.set_decode_settings(d, "NOPE", {1}, {1}, reset_raw=0)
    with pytest.raises(ValueError):
        ft.set_delays_ms(d, 205, 0, 0, 0)
