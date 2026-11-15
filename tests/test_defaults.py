"""CPS "Default" values measured in the sandbox (kta16/defaults.py)."""

import pytest

from kta16 import defaults, dtmf, fivetone, fm, image


def blank():
    return bytearray(b"\xff" * 0x4000)


def test_each_zone_stays_inside_its_screen():
    regions = {r.name: r.ranges for r in image.REGIONS}
    regions["calibration"] += image.PASSWORD.ranges
    for zone, parts in defaults.ZONES.items():
        for start, values in parts:
            for addr in range(start, start + len(values)):
                assert any(s <= addr < e for s, e in regions[zone]), (zone, addr)


def test_values_seen_in_the_cps_screens():
    d = blank()
    for zone in defaults.ZONES:
        defaults.apply(d, zone)
    assert d[0x0E05] == 4  # TOT 60 s
    assert dtmf.get_code(d, 1) == "20202" and dtmf.get_code(d, 15) == "30303"
    assert dtmf.get_function(d, "master_id") == "60606"
    assert fm.get(d, 1) == (88_900_000, "QZNEW")
    assert fivetone.get_tones(d, 0)[:2] == [1981, 1124]  # CCIR1
    assert image.Image(d).passwords() == ("123456", "303688")


def test_unset_bytes_are_kept():
    d = blank()
    defaults.apply(d, "5-tone")
    defaults.apply(d, "options")
    # end of each 5-tone period row, Model text, block 0x0E24..0x0E60
    for addr in (0x2403, 0x24F0, 0x0FE0, 0x0E24):
        assert d[addr] == 0xFF


def test_unknown_zone_is_refused():
    with pytest.raises(KeyError):
        defaults.apply(blank(), "channels")


def test_fm_clear_empties_every_row():
    d = blank()
    defaults.apply(d, "fm")
    fm.clear(d)
    assert d[0x3000:0x3100] == bytes(0x100)  # CPS "Clear" writes zeros
    assert all(fm.get(d, n) is None for n in range(1, fm.COUNT + 1))


def test_channel_clear_blanks_rows_and_names():
    im = image.Image()
    im.data[0:0x0C80] = bytes(0x0C80)
    im.data[0x1000:0x1C80] = b"A" * 0x0C80
    im.clear_channels()
    for start, end in image.CHANNELS.ranges:
        assert set(im.data[start:end]) == {0xFF}
