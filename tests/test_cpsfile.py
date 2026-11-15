"""CPS text files (.dat .menu .sig .adj): 1025 lines "A B N d0..d15" (captures/opt1.dat)."""

from pathlib import Path

import pytest

from kta16 import cpsfile
from kta16.image import Image

SAMPLE = Path(__file__).parent.parent / "captures" / "opt1.dat"


def test_dump_line_format():
    im = Image(bytes(range(256)) * 64)
    lines = cpsfile.dump(im).split(b"\r\n")
    assert len(lines) == 1026 and lines[-1] == b""
    assert (
        lines[0] == b" 0  0  0  0  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15 "
    )
    assert lines[17].startswith(b" 1  1  17  ")
    assert lines[1024] == b" 64  0  1024 " + b" 255 " * 16 or lines[1024].startswith(
        b" 64  0  1024 "
    )


def test_round_trip():
    im = Image(bytes((i * 7) & 0xFF for i in range(0x4000)))
    assert cpsfile.load(cpsfile.dump(im)).data == im.data


@pytest.mark.skipif(not SAMPLE.exists(), reason="capture not available")
def test_real_cps_file_loads_and_dumps_identically():
    raw = SAMPLE.read_bytes()
    assert cpsfile.dump(cpsfile.load(raw)) == raw
    assert cpsfile.load(raw).data[0xE00:0xE10] == bytes.fromhex(
        "00 03 05 00 00 04 01 00 01 00 01 00 02 02 02 00"
    )


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"abc",
        b" 0  0  0  1 \r\n",
        cpsfile.dump(Image()).replace(b" 255 ", b" 256 ", 1),
        cpsfile.dump(Image()).replace(b" 0  1  1 ", b" 0  1  2 ", 1),
        cpsfile.dump(Image())[:-200],
        b"\xff\xfe" * 50,
    ],
)
def test_load_rejects_corrupt(raw):
    with pytest.raises(ValueError):
        cpsfile.load(raw)


def test_suffixes():
    assert cpsfile.is_cps_file("a.DAT")
    for other in ("b.menu", "c.sig", "d.adj", "e.img"):
        assert not cpsfile.is_cps_file(other)  # other layouts, not supported


# First line of a file saved by the Adjust window of the CPS (sandbox,
# captures/def/cal.adj): 32 lines of 16 values, no header, CR LF.
ADJ_LINE = b" 13  12  12  12  12  12  15  14  14  14  14  14  14  14  14  14 \r\n"


def test_adj_round_trip_touches_only_calibration_and_passwords():
    src = Image(bytes((i * 3) & 0xFF for i in range(0x4000)))
    raw = cpsfile.dump_adj(src)
    assert raw.count(b"\r\n") == 32 and raw.endswith(b"\r\n")
    assert raw.split(b"\r\n")[0] == b"".join(
        f" {v} ".encode() for v in src.data[0x3C00:0x3C10]
    )
    dst = Image()
    merged = cpsfile.load_adj(raw, dst)
    assert merged.data[0x3C00:0x3E00] == src.data[0x3C00:0x3E00]
    assert merged.data[:0x3C00] == dst.data[:0x3C00]
    assert dst.data[0x3C00] == 0xFF  # input image left untouched


def test_adj_reads_the_cps_line_format():
    merged = cpsfile.load_adj(ADJ_LINE * 32, Image())
    assert merged.data[0x3C00:0x3C02] == bytes([13, 12])


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        ADJ_LINE * 31,
        ADJ_LINE * 33,
        ADJ_LINE.replace(b"13", b"256") * 32,
        ADJ_LINE.replace(b"13", b"-1") * 32,
        ADJ_LINE.replace(b"13", b"x") * 32,
        ADJ_LINE.replace(b" 14 \r\n", b"\r\n") * 32,
        "é".encode() * 40,
    ],
)
def test_adj_rejects_bad_files(raw):
    with pytest.raises(ValueError):
        cpsfile.load_adj(raw, Image())
