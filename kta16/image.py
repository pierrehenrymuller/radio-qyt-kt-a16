"""Radio memory image (16 KiB) and the address ranges each CPS screen uses."""

import datetime
from dataclasses import dataclass
from pathlib import Path

from kta16 import channels
from kta16.protocol import IMAGE_SIZE


@dataclass(frozen=True)
class Region:
    name: str
    ranges: tuple  # ((start, end), ...) end excluded
    calibration: bool = False


# Bases and block counts from the comm routines of each screen
# (docs/protocol.md): reads are 64-byte blocks, writes 16-byte blocks.
CHANNELS = Region("channels", ((0x0000, 0x0C80), (0x1000, 0x1C80)))
OPTIONS = Region("options", ((0x0E00, 0x1000),))
FIVE_TONE = Region("5-tone", ((0x2000, 0x2600),))
DTMF = Region("dtmf", ((0x2900, 0x2B00),))
TWO_TONE = Region("2-tone", ((0x2D00, 0x3000),))
FM = Region("fm", ((0x3000, 0x3100),))
# The CPS writes calibration as 0x3C00..0x3DFF; the last 16 bytes are the
# password block, kept as a separate region here.
# The CPS "Adjust" write also sends the 16 bytes at 0x3B90 (captures).
CALIBRATION = Region(
    "calibration", ((0x3B90, 0x3BA0), (0x3C00, 0x3DF0)), calibration=True
)
PASSWORD = Region("password", ((0x3DF0, 0x3E00),))
PASSWORD_ADDR = 0x3DF0  # read first by the CPS (16-byte request, VA 0x483525)
# "Write to radio" of the CPS: 0x310 blocks of 16 from 0 (VA 0x5461a0);
# "Read from radio": 200 blocks of 64 from 0 (VA 0x53f270).
ALL = Region("all", ((0x0000, 0x3100),))
# Zones written together by the TUI batch write (no calibration, no password).
DATA_REGIONS = (CHANNELS, OPTIONS, FIVE_TONE, DTMF, TWO_TONE, FM)
REGIONS = (CHANNELS, OPTIONS, FIVE_TONE, DTMF, TWO_TONE, FM, CALIBRATION, PASSWORD, ALL)


def read_ranges(region):
    """Ranges widened to 64-byte read blocks (16 for the password block)."""
    if region is PASSWORD:
        return region.ranges
    return tuple((s & ~0x3F, (e + 0x3F) & ~0x3F) for s, e in region.ranges)


