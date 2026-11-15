"""FM broadcast channels, 16 rows of 16 bytes at 0x3000.

Bytes 0-7: frequency, one decimal digit per byte (088.90000 MHz);
bytes 8-15: station name, ASCII padded with 0xff. Empty: digits 0 and
name 0xff. Source: CPS "Default" + "Write" (docs/protocol.md).
"""

BASE = 0x3000
COUNT = 16
NAME_LEN = 8
# Broadcast band; step 100 kHz (hypothèse non vérifiée : limites non lues dans le CPS)
LOW_HZ, HIGH_HZ, STEP_HZ = 65_000_000, 108_000_000, 100_000


def _row(n):
    if not 1 <= n <= COUNT:
        raise ValueError(f"FM channel must be 1..{COUNT}")
    return BASE + 16 * (n - 1)


def get(data, n):
    a = _row(n)
    digits = data[a : a + 8]
    name = bytes(data[a + 8 : a + 16]).split(b"\xff")[0]
    if any(d > 9 for d in digits) or (not any(digits) and not name.strip(b"\0")):
        return None  # 0xff row (blank radio), zero digits (CPS Default, Clear)
    hz = int("".join(str(d) for d in digits)) * 10
    return hz, name.decode("ascii", errors="replace")


def set(data, n, hz, name):
    a = _row(n)
    if hz is None:
        data[a : a + 16] = bytes(8) + b"\xff" * 8
        return
    if not isinstance(hz, int) or not isinstance(name, str):
        raise TypeError("frequency must be int Hz and name a string")
    if not LOW_HZ <= hz <= HIGH_HZ or hz % STEP_HZ:
        raise ValueError(f"FM frequency must be {LOW_HZ}..{HIGH_HZ} Hz by 100 kHz")
    if len(name) > NAME_LEN or not name.isascii() or not name.isprintable():
        raise ValueError(f"FM name must be at most {NAME_LEN} ASCII characters")
    digits = bytes(int(c) for c in f"{hz // 10:08d}")
    data[a : a + 16] = digits + name.encode("ascii") + b"\xff" * (NAME_LEN - len(name))


def clear(data):
    """CPS "Clear" button: every row to zero."""
    data[BASE : BASE + 16 * COUNT] = bytes(16 * COUNT)
