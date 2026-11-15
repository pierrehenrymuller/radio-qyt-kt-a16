"""Memory channel codec: 16-byte row at (n-1)*16, 8-byte name at 0x1000+(n-1)*16.

Decoder of the CPS: VA 0x474b20 (row) and 0x4773e0 (name); encoder 0x487280.
Bits not decoded by the CPS are kept as they were in the image.
"""

import re
from dataclasses import dataclass

from kta16.tones import TONE_TABLE

CHANNEL_COUNT = 200  # [0x5772a0] = 0xc8 (VA 0x467c22)
# The CPS stops at 6 characters ("The letter of channel name max 6 bit", VA
# 0x48b4e2) and 0-9 A-Z. Written to the real radio (captures/names-1.log,
# 2026-11-11): it shows space, - + _ and 7 characters; the 8th byte is shown
# as a number (72 for "H"), so it is never used.
NAME_LEN = 7
NAME_BYTES = 8  # name row cleared to 0xff on 8 bytes (VA 0x48b8c9)
CTCSS = TONE_TABLE[1:51]
DCS = TONE_TABLE[51:]
# TX written for "no transmit" on a voice channel (ATIS): outside every band the
# radio transmits on, so a PTT does nothing (measured 2026-11-15: no carrier,
# no red PTT screen). 0xFF in the TX bytes does NOT stop it: the radio sent.
TX_OFF_HZ = 200_000_000
POWERS = ("HIGH", "LOW")
PTT_IDS = ("OFF", "BOT", "EOT", "BOTH")
OPT_SIGNALS = ("OFF", "DTMF", "2TONE", "5TONE")
SP_MUTES = ("QT", "AND", "OR")
NAME_RE = re.compile(r"[0-9A-Z +_-]{0,7}")


@dataclass(frozen=True)
class Channel:
    rx_hz: int
    tx_hz: int | None
    rx_tone: str
    tx_tone: str
    power: str
    narrow: bool
    ptt_id: str
    busy_lock: bool
    scan_add: bool
    sig_code: int | None
    opt_signal: str
    sp_mute: str
    scrambler: bool
    name: str


def _bcd_to_hz(raw):
    digits = ""
    for b in reversed(raw):
        hi, lo = b >> 4, b & 0xF
        if hi > 9 or lo > 9:
            return None
        digits += f"{hi}{lo}"
    return int(digits) * 10


def _hz_to_bcd(hz):
    if not isinstance(hz, int) or isinstance(hz, bool) or hz % 10:
        raise ValueError(f"frequency must be an integer multiple of 10 Hz: {hz!r}")
    units = hz // 10
    if not 1 <= units <= 99_999_999:
        raise ValueError(f"frequency out of range: {hz}")
    s = f"{units:08d}"
    return bytes(int(s[i : i + 2], 16) for i in (6, 4, 2, 0))


def _decode_tone(lo, hi):
    if (lo, hi) in ((0, 0), (0xFF, 0xFF)):
        return "OFF"
    if hi == 0:
        index = lo + 0x32  # table offset used by the CPS (VA 0x474fb8 branch)
        return TONE_TABLE[index] if index < len(TONE_TABLE) else "OFF"
    return f"{(hi << 8 | lo) / 10:.1f}"


def _encode_tone(tone):
    if tone == "OFF":
        return b"\x00\x00"  # what the CPS writes (captures/chan-written.img)
    if tone in DCS:
        return bytes([DCS.index(tone) + 1, 0])
    if tone in CTCSS:
        value = round(float(tone) * 10)
        return bytes([value & 0xFF, value >> 8])
    raise ValueError(f"unknown tone {tone!r}")


def _decode_name(raw):
    """ASCII up to 0xff; the radio pads its own names with spaces ("  WX01")."""
    out = ""
    for b in raw:
        if b <= 9:
            out += str(b)
        elif 0x20 <= b < 0x7F:
            out += chr(b)
        elif b == 0xFB:
            out += "+"
        elif b == 0xFD:
            out += "-"
    return out.strip()


def _pick(value, choices, label):
    if value not in choices:
        raise ValueError(f"{label} must be one of {choices}, got {value!r}")
    return choices.index(value)


def decode_channel(row, name):
    """Return a Channel, or None for an empty slot (RX byte 0 == 0xff)."""
    if len(row) != 16 or len(name) != NAME_BYTES:
        raise ValueError("row must be 16 bytes and name 8 bytes")
    if row[0] == 0xFF:
        return None
    sig = row[12] & 0x0F
    opt = row[13] & 0x0F
    mute = row[13] >> 4
    return Channel(
        rx_hz=_bcd_to_hz(row[0:4]),
        tx_hz=None if row[4] == 0xFF else _bcd_to_hz(row[4:8]),
        rx_tone=_decode_tone(row[8], row[9]),
        tx_tone=_decode_tone(row[10], row[11]),
        power=POWERS[row[14] & 0x07] if row[14] & 0x07 < 2 else "HIGH",
        narrow=bool(row[15] & 0x40),
        ptt_id=PTT_IDS[row[15] & 0x03],
        busy_lock=bool(row[15] & 0x08),
        scan_add=bool(row[15] & 0x04),
        sig_code=None if sig == 0x0F else sig + 1,  # CPS displays value + 1
        opt_signal=OPT_SIGNALS[opt] if opt < 4 else "OFF",
        sp_mute=SP_MUTES[mute] if mute < 3 else "QT",
        scrambler=bool(row[14] >> 4 == 1),
        name=_decode_name(name),
    )


def encode_channel(ch, old_row, old_name):
    """Return (row, name) bytes; unknown bits come from old_row."""
    if ch is None:
        return b"\xff" * 16, b"\xff" * NAME_BYTES
    if not isinstance(ch.name, str) or not NAME_RE.fullmatch(ch.name):
        raise ValueError(
            f"name must be 0-{NAME_LEN} characters 0-9 A-Z space - + _, got {ch.name!r}"
        )
    if not isinstance(ch.sig_code, (int, type(None))) or (
        ch.sig_code is not None and not 1 <= ch.sig_code <= 15
    ):
        raise ValueError(f"sig_code must be 1..15 or None, got {ch.sig_code!r}")
    # A new channel starts from zeros, as the CPS writes it.
    row = bytearray(16) if old_row[0] == 0xFF else bytearray(old_row)
    row[0:4] = _hz_to_bcd(ch.rx_hz)
    row[4:8] = b"\xff" * 4 if ch.tx_hz is None else _hz_to_bcd(ch.tx_hz)
    row[8:10] = _encode_tone(ch.rx_tone)
    row[10:12] = _encode_tone(ch.tx_tone)
    row[12] = (row[12] & 0xF0) | (0x0F if ch.sig_code is None else ch.sig_code - 1)
    row[13] = _pick(ch.sp_mute, SP_MUTES, "sp_mute") << 4 | _pick(
        ch.opt_signal, OPT_SIGNALS, "opt_signal"
    )
    row[14] = (
        (int(bool(ch.scrambler)) << 4)
        | (row[14] & 0x08)
        | _pick(ch.power, POWERS, "power")
    )
    row[15] = (
        (row[15] & 0xB0)
        | (0x40 if ch.narrow else 0)
        | (0x08 if ch.busy_lock else 0)
        | (0x04 if ch.scan_add else 0)
        | _pick(ch.ptt_id, PTT_IDS, "ptt_id")
    )
    name = ch.name.encode("ascii") + b"\xff" * (NAME_BYTES - len(ch.name))
    return bytes(row), name
