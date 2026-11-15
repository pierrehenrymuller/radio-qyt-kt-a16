"""2-tone screen (CPS Signal > 2 TONE, captures/2tone-written.img)."""

import pytest

from kta16 import twotone as tt


def cps_default():
    d = bytearray(b"\xff" * 0x4000)
    d[0x2D00:0x2D10] = bytes.fromhex("bd 07 ff ff ff ff ff ff 64 04 ff ff ff ff ff ff")
    d[0x2DF0:0x2DF3] = bytes.fromhex("3c 3c 1e")
    d[0x2E00:0x2E0C] = bytes.fromhex("00 01 01 04 02 02 08 03 03 09 00 04")
    d[0x2F00:0x2F10] = bytes.fromhex("bd 07 64 04 ad 04 fb 04 b7 01 f9 00 0a 01 1b 01")
    return d


def test_decode_cps_default():
    d = cps_default()
    assert tt.get_encode(d, 1) == (1981, 1124)
    assert tt.get_encode(d, 2) is None
    assert tt.durations_ms(d) == (600, 600, 300)
    assert tt.get_decode(d, 1) == [
        ("A-B", "1.Alert", 1),
        ("B-C", "2.Transpond", 2),
        ("C-D", "3.Alert+Transpond", 3),
        ("D-A", "0.None", 4),
    ]
    assert tt.get_tones(d, 1) == (1981, 1124, 1197, 1275)


def test_set_tones_recomputes_coefficients_like_cps():
    d = bytearray(b"\xff" * 0x4000)
    tt.set_tones(d, 1, (1981, 1124, 1197, 1275))
    assert bytes(d[0x2F00:0x2F10]) == bytes.fromhex(
        "bd 07 64 04 ad 04 fb 04 b7 01 f9 00 0a 01 1b 01"
    )
    tt.set_tones(d, 1, (None, 1124, None, None))
    assert tt.get_tones(d, 1) == (None, 1124, None, None)


def test_set_encode_and_clear():
    d = bytearray(b"\xff" * 0x4000)
    tt.set_encode(d, 15, (2200, 970))
    assert bytes(d[0x2DE0:0x2DE2]) == bytes.fromhex("98 08")
    tt.set_encode(d, 15, None)
    assert tt.get_encode(d, 15) is None


@pytest.mark.parametrize("hz", [299, 3001, "1000", 1000.5])
def test_frequency_range(hz):
    with pytest.raises((ValueError, TypeError)):
        tt.set_encode(bytearray(0x4000), 1, (hz, 1000))


def test_set_decode_validates():
    d = bytearray(b"\xff" * 0x4000)
    tt.set_decode(d, 2, [("A-C", "1.Alert", 5)] * 4)
    assert d[0x2E10:0x2E13] == bytes([1, 1, 5])
    with pytest.raises(ValueError):
        tt.set_decode(d, 2, [("A-A", "1.Alert", 1)] * 4)
    with pytest.raises(ValueError):
        tt.set_decode(d, 2, [("A-B", "9.Bad", 1)] * 4)


def test_reset_raw_value():
    d = bytearray(b"\xff" * 0x4000)
    tt.set_reset_raw(d, 0x3B)  # CPS default, shown as 6000 ms
    assert d[0x2FF0] == 0x3B and tt.reset_raw(d) == 0x3B
    with pytest.raises(ValueError):
        tt.set_reset_raw(d, 256)


@pytest.mark.parametrize("ms,value", [(100, 0), (6000, 59), (6500, 64), (8000, 79)])
def test_reset_ms_formula_measured_in_the_cps(ms, value):
    # CPS lists 100..8000 ms by 100; written bytes seen: 0, 0x48, 0x4f, 0x40
    assert tt.reset_value(ms) == value and tt.reset_ms(value) == ms


@pytest.mark.parametrize("ms", [0, 50, 150, 8100, -100, "6000", None])
def test_reset_ms_rejects(ms):
    with pytest.raises((TypeError, ValueError)):
        tt.reset_value(ms)
