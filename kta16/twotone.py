"""2-tone encode/decode screen, image 0x2D00..0x2FFF.

Layout from the CPS "Default" + "Write" experiment and the screen
(docs/protocol.md). Frequencies are integer Hz, 16-bit little-endian,
0xffff = empty; 300..3000 Hz ("Frequency range 300Hz to 3000Hz").
"""

COUNT = 15
ENCODE, DURATIONS, DECODE, TONES, RESET = 0x2D00, 0x2DF0, 0x2E00, 0x2F00, 0x2FF0
PAIRS = (
    "A-B",
    "A-C",
    "A-D",
    "B-A",
    "B-C",
    "B-D",
    "C-A",
    "C-B",
    "C-D",
    "D-A",
    "D-B",
    "D-C",
)
RESPONSES = ("0.None", "1.Alert", "2.Transpond", "3.Alert+Transpond")
LOW_HZ, HIGH_HZ = 300, 3000
# coefficient stored after the 4 tones (encoder 0x523e60, constant 18466.0)
COEF_NUM, COEF_DEN = 4096, 18466


def _row(base, n):
    if not 1 <= n <= COUNT:
        raise ValueError(f"code must be 1..{COUNT}")
    return base + 16 * (n - 1)


def _u16(data, a):
    v = data[a] | data[a + 1] << 8
    return None if v == 0xFFFF else v


def _put_hz(data, a, hz):
    if hz is None:
        data[a : a + 2] = b"\xff\xff"
        return
    if not isinstance(hz, int) or isinstance(hz, bool):
        raise TypeError("frequency must be an integer number of Hz")
    if not LOW_HZ <= hz <= HIGH_HZ:
        raise ValueError(f"frequency must be {LOW_HZ}..{HIGH_HZ} Hz")
    data[a : a + 2] = hz.to_bytes(2, "little")


def get_encode(data, n):
    a = _row(ENCODE, n)
    pair = (_u16(data, a), _u16(data, a + 8))
    return None if pair == (None, None) else pair


def set_encode(data, n, pair):
    a = _row(ENCODE, n)
    first, second = pair if pair else (None, None)
    _put_hz(data, a, first)
    _put_hz(data, a + 8, second)


def durations_ms(data):
    """1st tone, 2nd tone, gap, in ms (stored in units of 10 ms)."""
    return tuple(10 * data[DURATIONS + i] for i in range(3))


def set_durations_ms(data, first, second, gap):
    for i, ms in enumerate((first, second, gap)):
        if not isinstance(ms, int) or ms % 10 or not 0 <= ms <= 2550:
            raise ValueError("durations must be 0..2550 ms by 10 ms")
        data[DURATIONS + i] = ms // 10


def get_decode(data, n):
    a = _row(DECODE, n)
    out = []
    for k in range(4):
        pair, resp, alert = data[a + 3 * k : a + 3 * k + 3]
        if pair >= len(PAIRS):
            out.append(None)
            continue
        out.append((PAIRS[pair], RESPONSES[resp] if resp < 4 else f"{resp}?", alert))
    return out


def set_decode(data, n, entries):
    a = _row(DECODE, n)
    raw = bytearray()
    for entry in entries:
        if entry is None:
            raw += b"\xff\xff\xff"
            continue
        pair, resp, alert = entry
        if pair not in PAIRS or resp not in RESPONSES or not 0 <= alert <= 255:
            raise ValueError(f"invalid decode entry {entry!r}")
        raw += bytes([PAIRS.index(pair), RESPONSES.index(resp), alert])
    if len(raw) != 12:
        raise ValueError("4 decode entries expected")
    data[a : a + 12] = raw


def get_tones(data, n):
    a = _row(TONES, n)
    return tuple(_u16(data, a + 2 * k) for k in range(4))


def set_tones(data, n, tones):
    a = _row(TONES, n)
    for k, hz in enumerate(tones):
        _put_hz(data, a + 2 * k, hz)
        coef = 0xFFFF if hz is None else int(hz * COEF_NUM / COEF_DEN + 0.5)
        data[a + 8 + 2 * k : a + 10 + 2 * k] = coef.to_bytes(2, "little")


def reset_ms(value):
    """Reset time of the 2-tone and 5-tone decoders: CPS lists 100..8000 ms."""
    return 100 * (value + 1)


def reset_value(ms):
    """Byte for a reset time; formula measured on CPS writes (sandbox)."""
    if not isinstance(ms, int) or isinstance(ms, bool):
        raise TypeError("reset time must be an int in ms")
    if ms % 100 or not 100 <= ms <= 8000:
        raise ValueError("reset time must be 100..8000 ms by 100 ms")
    return ms // 100 - 1


def reset_raw(data):
    """Reset_Time byte (0x3b = 6000 ms, see reset_ms)."""
    return data[RESET]


def set_reset_raw(data, value):
    if not isinstance(value, int) or not 0 <= value <= 255:
        raise ValueError("reset value must be 0..255")
    data[RESET] = value
