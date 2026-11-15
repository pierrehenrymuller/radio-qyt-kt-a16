"""5-tone screen, image 0x2000..0x25FF (CPS "Default" + "Write", docs/protocol.md).

Standards s = 0..14, 16 tones each (digits 0..F): frequency low bytes at
0x2000+16s, high bytes at 0x2100+16s, coefficient low/high at 0x2200/0x2300
(same formula as 2-tone); 0x2400+16s = period, group tone, repeat tone.
Encode codes at 0x2500+16(n-1): 3 frames of 5 hex digits, then the standard.
"""

from kta16.twotone import COEF_DEN, COEF_NUM, HIGH_HZ, LOW_HZ

STANDARDS = (
    "CCIR1", "CCIR2", "PCCIR", "ZVEI1", "ZVEI2", "ZVEI3", "PZVEI", "DZVEI",
    "PDZVEI", "EEA", "EIA", "EURO", "CCITT", "NATEL", "MODAT",
)  # fmt: skip
FREQ_LO, FREQ_HI, COEF_LO, COEF_HI, PARAMS = 0x2000, 0x2100, 0x2200, 0x2300, 0x2400
ENCODE, CODE_COUNT, FRAME_LEN = 0x2500, 15, 5
DELAYS = 0x25F0  # delay 1..3 and first digit extend, units of 10 ms
DECODE_STD, DECODE_CALL, DECODE_DISP, DECODE_RESET = 0x25F8, 0x25F9, 0x25FA, 0x25FB
HEX = "0123456789ABCDEF"


def _std(s):
    if not 0 <= s < len(STANDARDS):
        raise ValueError(f"standard index must be 0..{len(STANDARDS) - 1}")
    return 16 * s


def get_tones(data, s):
    o = _std(s)
    out = []
    for i in range(16):
        v = data[FREQ_LO + o + i] | data[FREQ_HI + o + i] << 8
        out.append(None if v == 0xFFFF else v)
    return out


def set_tone(data, s, i, hz):
    o = _std(s)
    if not 0 <= i < 16:
        raise ValueError("tone index must be 0..15")
    if not isinstance(hz, int) or not LOW_HZ <= hz <= HIGH_HZ:
        raise ValueError(f"tone must be {LOW_HZ}..{HIGH_HZ} Hz")
    coef = int(hz * COEF_NUM / COEF_DEN + 0.5)
    data[FREQ_LO + o + i], data[FREQ_HI + o + i] = hz & 0xFF, hz >> 8
    data[COEF_LO + o + i], data[COEF_HI + o + i] = coef & 0xFF, coef >> 8


def get_standard_params(data, s):
    """(period ms, group tone, repeat tone); period = 20 + 10 * value."""
    a = PARAMS + _std(s)
    return 20 + 10 * data[a], HEX[data[a + 1] & 0xF], HEX[data[a + 2] & 0xF]


