"""DTMF screen codec (CPS "Default" + "Write", captures/dtmf-written.img)."""

import pytest

from kta16 import dtmf


def default_region():
    data = bytearray(b"\xff" * 0x4000)
    data[0x2900:0x2905] = bytes.fromhex("02 0a 02 0a 02")
    data[0x29E0:0x29E5] = bytes.fromhex("03 0a 03 0a 03")
    data[0x29F0:0x29F2] = b"\x03\x03"
    data[0x2A20:0x2A23] = bytes.fromhex("01 01 09")
    data[0x2AD0:0x2AD5] = bytes.fromhex("06 0a 06 0a 06")
    data[0x2AF0:0x2AF8] = bytes.fromhex("01 1f 03 00 0b 0c 04 9f")
    return data


def test_decode_defaults_as_cps_shows():
    d = default_region()
    assert dtmf.get_code(d, 1) == "20202"
    assert dtmf.get_code(d, 2) == ""
    assert dtmf.get_code(d, 15) == "30303"
    assert dtmf.get_function(d, "alarm") == "119"
    assert dtmf.get_function(d, "master_id") == "60606"
    assert dtmf.speed_ms(d[0x29F0]) == 80
    assert dtmf.decode_digits(d[0x2AF4:0x2AF6]) == "*#"
    assert dtmf.get_rights(d, "vice") == {"inspection", "monitor"}


def test_encode_round_trip():
    d = bytearray(b"\xff" * 0x4000)
    dtmf.set_code(d, 3, "0123456789ABCD*#")
    assert dtmf.get_code(d, 3) == "0123456789ABCD*#"
    assert d[0x2920] == 0x0A and d[0x292D] == 0x00  # '0' and 'D'
    dtmf.set_code(d, 3, "")
    assert bytes(d[0x2920:0x2930]) == b"\xff" * 16


@pytest.mark.parametrize("code", ["12E", "1 2", "x", "1" * 17, 12])
def test_encode_rejects(code):
    with pytest.raises((ValueError, TypeError)):
        dtmf.set_code(bytearray(0x4000), 1, code)


@pytest.mark.parametrize("n", [0, 16])
def test_code_number_range(n):
    with pytest.raises(ValueError):
        dtmf.get_code(bytearray(0x4000), n)


def test_rights_bits():
    d = default_region()
    dtmf.set_rights(d, "master", {"monitor", "kill"})
    assert d[0x2AF1] == 0b01010
    with pytest.raises(ValueError):
        dtmf.set_rights(d, "master", {"reboot"})


def test_times_measured_on_cps_lists():
    # CPS list item i writes base + i (captures: 3/4/159 then 4/5/160 ...)
    assert dtmf.reset_ms(4) == 16000 and dtmf.reset_ms(5) == 16100
    assert dtmf.delay_ms(159) == 500 and dtmf.delay_ms(160) == 600
    assert dtmf.speed_ms(4) == 90
    d = bytearray(0x4000)
    dtmf.set_times(d, on_ms=100, off_ms=80, reset_ms=16200, delay_ms=700)
    assert (d[0x29F0], d[0x29F1], d[0x2AF6], d[0x2AF7]) == (5, 3, 6, 161)
    with pytest.raises(ValueError):
        dtmf.set_times(d, on_ms=85, off_ms=80, reset_ms=16000, delay_ms=500)


def test_state_flags_and_times():
    d = bytearray(b"\xff" * 0x4000)
    dtmf.set_state(d, {"rx_disable"})
    assert d[dtmf.STATE] == 0xFD and dtmf.get_state(d) == {"rx_disable"}
    with pytest.raises(ValueError):
        dtmf.set_state(d, {"bogus"})
    dtmf.set_times(d, 80, 80, 16000, 500)
    assert dtmf.times_ms(d) == (80, 80, 16000, 500)
