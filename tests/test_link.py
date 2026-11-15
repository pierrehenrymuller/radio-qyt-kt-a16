"""Serial session against the radio emulator."""

import pytest

from kta16 import protocol
from kta16.emulator import FakeSerial, RadioEmulator
from kta16.link import Radio
from kta16.protocol import ProtocolError


def make_radio(**kw):
    image = bytearray(range(256)) * (protocol.IMAGE_SIZE // 256)
    emu = RadioEmulator(image, **kw)
    return Radio(FakeSerial(emu), timeout=0.2), emu


def test_connect_returns_ident():
    radio, emu = make_radio()
    ident = radio.connect()
    assert ident.bands[0] == (136, 174)
    assert emu.log[0] == protocol.HANDSHAKE


def test_read_block_acknowledges_reply():
    radio, emu = make_radio()
    radio.connect()
    assert radio.read_block(0x0040) == bytes(range(0x40, 0x80))
    assert emu.log[-1] == protocol.ACK


def test_read_range_covers_all_blocks():
    radio, emu = make_radio()
    radio.connect()
    seen = []
    data = radio.read_range(
        0x1000, 0x1100, progress=lambda done, total: seen.append(done)
    )
    assert data == bytes(emu.image[0x1000:0x1100])
    assert seen == [1, 2, 3, 4]


def test_write_range_updates_emulator():
    radio, emu = make_radio()
    radio.connect()
    new = bytes([0xA5]) * 0x40
    radio.write_range(0x0E00, new)
    assert bytes(emu.image[0x0E00:0x0E40]) == new
    assert emu.image[0x0E40] == 0x40


def test_operations_require_connect():
    radio, _ = make_radio()
    with pytest.raises(ProtocolError):
        radio.read_block(0)


def test_silent_radio_times_out():
    radio, _ = make_radio(silent=True)
    with pytest.raises(ProtocolError, match="timeout"):
        radio.connect()


def test_demo_firmware_banner_is_rejected():
    banner = b"Uart functional API interrupt example\r\n" * 4
    radio, _ = make_radio(handshake_reply=banner)
    with pytest.raises(ProtocolError):
        radio.connect()


def test_write_without_ack_fails():
    radio, _ = make_radio(write_ack=b"\x15")
    radio.connect()
    with pytest.raises(ProtocolError, match="ACK"):
        radio.write_range(0x0E00, bytes(16))


def test_write_range_rejects_misaligned_length():
    radio, _ = make_radio()
    radio.connect()
    with pytest.raises(ValueError):
        radio.write_range(0x0E00, bytes(17))


def test_read_password_block():
    radio, emu = make_radio()
    emu.image[0x3DF0:0x3E00] = b"      " + b"123456" + b"\xff" * 4
    radio.connect()
    assert radio.read_block(0x3DF0, size=0x10)[:12] == b"      123456"


def test_session_matches_real_capture_sequence():
    """Order seen on the wire with the vendor CPS (captures/win-read1-flow.txt)."""
    radio, emu = make_radio()
    radio.connect()
    radio.read_block(0x3DF0, size=0x10)
    radio.read_block(0x0000)
    assert emu.log == [
        protocol.HANDSHAKE,
        protocol.ACK,
        bytes.fromhex("53 3d f0 10"),
        protocol.ACK,
        bytes.fromhex("53 00 00 40"),
        protocol.ACK,
    ]
    assert emu.acks_answered == 2  # the radio answers 06 to the ACK of each block


def test_read_fails_when_radio_does_not_confirm_ack():
    radio, _ = make_radio(ack_reply=b"")
    radio.connect()
    with pytest.raises(ProtocolError, match="ACK"):
        radio.read_block(0x0000)


def test_open_port_line_states_match_cps(monkeypatch):
    import serial

    from kta16 import link

    created = {}

    class Fake:
        def open(self):
            created["dtr"], created["rts"] = self.dtr, self.rts

    monkeypatch.setattr(serial, "Serial", Fake)
    link.open_port("/dev/null")
    assert created == {"dtr": True, "rts": False}  # SET_CONTROL_LINE_STATE 0x01


def test_connect_retries_like_cps_then_fails():
    # the vendor CPS repeats the handshake every 5 s, 4 times (captures/win-read2.txt)
    radio, emu = make_radio(silent=True)
    with pytest.raises(ProtocolError, match="4 handshakes"):
        radio.connect(attempts=4, interval=0)
    assert emu.log == [protocol.HANDSHAKE] * 4


def test_connect_succeeds_on_second_attempt():
    radio, emu = make_radio(silent=True)
    emu_answers = iter([False, True])

    original = emu.feed

    def feed(data):
        emu.silent = not next(emu_answers) if data == protocol.HANDSHAKE else emu.silent
        return original(data)

    emu.feed = feed
    assert radio.connect(attempts=2, interval=0).bands[0] == (136, 174)


def test_write_sequence_matches_real_capture():
    """captures/win-write-flow.txt: password read, then 58.. and 06 58.. frames."""
    radio, emu = make_radio()
    radio.connect()
    radio.read_block(0x3DF0, size=0x10)
    radio.write_range(0x0000, bytes(range(32)))
    assert emu.log[4:] == [
        bytes.fromhex("58 00 00 10") + bytes(range(16)),
        protocol.ACK,
        bytes.fromhex("58 00 10 10") + bytes(range(16, 32)),
    ]
    assert bytes(emu.image[0:32]) == bytes(range(32))


def test_write_frame_without_leading_ack():
    assert protocol.write_frame(0x0010, bytes(16), ack=False)[:4] == bytes.fromhex(
        "58 00 10 10"
    )


def test_session_alive_from_handshake_to_first_error():
    radio, emu = make_radio()
    assert not radio.session_alive
    radio.connect()
    assert radio.session_alive
    emu.silent = True
    with pytest.raises(ProtocolError):
        radio.read_block(0x0040)
    assert not radio.session_alive


def test_write_after_a_read_has_no_leading_ack():
    radio, emu = make_radio()
    radio.connect()
    data = bytes(16)
    radio.write_block(0x0000, data)  # first frame of a session: no ACK in front
    radio.write_block(0x0010, data)  # then 06 58 ...
    radio.read_block(0x0040)  # the read acknowledges: a new first frame
    radio.write_block(0x0020, data)
    kinds = ["HS" if f == protocol.HANDSHAKE else "ACK" if f == protocol.ACK
             else chr(f[0]) for f in emu.log]  # fmt: skip
    assert kinds == ["HS", "ACK", "X", "ACK", "X", "S", "ACK", "X"]