def set_standard_params(data, s, period_ms, group, repeat):
    a = PARAMS + _std(s)
    if (
        not isinstance(period_ms, int)
        or (period_ms - 20) % 10
        or not 20 <= period_ms <= 2570
    ):
        raise ValueError("period must be 20..2570 ms by 10 ms")
    if group not in HEX or repeat not in HEX or len(group) != 1 or len(repeat) != 1:
        raise ValueError("group and repeat tones are one hex digit")
    data[a : a + 3] = bytes(
        [(period_ms - 20) // 10, HEX.index(group), HEX.index(repeat)]
    )


def _code(n):
    if not 1 <= n <= CODE_COUNT:
        raise ValueError(f"code must be 1..{CODE_COUNT}")
    return ENCODE + 16 * (n - 1)


def get_encode(data, n):
    a = _code(n)
    frames = []
    for f in range(3):
        raw = data[a + 5 * f : a + 5 * f + 5]
        frames.append("" if raw[0] > 0xF else "".join(HEX[b & 0xF] for b in raw))
    std = data[a + 15]
    return (*frames, STANDARDS[std] if std < len(STANDARDS) else "")


def set_encode(data, n, code):
    a = _code(n)
    *frames, std = code
    raw = bytearray()
    for frame in frames:
        frame = frame.upper()
        if frame and (len(frame) != FRAME_LEN or any(c not in HEX for c in frame)):
            raise ValueError("a frame is empty or 5 hex digits (0-9 A-F)")
        raw += bytes(HEX.index(c) for c in frame) if frame else b"\xff" * FRAME_LEN
    if std not in STANDARDS:
        raise ValueError(f"unknown standard {std!r}")
    data[a : a + 16] = raw + bytes([STANDARDS.index(std)])


def delays_ms(data):
    return tuple(10 * data[DELAYS + i] for i in range(4))


def decode_settings(data):
    """(decode standard, frames that call, frames displayed)."""
    bits = lambda v: {f + 1 for f in range(3) if v >> f & 1}
    std = data[DECODE_STD]
    return (
        STANDARDS[std] if std < len(STANDARDS) else "",
        bits(data[DECODE_CALL]),
        bits(data[DECODE_DISP]),
    )


# Tables written by the vendor CPS on every "Write to radio" (0x2000..0x23EF),
# read back from the real radio after such a write (captures).
DEFAULT_TABLES = bytes.fromhex(
    "bd64adfb4ea60468d34460a2c7df3e1f"
    "bd64adfb4ea60468d34460a2c7df3e1f"
    "bd64adfb4ea60468d3441aa260df3e00"
    "602488f678fa8626d098f02aca7528a8"
    "602488f678fa8626d098752ae4a8ca28"
    "98ca2488f678fa8626d0750000006000"
    "602488f678fa8626d098ca2af07528a8"
    "98ca2488f678fa8626d039e4287560a8"
    "98ca2488f678fa8626d0397628586000"
    "bd64adfb4ea60468d3441fa260df3ec7"
    "58e572ff8c19a633c04d6781daf4cb43"
    "d38740ffc38c592afed6000000002600"
    "90b90254adb937c561086cd03498fc00"
    "6177b90254ad10b938c5cb3b9d850d86"
    "9113a93fd56b01972dc300000000e700"
    "ffffffffffffffffffffffffffffffff"
    "07040404050506060607090308030804"
    "07040404050506060607090308030804"
    "07040404050506060607040309030800"
    "090404040505060707080a0303030a02"
    "0904040405050607070803030202030a"
    "08030404040505060707030000000900"
    "0904040405050607070803030a030a02"
    "0803040404050506070703020a030902"
    "0803040404050506070703030a030900"
    "07040404050506060607040309030808"
    "02020303040505060607080907080104"
    "03030302020202020101000000000400"
    "01020303030405050607070708080800"
    "0602020303030404050507020809070a"
    "02030304040506060707000000000100"
    "ffffffffffffffffffffffffffffffff"
    "b7f9091a2d40556b839c14cef2dbd4ea"
    "b7f9091a2d40556b839c14cef2dbd4ea"
    "b7f9091a2d40556b839ce8ce14dbd499"
    "14eb011936537295bbe76db3d7c44096"
    "14eb011936537295bbe7c4b3a496d740"
    "e7d7eb011936537295bbc49999991499"
    "14eb011936537295bbe7d7b36dc44096"
    "e7d7eb011936537295bbb6a440c41496"
    "e7d7eb011936537295bbb6c440bd1499"
    "b7f9091a2d40556b839ceace14dbd4f2"
    "85a4c3e2022140607f9edd1bbdfc65f1"
    "d9c8b8aa9c90857a716899999999eb99"
    "589aaabcd00c28476a8fa5bbd1e7fe99"
    "6a8b9aaabcd0e60c2847ba7ee91c9055"
    "91aecff11233557697b8429999996c99"
    "ffffffffffffffffffffffffffffffff"
    "01000101010101010101020001000100"
    "01000101010101010101020001000100"
    "01000101010101010101000002000102"
    "02000101010101010101020000000200"
    "02000101010101010101000000000002"
    "01000001010101010101000202020202"
    "02000101010101010101000002000200"
    "01000001010101010101000002000200"
    "01000001010101010101000002000202"
    "01000101010101010101000002000101"
    "00000000010101010101010201010000"
    "00000000000000000000020202020002"
    "00000000000101010101010101010102"
    "01000000000000010101010001020102"
    "00000000010101010101000202020002"
)


def install_default_tables(data):
    """Regenerate the standard tone tables as the vendor CPS does when it writes."""
    data[FREQ_LO : FREQ_LO + len(DEFAULT_TABLES)] = DEFAULT_TABLES


def set_delays_ms(data, delay1, delay2, delay3, first_digit):
    """Delay 1..3 and first digit extend, in ms (stored in units of 10 ms)."""
    values = (delay1, delay2, delay3, first_digit)
    if any(not isinstance(v, int) or v % 10 or not 0 <= v <= 2550 for v in values):
        raise ValueError("delays must be 0..2550 ms by 10 ms")
    data[DELAYS : DELAYS + 4] = bytes(v // 10 for v in values)


def set_decode_settings(data, standard, call_frames, disp_frames, reset_raw):
    """Decode standard, frames that call / are displayed (1..3), raw reset byte."""
    if standard not in STANDARDS:
        raise ValueError(f"unknown standard {standard!r}")
    if not (set(call_frames) | set(disp_frames)) <= {1, 2, 3}:
        raise ValueError("frames are 1, 2 or 3")
    if not isinstance(reset_raw, int) or not 0 <= reset_raw <= 255:
        raise ValueError("reset value must be 0..255")
    bits = lambda frames: sum(1 << (f - 1) for f in frames)
    data[DECODE_STD : DECODE_STD + 4] = bytes(
        [STANDARDS.index(standard), bits(call_frames), bits(disp_frames), reset_raw]
    )
