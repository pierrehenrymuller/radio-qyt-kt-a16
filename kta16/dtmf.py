"""DTMF encode/decode screen, image 0x2900..0x2AFF.

Layout from the CPS "Default" + "Write" experiment (docs/protocol.md):
one DTMF digit per byte, 0xff ends a code. Digit codes from the encoder
0x519c60: '1'..'9' = 1..9, '0' = 10, '*' = 11, '#' = 12, 'A'..'C' = 13..15,
'D' = 0.
"""

BASE = 0x2900
CODE_COUNT = 15
CODE_LEN = 16
DIGITS = "D123456789" + "0*#ABC"  # index = stored value
FUNCTIONS = {  # 16-byte rows holding one code each
    "inspection": 0x2A00,
    "monitor": 0x2A10,
    "alarm": 0x2A20,
    "stun": 0x2A30,
    "kill": 0x2A40,
    "revive": 0x2A50,
    "master_id": 0x2AD0,
    "vice_id": 0x2AE0,
}
SPEED_ON, SPEED_OFF = 0x29F0, 0x29F1  # ms = 50 + 10 * value (seen: 3 -> 80)
MASTER_AND_VICE = 0x2AF0  # checkbox "master and vice ID"
RIGHTS = {"master": 0x2AF1, "vice": 0x2AF2}
# bits 0..4 in the column order of the CPS (each box ticked alone in the
# sandbox: Stun 0x04, Kill 0x08, Revive 0x10)
RIGHT_BITS = ("inspection", "monitor", "stun", "kill", "revive")
STATE = 0x2AF3  # State box: bit 0 RX Disable, bit 1 TX Disable (sandbox)
STATE_BITS = ("rx_disable", "tx_disable")
GROUP_CODE, SPACE_CODE = 0x2AF4, 0x2AF5
RESET_TIME, DELAY_TIME = 0x2AF6, 0x2AF7  # see reset_ms() and delay_ms()


def decode_digits(raw):
    out = ""
    for b in raw:
        if b >= len(DIGITS):
            break
        out += DIGITS[b]
    return out


def encode_digits(text, size=CODE_LEN):
    if not isinstance(text, str):
        raise TypeError("DTMF code must be a string")
    text = text.upper()
    if len(text) > size or any(c not in DIGITS for c in text):
        raise ValueError(f"DTMF code must be at most {size} of 0-9 A-D * #")
    return bytes(DIGITS.index(c) for c in text) + b"\xff" * (size - len(text))


def _row(n):
    if not 1 <= n <= CODE_COUNT:
        raise ValueError(f"code number must be 1..{CODE_COUNT}")
    return BASE + (n - 1) * 16


def get_code(data, n):
    a = _row(n)
    return decode_digits(data[a : a + CODE_LEN])


def set_code(data, n, text):
    a = _row(n)
    data[a : a + CODE_LEN] = encode_digits(text)


def get_function(data, name):
    a = FUNCTIONS[name]
    return decode_digits(data[a : a + CODE_LEN])


def set_function(data, name, text):
    a = FUNCTIONS[name]
    data[a : a + CODE_LEN] = encode_digits(text)


def speed_ms(value):
    return 50 + 10 * value


def get_rights(data, who):
    v = data[RIGHTS[who]]
    return {name for i, name in enumerate(RIGHT_BITS) if v >> i & 1}


def set_rights(data, who, rights):
    unknown = set(rights) - set(RIGHT_BITS)
    if unknown:
        raise ValueError(f"unknown rights {unknown}")
    a = RIGHTS[who]
    keep = data[a] & ~0x1F
    data[a] = keep | sum(1 << RIGHT_BITS.index(r) for r in rights)


def reset_ms(value):
    return 15600 + 100 * value


def delay_ms(value):
    return 100 * (value - 154)


def set_times(data, on_ms, off_ms, reset_ms, delay_ms):
    """Store the four DTMF times; formulas measured on the CPS lists."""
    raw = []
    for ms, base, step in (
        (on_ms, 50, 10),
        (off_ms, 50, 10),
        (reset_ms, 15600, 100),
        (delay_ms, -15400, 100),
    ):
        value, rest = divmod(ms - base, step)
        if rest or not 0 <= value <= 255:
            raise ValueError(f"time {ms} ms not available")
        raw.append(value)
    data[SPEED_ON], data[SPEED_OFF], data[RESET_TIME], data[DELAY_TIME] = raw


def times_ms(data):
    """DTMF speed on, speed off, reset time and delay, in ms."""
    return (
        speed_ms(data[SPEED_ON]),
        speed_ms(data[SPEED_OFF]),
        reset_ms(data[RESET_TIME]),
        delay_ms(data[DELAY_TIME]),
    )


def get_state(data):
    return {name for i, name in enumerate(STATE_BITS) if data[STATE] >> i & 1}


def set_state(data, flags):
    unknown = set(flags) - set(STATE_BITS)
    if unknown:
        raise ValueError(f"unknown state flags {unknown}")
    keep = data[STATE] & ~0x03
    data[STATE] = keep | sum(1 << STATE_BITS.index(f) for f in flags)
