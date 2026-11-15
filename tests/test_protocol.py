"""Frame building and parsing (docs/protocol.md)."""

import pytest

from kta16 import protocol
from kta16.protocol import ProtocolError


def ident_payload(**texts):
    """48-byte identification payload as the radio would send it."""
    p = bytearray(48)
    p[0:6] = bytes([1, 3, 6, 1, 7, 4])  # band A 136..174 MHz
    p[0x10:0x16] = bytes([4, 0, 0, 4, 8, 0])  # band B 400..480 MHz
    p[0x20:0x26] = bytes([2, 2, 0, 2, 6, 0])  # band C 220..260 MHz
    p[0x0A:0x10] = texts.get("t1", b"KTA16 ")
    p[0x1A:0x20] = texts.get("t2", b"SIM001")
    p[0x26:0x30] = texts.get("t3", b"V1.00     ")
    return bytes(p)


def test_handshake_is_fixed_frame():
    assert protocol.HANDSHAKE == bytes.fromhex("55 20 23 04 26 ff dc 02")


def test_read_request():
    assert protocol.read_request(0x1040) == bytes.fromhex("53 10 40 40")
    assert protocol.read_request(0x0000, ack=True) == bytes.fromhex("06 53 00 00 40")


@pytest.mark.parametrize("addr", [-1, 0x4000, 0x0001, 0x0020])
def test_read_request_rejects_bad_address(addr):
    with pytest.raises(ValueError):
        protocol.read_request(addr)


def test_write_frame():
    data = bytes(range(16))
    assert protocol.write_frame(0x0E10, data) == bytes.fromhex("06 58 0e 10 10") + data


@pytest.mark.parametrize("data", [b"", bytes(15), bytes(17), "0123456789abcdef"])
def test_write_frame_rejects_bad_data(data):
    with pytest.raises((ValueError, TypeError)):
        protocol.write_frame(0x0000, data)


@pytest.mark.parametrize("addr", [-16, 0x4000, 0x0008])
def test_write_frame_rejects_bad_address(addr):
    with pytest.raises(ValueError):
        protocol.write_frame(addr, bytes(16))


@pytest.mark.parametrize("prefix", [b"\x06", b""])
def test_parse_ident_with_and_without_ack(prefix):
    raw = prefix + ident_payload() + b"\x55"
    ident = protocol.parse_ident(raw)
    assert ident.bands == ((136, 174), (400, 480), (220, 260))
    assert ident.texts == ("KTA16", "SIM001", "V1.00")


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\x06" + ident_payload(),  # missing 0x55 trailer
        b"\x06" + ident_payload() + b"\x54",
        b"\x07" + ident_payload() + b"\x55",
        b"Uart functional API interrupt example\r\n" * 2,
    ],
)
def test_parse_ident_rejects_garbage(raw):
    with pytest.raises(ProtocolError):
        protocol.parse_ident(raw)


def test_parse_ident_non_digit_band_is_unknown_not_fatal():
    p = bytearray(ident_payload())
    p[1] = 0x33  # ASCII '3' instead of the digit value 3
    assert protocol.parse_ident(b"\x06" + bytes(p) + b"\x55").bands[0] is None


def test_read_request_16_bytes():
    # password block read by the channel screen (VA 0x483525 scans for 0x58)
    assert protocol.read_request(0x3DF0, size=0x10) == bytes.fromhex("53 3d f0 10")


def test_parse_read_reply_16_bytes():
    reply = bytes.fromhex("58 3d f0 10") + b"      123456    "
    assert protocol.parse_read_reply(reply, size=0x10) == b"      123456    "


def test_read_request_rejects_bad_size():
    with pytest.raises(ValueError):
        protocol.read_request(0, size=0x20)


def test_parse_read_reply():
    data = bytes(range(64))
    reply = bytes.fromhex("58 0c 80 40") + data
    assert protocol.parse_read_reply(reply) == data


@pytest.mark.parametrize("reply", [b"", bytes(67), bytes(69)])
def test_parse_read_reply_rejects_bad_length(reply):
    with pytest.raises(ProtocolError):
        protocol.parse_read_reply(reply)


# Frames captured from the real radio with the vendor CPS under Windows
# (captures/win-read1.pcap, docs/protocol.md).
REAL_IDENT = bytes.fromhex(
    "06 01 05 05 09 07 05 00 00 00 02 06 04 05 00 00 00 01 05 05 09 07 05 00 00 00"
    " 02 06 04 05 00 00 00 01 05 05 09 07 05 00 00 01 05 05 09 07 05 00 00 55 05"
)


def test_parse_real_ident_with_and_without_tail_byte():
    for raw in (REAL_IDENT, REAL_IDENT[:50]):
        ident = protocol.parse_ident(raw)
        assert ident.bands == ((155, 975), (155, 975), (155, 975))
        assert ident.texts[0] == "645000"


def test_real_password_reply():
    reply = bytes.fromhex("58 3d f0 10") + b" " * 12 + bytes(4)
    assert protocol.parse_read_reply(reply, size=0x10)[:12] == b" " * 12


def test_read_reply_must_echo_address():
    reply = bytes.fromhex("58 00 40 40") + bytes(64)
    assert protocol.parse_read_reply(reply, addr=0x0040) == bytes(64)
    with pytest.raises(ProtocolError):
        protocol.parse_read_reply(reply, addr=0x0080)
    with pytest.raises(ProtocolError):
        protocol.parse_read_reply(b"\x53" + reply[1:], addr=0x0040)


# Real identification of 2026-11-15: valid frame, band bytes are not digits.
REAL_ODD_IDENT = bytes.fromhex(
    "06 00 00 00 00 0f 00 00 00 00 00 00 00 00 00 00 04 00 00 00 00 0f 00 00"
    " 00 00 00 00 00 00 00 00 04 00 00 00 00 0f 00 00 00 00 00 00 00 0f 00 00"
    " 00 55"
)


def test_band_bytes_that_are_not_digits_make_the_band_unknown():
    ident = protocol.parse_ident(REAL_ODD_IDENT)
    assert ident.bands == (None, None, None)


def test_one_odd_band_leaves_the_others_decoded():
    p = bytearray(ident_payload())
    p[0x14] = 0x0F
    ident = protocol.parse_ident(b"\x06" + bytes(p) + b"\x55")
    assert ident.bands == ((136, 174), None, (220, 260))


def test_bad_frame_is_still_refused():
    with pytest.raises(ProtocolError):
        protocol.parse_ident(REAL_ODD_IDENT[:-1] + b"\x00")  # no 55 trailer
