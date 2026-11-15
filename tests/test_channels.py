"""Channel row codec (docs/protocol.md, decoder VA 0x474b20)."""

import pytest

from kta16.channels import Channel, decode_channel, encode_channel

# RX 146.52500, TX 146.52500, RX CTCSS 88.5, TX DCS D023N, LOW power,
# PTT-ID BOT, scan add, busy lock, narrow, 2TONE opt signal, AND, scrambler on.
ROW = bytes.fromhex("00 25 65 14 00 25 65 14 75 03 01 00 03 12 11 4d")
NAME = b"LFPX\xff\xff\xff\xff"


def test_decode_full_row():
    ch = decode_channel(ROW, NAME)
    assert ch == Channel(
        rx_hz=146_525_000,
        tx_hz=146_525_000,
        rx_tone="88.5",
        tx_tone="D023N",
        power="LOW",
        narrow=True,
        ptt_id="BOT",
        busy_lock=True,
        scan_add=True,
        sig_code=4,  # CPS shows stored value + 1 (captures/chan-read.png)
        opt_signal="2TONE",
        sp_mute="AND",
        scrambler=True,
        name="LFPX",
    )


def test_encode_is_inverse_of_decode():
    ch = decode_channel(ROW, NAME)
    assert encode_channel(ch, ROW, NAME) == (ROW, NAME)


def test_empty_channel():
    assert decode_channel(b"\xff" * 16, b"\xff" * 8) is None
    assert encode_channel(None, ROW, NAME) == (b"\xff" * 16, b"\xff" * 8)


@pytest.mark.parametrize("raw", [b"\x00\x00", b"\xff\xff"])
def test_tone_off_variants(raw):
    row = ROW[:8] + raw + ROW[10:]
    assert decode_channel(row, NAME).rx_tone == "OFF"


def test_unknown_bits_are_preserved():
    row = bytearray(ROW)
    row[12] |= 0xA0  # high nibble of byte 12: meaning unknown
    ch = decode_channel(bytes(row), NAME)
    assert encode_channel(ch, bytes(row), NAME)[0] == bytes(row)


def test_dcs_inverted():
    row = ROW[:8] + bytes([1 + 105, 0]) + ROW[10:]
    assert decode_channel(row, NAME).rx_tone == "D023I"


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "TOOLONG1"),  # 8 characters: the radio shows the 8th as a number
        ("name", "lfpx"),
        ("name", "A.B"),
        ("name", "A\nB"),
        ("name", "É"),
        ("rx_hz", 146_525_001),  # not a multiple of 10 Hz
        ("rx_hz", 0),
        ("rx_hz", 10**9),
        ("rx_tone", "88.6"),
        ("rx_tone", "D999N"),
        ("power", "MID"),
        ("ptt_id", "ALL"),
        ("sig_code", 16),
        ("sig_code", 0),
        ("sig_code", -1),
        ("opt_signal", "FSK"),
        ("sp_mute", "XOR"),
        ("rx_hz", "146.525"),
    ],
)
def test_encode_rejects_bad_values(field, value):
    ch = decode_channel(ROW, NAME)
    bad = ch.__class__(**{**ch.__dict__, field: value})
    with pytest.raises(ValueError):
        encode_channel(bad, ROW, NAME)


def test_name_digits_and_empty():
    ch = decode_channel(ROW, NAME)
    for name in ("", "123456", "A1"):
        new = ch.__class__(**{**ch.__dict__, "name": name})
        _, raw = encode_channel(new, ROW, NAME)
        assert len(raw) == 8 and decode_channel(ROW, raw).name == name


@pytest.mark.parametrize(
    "name", ["A B", "A-B", "A+B", "A_B", "ABCDEFG", "1234567", "A  B", "-", "_"]
)
def test_names_the_radio_accepts(name):
    # Written to the real radio (captures/names-1.log, 2026-11-11): the screen
    # shows space, - + _ and 7 characters; the CPS refuses them and stops at 6.
    ch = decode_channel(ROW, NAME)
    new = ch.__class__(**{**ch.__dict__, "name": name})
    _, raw = encode_channel(new, ROW, NAME)
    assert len(raw) == 8 and raw[7] == 0xFF  # the 8th byte is never used
    assert decode_channel(ROW, raw).name == name


def test_name_spaces_at_the_ends_are_not_kept():
    # the radio pads its own names with spaces ("  WX01"): shown trimmed
    ch = decode_channel(ROW, NAME)
    new = ch.__class__(**{**ch.__dict__, "name": " AB "})
    _, raw = encode_channel(new, ROW, NAME)
    assert decode_channel(ROW, raw).name == "AB"


def test_off_tone_encoded_as_zero_like_cps():
    # CPS write of channel 2 (captures/chan-written.img): RX tone OFF = 00 00
    row = bytes.fromhex("25 06 60 44 25 06 60 44 00 00 6a 00 0f 00 00 00")
    name = b"PMR1\xff\xff\xff\xff"
    assert encode_channel(decode_channel(row, name), b"\xff" * 16, b"\xff" * 8) == (
        row,
        name,
    )


def test_real_radio_weather_channel_name_has_leading_spaces():
    # channel 191 of the real radio (captures/radio-real.img); CPS shows "WX01"
    row = bytes.fromhex("00 50 25 16 00 50 25 16 00 00 00 00 00 00 00 04")
    name = bytes.fromhex("20 20 57 58 30 31 ff ff")
    ch = decode_channel(row, name)
    assert (ch.name, ch.rx_hz, ch.sig_code, ch.scan_add) == (
        "WX01",
        162_550_000,
        1,
        True,
    )


def test_tx_off_frequency_round_trips_and_differs_from_empty():
    from kta16 import channels

    assert channels.TX_OFF_HZ == 200_000_000
    ch = channels.Channel(
        122_500_000, channels.TX_OFF_HZ, "OFF", "OFF", "LOW", False, "OFF", False,
        True, None, "OFF", "QT", False, "ATIS",
    )  # fmt: skip
    row, name = channels.encode_channel(ch, b"\xff" * 16, b"\xff" * 8)
    assert channels.decode_channel(row, name).tx_hz == 200_000_000
    assert bytes(row[4:8]) != b"\xff" * 4
