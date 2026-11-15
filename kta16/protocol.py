"""Serial frames of the KT-A16 programming protocol.

Every constant here comes from the static analysis of the vendor CPS;
docs/protocol.md gives the virtual address that proves each one.
"""

from dataclasses import dataclass

HANDSHAKE = bytes.fromhex("55 20 23 04 26 ff dc 02")
ACK = b"\x06"
CMD_READ = 0x53  # 'S'
CMD_WRITE = 0x58  # 'X'
READ_SIZE = 0x40
WRITE_SIZE = 0x10
IMAGE_SIZE = 0x4000
IDENT_SIZE = 48
IDENT_TRAILER = 0x55
IDENT_FRAME_SIZE = IDENT_SIZE + 3  # 06, payload, 55 and one tail byte (0x05 seen)
READ_REPLY_SIZE = 4 + READ_SIZE


class ProtocolError(Exception):
    """The radio sent something the CPS would reject."""


@dataclass(frozen=True)
class Ident:
    """Identification sent by the radio after the handshake."""

    bands: tuple  # ((low_mhz, high_mhz) or None, ...) for bands A, B, C
    texts: tuple  # three ASCII strings shown by the CPS


def _check_address(addr, size):
    if not 0 <= addr <= IMAGE_SIZE - size or addr % size:
        raise ValueError(f"address {addr:#06x} invalid for a {size}-byte block")


READ_SIZES = (0x10, READ_SIZE)  # 16 bytes: password block (VA 0x483525)
REPLY_HEADER = 0x58  # the CPS looks for 'X' in the reply (VA 0x483525)


def read_request(addr, ack=False, size=READ_SIZE):
    """Ask for size bytes at addr; ack=True prefixes the ACK of the last reply."""
    if size not in READ_SIZES:
        raise ValueError(f"read size must be one of {READ_SIZES}")
    _check_address(addr, size)
    frame = bytes([CMD_READ, addr >> 8, addr & 0xFF, size])
    return ACK + frame if ack else frame


def write_frame(addr, data, ack=True):
    """Write 16 bytes at addr.

    ack=True prefixes the ACK of the previous write reply, as the CPS does
    for every frame but the first of a session (real capture).
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    if len(data) != WRITE_SIZE:
        raise ValueError(f"data must be {WRITE_SIZE} bytes, got {len(data)}")
    _check_address(addr, WRITE_SIZE)
    frame = bytes([CMD_WRITE, addr >> 8, addr & 0xFF, WRITE_SIZE]) + bytes(data)
    return ACK + frame if ack else frame


def _digits(raw):
    """3 digit bytes to a number, None when a byte is not a digit."""
    if any(b > 9 for b in raw):
        return None
    return raw[0] * 100 + raw[1] * 10 + raw[2]


def _band(raw):
    """(low, high) MHz of one band, None when unknown.

    Seen on the real radio (2026-11-15): 00 00 00 00 0f 00 in all three bands,
    frame otherwise valid. Refusing it ended the session before the ACK.
    """
    low, high = _digits(raw[:3]), _digits(raw[3:6])
    return None if low is None or high is None else (low, high)


def _ident_text(raw):
    """The real radio sends digit values (0..9); the CPS also accepts ASCII."""
    if all(b <= 9 for b in raw):
        return "".join(str(b) for b in raw)
    return raw.decode("ascii", errors="replace").strip()


def parse_ident(raw):
    """Decode the identification: 06, 48 bytes, 55, then one tail byte.

    Accepted with or without the leading ACK and the tail byte (the CPS acts
    as soon as it holds 50 bytes).
    """
    if len(raw) in (IDENT_SIZE + 2, IDENT_SIZE + 3) and raw[0] == ACK[0]:
        raw = raw[1 : IDENT_SIZE + 2]
    # Without ACK the CPS accepts the frame only if it starts with digit 1.
    elif not raw or raw[0] != 1:
        raise ProtocolError("identification does not start with ACK or digit 1")
    if len(raw) != IDENT_SIZE + 1 or raw[-1] != IDENT_TRAILER:
        raise ProtocolError(f"bad identification frame ({len(raw)} bytes)")
    p = raw[:IDENT_SIZE]
    bands = tuple(_band(p[o : o + 6]) for o in (0x00, 0x10, 0x20))
    texts = tuple(
        _ident_text(p[a:b]) for a, b in ((0x0A, 0x10), (0x1A, 0x20), (0x26, 0x30))
    )
    return Ident(bands, texts)


def parse_read_reply(reply, size=READ_SIZE, addr=None):
    """Return the data of a read reply: 58 AH AL LEN then LEN bytes."""
    if len(reply) != 4 + size:
        raise ProtocolError(f"read reply has {len(reply)} bytes, expected {4 + size}")
    if addr is not None:
        expected = bytes([REPLY_HEADER, addr >> 8, addr & 0xFF, size])
        if bytes(reply[:4]) != expected:
            raise ProtocolError(
                f"read reply header {bytes(reply[:4]).hex(' ')}, expected {expected.hex(' ')}"
            )
    return bytes(reply[4:])