class Image:
    def __init__(self, data=None):
        data = bytes(data) if data is not None else b"\xff" * IMAGE_SIZE
        if len(data) != IMAGE_SIZE:
            raise ValueError(f"image must be {IMAGE_SIZE} bytes, got {len(data)}")
        self.data = bytearray(data)

    @classmethod
    def load(cls, path):
        return cls(Path(path).read_bytes())

    def save(self, path):
        Path(path).write_bytes(self.data)

    def backup(self, directory, label):
        """Timestamped copy, written before any radio write."""
        directory = Path(directory)
        # Backups hold the radio passwords: owner only.
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = directory / f"kta16-{label}-{stamp}.img"
        path.touch(mode=0o600)
        self.save(path)
        return path

    def channel(self, number):
        if not 1 <= number <= channels.CHANNEL_COUNT:
            raise ValueError(f"channel must be 1..{channels.CHANNEL_COUNT}")
        row = (number - 1) * 16
        return channels.decode_channel(
            bytes(self.data[row : row + 16]),
            bytes(self.data[0x1000 + row : 0x1000 + row + channels.NAME_BYTES]),
        )

    def swap_channels(self, a, b):
        """Exchange two channels byte for byte (undecoded bits follow the channel)."""
        for number in (a, b):
            if not (isinstance(number, int) and 1 <= number <= channels.CHANNEL_COUNT):
                raise ValueError(f"channel must be 1..{channels.CHANNEL_COUNT}")
        ra, rb = (a - 1) * 16, (b - 1) * 16
        for start, size in ((0, 16), (0x1000, channels.NAME_BYTES)):
            x, y = start + ra, start + rb
            self.data[x : x + size], self.data[y : y + size] = (
                bytes(self.data[y : y + size]),
                bytes(self.data[x : x + size]),
            )

    def insert_channels(self, start, new):
        """Put `new` channels on start, start+1, ...

        The free places right at `start` are used first. For the others, every
        channel after them moves on by the same number of places (gaps kept).
        Raises ValueError, with the image unchanged, when the last channel
        would go past the end of the list.
        """
        if not (isinstance(start, int) and 1 <= start <= channels.CHANNEL_COUNT):
            raise ValueError(f"channel must be 1..{channels.CHANNEL_COUNT}")
        last = channels.CHANNEL_COUNT
        free = 0
        while start + free <= last and self.channel(start + free) is None:
            free += 1
        shift = max(0, len(new) - free)
        occupied = [n for n in range(start + free, last + 1) if self.channel(n)]
        if start + len(new) - 1 > last or (occupied and occupied[-1] + shift > last):
            raise ValueError("no room left: the channels would go past the last one")
        for n in reversed(occupied):  # from the end: each target place is already empty
            self.swap_channels(n, n + shift)
        for place, ch in enumerate(new, start):
            self.set_channel(place, ch)

    def move_block(self, lo, hi, step):
        """Move channels lo..hi by `step` places; the channels crossed go to the other side."""
        count = channels.CHANNEL_COUNT
        ints = all(isinstance(v, int) for v in (lo, hi, step))
        if not ints or not (
            1 <= lo <= hi <= count and 1 <= lo + step and hi + step <= count
        ):
            raise ValueError(
                f"block {lo}..{hi} cannot move by {step} within 1..{count}"
            )
        for _ in range(abs(step)):  # one place at a time, byte for byte
            if step > 0:
                for n in range(hi, lo - 1, -1):
                    self.swap_channels(n, n + 1)
                lo, hi = lo + 1, hi + 1
            else:
                for n in range(lo, hi + 1):
                    self.swap_channels(n - 1, n)
                lo, hi = lo - 1, hi - 1

    def set_channel(self, number, ch):
        if not 1 <= number <= channels.CHANNEL_COUNT:
            raise ValueError(f"channel must be 1..{channels.CHANNEL_COUNT}")
        row = (number - 1) * 16
        name_at = 0x1000 + row
        new_row, new_name = channels.encode_channel(
            ch,
            bytes(self.data[row : row + 16]),
            bytes(self.data[name_at : name_at + channels.NAME_BYTES]),
        )
        self.data[row : row + 16] = new_row
        self.data[name_at : name_at + channels.NAME_BYTES] = new_name

    def clear_channels(self):
        """CPS "Clear" button of the channel window: rows and names to 0xff."""
        for start, end in CHANNELS.ranges:
            self.data[start:end] = b"\xff" * (end - start)

    def passwords(self):
        """Two 6-digit passwords at 0x3DF0 and 0x3DF6; six spaces = none."""
        raw = bytes(self.data[PASSWORD_ADDR : PASSWORD_ADDR + 12])
        return tuple(
            "" if part == b" " * 6 else part.decode("ascii", errors="replace")
            for part in (raw[:6], raw[6:])
        )

    def set_passwords(self, first, second):
        out = b""
        for pw in (first, second):
            if not isinstance(pw, str):
                raise TypeError("password must be a string")
            if pw and not (len(pw) == 6 and pw.isascii() and pw.isdigit()):
                raise ValueError("password must be empty or 6 digits (000000-999999)")
            out += pw.encode("ascii") if pw else b" " * 6
        self.data[PASSWORD_ADDR : PASSWORD_ADDR + 12] = out
