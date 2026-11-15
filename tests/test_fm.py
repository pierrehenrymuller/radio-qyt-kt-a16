"""FM broadcast channels (CPS FM-Radio screen, captures/fm-written.img)."""

import pytest

from kta16 import fm


def test_decode_cps_default():
    data = bytearray(0x4000)
    data[0x3000:0x3010] = bytes.fromhex(
        "00 08 08 09 00 00 00 00 51 5a 4e 45 57 ff ff ff"
    )
    data[0x3020:0x3030] = bytes.fromhex("00" * 8 + "ff" * 8)
    assert fm.get(data, 1) == (88_900_000, "QZNEW")
    assert fm.get(data, 3) is None


def test_encode_round_trip():
    data = bytearray(0x4000)
    fm.set(data, 16, 105_900_000, "CCTV9")
    assert bytes(data[0x30F0:0x3100]) == bytes.fromhex(
        "01 00 05 09 00 00 00 00 43 43 54 56 39 ff ff ff"
    )
    fm.set(data, 16, None, "")
    assert fm.get(data, 16) is None


@pytest.mark.parametrize(
    "hz,name",
    [
        (64_000_000, "A"),
        (108_100_000, "A"),
        (88_950_000, "A"),
        (88_900_000, "TOOLONGNAME"),
        (88_900_000, "é"),
        ("88.9", "A"),
    ],
)
def test_encode_rejects(hz, name):
    with pytest.raises((ValueError, TypeError)):
        fm.set(bytearray(0x4000), 1, hz, name)


@pytest.mark.parametrize("n", [0, 17])
def test_channel_range(n):
    with pytest.raises(ValueError):
        fm.get(bytearray(0x4000), n)


def test_blank_radio_row_is_empty():
    data = bytearray(b"\xff" * 0x4000)  # real radio: FM rows all 0xff
    assert fm.get(data, 1) is None
