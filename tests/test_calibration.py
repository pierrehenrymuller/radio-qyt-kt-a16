"""Calibration tables (CPS Adjust screen, captures/adj-written.img)."""

import itertools

import pytest

from kta16 import calibration as cal


def test_tables_do_not_overlap_and_stay_in_region():
    spans = sorted((t.addr, t.addr + t.length) for t in cal.TABLES)
    for (_a0, a1), (b0, _b1) in itertools.pairwise(spans):
        assert a1 <= b0
    assert all(0x3C00 <= s and e <= 0x3DF0 for s, e in spans)


def test_power_high_band1_defaults():
    data = bytearray(0x4000)
    data[0x3C00:0x3C10] = bytes.fromhex(
        "0c 0d 0d 0d 0d 0d 0e 0f 0f 0f 0f 0f 0f 0f 0f 0f"
    )
    t = cal.TABLE_BY_KEY["power_high_1"]
    assert t.get(data)[:7] == [12, 13, 13, 13, 13, 13, 14]


def test_set_value_bounds():
    data = bytearray(0x4000)
    t = cal.TABLE_BY_KEY["power_high_1"]
    t.set(data, 0, 255)
    assert data[0x3C00] == 255
    for bad in (-1, 256):
        with pytest.raises(ValueError):
            t.set(data, 0, bad)
    with pytest.raises(IndexError):
        t.set(data, 16, 1)


def test_band_limits_digits():
    data = bytearray(0x4000)
    data[0x3D90:0x3D98] = bytes.fromhex("01 03 07 01 07 04 00 01")
    assert cal.band_limits(data, 1) == (137, 174, True)


def test_tab4_and_tab5_tables_measured_in_the_sandbox():
    # Read, change one list, Write, diff (docs/protocol.md, 4th and 5th tabs)
    t = cal.TABLE_BY_KEY
    assert t["rf_out_wide_1"].addr == 0x3D00 and t["rf_out_narrow_1"].addr == 0x3D08
    assert t["rf_out_wide_2"].addr == 0x3D10 and t["rf_out_narrow_2"].addr == 0x3D18
    assert t["pa"].addr == 0x3D20 and t["pa"].length == 16
    assert t["audio_wide"].addr == 0x3D30 and t["audio_narrow"].addr == 0x3D38
    assert t["vox_threshold"].addr == 0x3DD0 and t["vox_threshold"].length == 11
    assert t["limit_mode"].addr == 0x3DDF and t["limit_mode"].length == 1
    covered = {a for x in cal.TABLES for a in range(x.addr, x.addr + x.length)}
    assert set(range(0x3D00, 0x3D40)) <= covered


def test_packed_audio_gain():
    # 0x79 shows "4" and "25" in the CPS, 0xBD "2" and "29"
    assert cal.unpack_gain(0x79) == (4, 25) and cal.unpack_gain(0xBD) == (2, 29)
    assert cal.pack_gain(4, 25) == 0x79
    for bad in ((8, 0), (0, 32), (-1, 0)):
        with pytest.raises(ValueError):
            cal.pack_gain(*bad)
