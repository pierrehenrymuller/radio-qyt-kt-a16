"""Full-image text file of the vendor CPS (.dat).

Format read from a file saved by the CPS (captures/opt1.dat, writer VA
0x53ad40): 1025 lines ending with CR LF; line n holds " n//16 ", " n%16 ",
" n " then the 16 image bytes of row n in decimal, each value written as
" value ". Row 1024 lies past the 16 KiB image and is ignored on load.
"""

from kta16.image import Image
from kta16.protocol import IMAGE_SIZE

# The channel, option, DTMF, 2-tone, 5-tone and FM windows all save the
# full ".dat" (files saved in the sandbox). The Adjust window saves ".adj":
# 32 lines of 16 values, no header, image bytes 0x3C00..0x3DFF
# (calibration and passwords).
SUFFIXES = (".dat",)
ADJ_SUFFIX = ".adj"
ADJ_START, ADJ_ROWS = 0x3C00, 32
ROWS = IMAGE_SIZE // 16 + 1


def is_cps_file(path):
    return str(path).lower().endswith(SUFFIXES)


def dump(image):
    out = bytearray()
    for n in range(ROWS):
        row = image.data[n * 16 : n * 16 + 16] if n < ROWS - 1 else b"\xff" * 16
        values = [n // 16, n % 16, n, *row]
        out += "".join(f" {v} " for v in values).encode("ascii") + b"\r\n"
    return bytes(out)


def load(raw):
    try:
        lines = raw.decode("ascii").split("\r\n")
    except UnicodeDecodeError as exc:
        raise ValueError("not an ASCII CPS file") from exc
    if len(lines) != ROWS + 1 or lines[-1] != "":
        raise ValueError(f"expected {ROWS} lines, got {len(lines) - 1}")
    data = bytearray()
    for n, line in enumerate(lines[:ROWS]):
        try:
            values = [int(w) for w in line.split()]
        except ValueError as exc:
            raise ValueError(f"line {n + 1}: not numbers") from exc
        if len(values) != 19 or values[:3] != [n // 16, n % 16, n]:
            raise ValueError(f"line {n + 1}: bad header or length")
        if any(not 0 <= v <= 255 for v in values[3:]):
            raise ValueError(f"line {n + 1}: value out of 0..255")
        if n < ROWS - 1:
            data += bytes(values[3:])
    return Image(data)


def _line(values):
    return "".join(f" {v} " for v in values).encode("ascii") + b"\r\n"


def dump_adj(image):
    return b"".join(
        _line(image.data[ADJ_START + 16 * n : ADJ_START + 16 * n + 16])
        for n in range(ADJ_ROWS)
    )


def load_adj(raw, image):
    """Copy of `image` with 0x3C00..0x3DFF taken from an Adjust file."""
    try:
        lines = raw.decode("ascii").split("\r\n")
    except UnicodeDecodeError as exc:
        raise ValueError("not an ASCII CPS file") from exc
    if len(lines) != ADJ_ROWS + 1 or lines[-1] != "":
        raise ValueError(f"expected {ADJ_ROWS} lines, got {len(lines) - 1}")
    zone = bytearray()
    for n, line in enumerate(lines[:ADJ_ROWS]):
        try:
            values = [int(w) for w in line.split()]
        except ValueError as exc:
            raise ValueError(f"line {n + 1}: not numbers") from exc
        if len(values) != 16 or any(not 0 <= v <= 255 for v in values):
            raise ValueError(f"line {n + 1}: 16 values 0..255 expected")
        zone += bytes(values)
    out = Image(image.data)
    out.data[ADJ_START : ADJ_START + len(zone)] = zone
    return out
