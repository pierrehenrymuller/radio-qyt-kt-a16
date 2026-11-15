"""Option-screen fields (addresses found by CPS write experiments)."""

import pytest

from kta16 import settings

# Image written by the CPS after "Default" then "Write" (captures, docs/protocol.md)
DEFAULTS = {
    0x0E00: 0x00,
    0x0E02: 0x05,
    0x0E03: 0x00,
    0x0E04: 0x00,
    0x0E05: 0x04,
    0x0E06: 0x01,
    0x0E07: 0x00,
    0x0E08: 0x01,
    0x0E09: 0x00,
    0x0E0A: 0x01,
    0x0E0B: 0x00,
    0x0E0F: 0x00,
    0x0E10: 0x05,
    0x0E11: 0x01,
    0x0E1F: 0x0A,
    0x0E20: 0x00,
}


def image_with_defaults():
    data = bytearray(0x4000)
    for addr, value in DEFAULTS.items():
        data[addr] = value
    return data


@pytest.mark.parametrize(
    "key,label",
    [
        ("tmr", "OFF"),
        ("squelch", "5"),
        ("tot", "60"),
        ("save", "1:1"),
        ("beep", "ON"),
        ("scan_add", "ON"),
        ("scan_rev", "TO"),
        ("color_above_stat", "Indigo"),
        ("color_main", "Red"),
        ("tmr_return_ab", "10"),
        ("tx_for_tmr", "Track"),
        ("voice", "OFF"),
    ],
)
def test_defaults_decode_as_cps_displays(key, label):
    f = settings.FIELD_BY_KEY[key]
    assert f.label_of(f.get(image_with_defaults())) == label


def test_set_writes_single_byte():
    data = image_with_defaults()
    before = bytes(data)
    settings.FIELD_BY_KEY["squelch"].set(data, 9)
    diff = [i for i in range(len(data)) if data[i] != before[i]]
    assert diff == [0x0E02] and data[0x0E02] == 9


@pytest.mark.parametrize("value", [-1, 10, 256, "5", None, 2.5])
def test_set_rejects_out_of_list(value):
    with pytest.raises((ValueError, TypeError)):
        settings.FIELD_BY_KEY["squelch"].set(bytearray(0x4000), value)


def test_unknown_value_has_raw_label():
    f = settings.FIELD_BY_KEY["save"]
    assert f.label_of(0x77) == "0x77 ?"


def test_fields_have_unique_addresses():
    addrs = [f.addr for f in settings.FIELDS]
    assert len(addrs) == len(set(addrs))


def test_vfo_digits_like_cps_default():
    data = bytearray(0x4000)
    data[0x0F00:0x0F08] = bytes.fromhex("01 03 06 00 02 05 00 00")
    data[0x0F08:0x0F0E] = bytes.fromhex("00 01 00 06 05 00")
    assert settings.vfo_frequency(data, 0) == "136.02500"
    assert settings.vfo_offset(data, 0) == "010.650"
    settings.set_vfo_frequency(data, 0, "446.00625")
    assert bytes(data[0x0F00:0x0F08]) == bytes([4, 4, 6, 0, 0, 6, 2, 5])
    settings.set_vfo_offset(data, 0, "005.000")
    assert bytes(data[0x0F08:0x0F0E]) == bytes([0, 0, 5, 0, 0, 0])


@pytest.mark.parametrize(
    "text", ["136.0250", "1360.2500", "abc.defgh", "", "136,02500"]
)
def test_vfo_frequency_rejects(text):
    with pytest.raises(ValueError):
        settings.set_vfo_frequency(bytearray(0x4000), 0, text)


def test_vfo_b_and_c_fields_checked_on_cps():
    # captures/vfo-all.png: B at 0x0F20, C at 0x0F40, same layout as A
    data = bytearray(0x4000)
    data[0x0F39], data[0x0F3B], data[0x0F5B] = 1, 2, 3
    assert settings.FIELD_BY_KEY["vfo_b_power"].label_of(data[0x0F39]) == "LOW"
    assert settings.FIELD_BY_KEY["vfo_b_step"].get(data) == 2
    assert settings.FIELD_BY_KEY["vfo_c_step"].label_of(3) == "10.00"
    assert "vfo_d_step" not in settings.FIELD_BY_KEY


@pytest.mark.parametrize(
    "text,raw", [("88.5", b"\x75\x03"), ("d023n", b"\x01\x00"), ("OFF", b"\x00\x00")]
)
def test_vfo_tones_use_the_channel_encoding(text, raw):
    d = bytearray(b"\xff" * 0x4000)
    settings.set_vfo_tone(d, 1, "rx", text)
    settings.set_vfo_tone(d, 1, "tx", text)
    assert d[0x0F30:0x0F32] == raw and d[0x0F32:0x0F34] == raw
    assert settings.vfo_tone(d, 1, "rx") == text.upper()


@pytest.mark.parametrize("text", ["", "88", "D999N", "88.5; rm", "x" * 300, None])
def test_vfo_tone_rejects(text):
    d = bytearray(b"\xff" * 0x4000)
    with pytest.raises((TypeError, ValueError)):
        settings.set_vfo_tone(d, 0, "rx", text)
    assert d[0x0F10:0x0F12] == b"\xff\xff"


def test_step_8_33_khz_is_the_value_6_held_by_the_real_radio():
    # the radio shows 8.33 kHz on line A, which holds 6 (past the CPS list)
    step = settings.FIELD_BY_KEY["vfo_a_step"]
    assert step.label_of(6) == "8.33"
    d = bytearray(b"\xff" * 0x4000)
    step.set(d, 6)
    assert d[0x0F1B] == 6


@pytest.mark.parametrize("line", "abc")
def test_step_list_is_shown_from_smallest_to_largest(line):
    step = settings.FIELD_BY_KEY[f"vfo_{line}_step"]
    labels = [label for _, label in step.options()]
    assert labels == ["2.50", "5.00", "6.25", "8.33", "10.00", "12.50", "25.00"]
    # the stored values do not move: 8.33 is still 6, 10.00 still 3
    stored = {label: value for value, label in step.options()}
    assert stored["8.33"] == 6 and stored["10.00"] == 3 and stored["25.00"] == 5


def test_other_lists_keep_the_order_of_the_cps():
    tot = settings.FIELD_BY_KEY["tot"]
    assert [v for v, _ in tot.options()] == sorted(v for v, _ in tot.options())
    assert [label for _, label in settings.FIELD_BY_KEY["beep"].options()] == [
        "OFF",
        "ON",
    ]
