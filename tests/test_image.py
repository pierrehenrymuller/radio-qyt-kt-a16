"""Memory image and radio transfers of whole regions."""

import itertools

import pytest

from kta16 import image as img
from kta16.channels import Channel
from kta16.emulator import FakeSerial, RadioEmulator
from kta16.link import Radio


def test_new_image_is_blank():
    im = img.Image()
    assert len(im.data) == 0x4000 and im.channel(1) is None


@pytest.mark.parametrize("data", [b"", bytes(0x3FFF), bytes(0x4001)])
def test_image_rejects_bad_size(data):
    with pytest.raises(ValueError):
        img.Image(data)


@pytest.mark.parametrize("n", [0, 201, -1])
def test_channel_number_range(n):
    with pytest.raises(ValueError):
        img.Image().channel(n)


def test_set_and_get_channel():
    im = img.Image()
    ch = Channel(
        446_006_250,
        446_006_250,
        "OFF",
        "OFF",
        "LOW",
        True,
        "OFF",
        False,
        True,
        None,
        "OFF",
        "QT",
        False,
        "PMR1",
    )
    im.set_channel(200, ch)
    assert im.channel(200).name == "PMR1"
    assert im.data[0x0C70:0x0C74] == bytes.fromhex("25 06 60 44")
    assert im.data[0x1C70:0x1C78] == b"PMR1\xff\xff\xff\xff"


def test_backup_and_load(tmp_path):
    im = img.Image(bytes(range(256)) * 64)
    path = im.backup(tmp_path / "bk", "before-write")
    assert img.Image.load(path).data == im.data


def test_read_ranges_are_block_aligned():
    assert img.read_ranges(img.CHANNELS) == ((0x0000, 0x0C80), (0x1000, 0x1C80))
    assert img.read_ranges(img.Region("x", ((0x0E10, 0x0E20),))) == ((0x0E00, 0x0E40),)


def test_regions_do_not_overlap_except_all():
    spans = sorted(r for reg in img.REGIONS if reg.name != "all" for r in reg.ranges)
    for (a0, a1), (b0, _) in itertools.pairwise(spans):
        assert a1 <= b0


def test_round_trip_through_emulator():
    src = bytearray(b"\xff" * 0x4000)
    emu = RadioEmulator(src)
    radio = Radio(FakeSerial(emu), timeout=0.2)
    radio.connect()
    im = img.Image()
    im.data[0x0E00:0x0E10] = bytes(range(16))
    for start, end in img.OPTIONS.ranges:
        radio.write_range(start, bytes(im.data[start:end]))
    back = radio.read_range(0x0E00, 0x0E40)
    assert back[:16] == bytes(range(16))


def test_passwords_blank_and_set():
    im = img.Image()
    im.data[0x3DF0:0x3DFC] = b" " * 12
    assert im.passwords() == ("", "")
    im.set_passwords("123456", "")
    assert bytes(im.data[0x3DF0:0x3DFC]) == b"123456      "
    assert im.passwords() == ("123456", "")


@pytest.mark.parametrize("pw", ["12345", "1234567", "12a456", "      ", 123456])
def test_passwords_rejected(pw):
    with pytest.raises((ValueError, TypeError)):
        img.Image().set_passwords(pw, "")


def test_backup_directory_is_private(tmp_path):
    # backups hold the radio passwords (0x3DF0)
    path = img.Image().backup(tmp_path / "backups", "test")
    assert (path.parent.stat().st_mode & 0o777) == 0o700
    assert (path.stat().st_mode & 0o077) == 0


def _chan(name, rx):
    return Channel(
        rx, rx, "OFF", "OFF", "LOW", False, "OFF", False, True, None, "OFF", "QT",
        False, name,
    )  # fmt: skip


def test_swap_channels_moves_rows_and_names_untouched():
    im = img.Image()
    im.set_channel(1, _chan("AAA", 122_500_000))
    im.set_channel(2, _chan("BBB", 123_450_000))
    im.data[0x0E] |= 0x08  # a bit the CPS does not decode: it follows the channel
    raw = bytes(im.data[0:16])
    im.swap_channels(1, 2)
    assert im.channel(1).name == "BBB" and im.channel(2).name == "AAA"
    assert bytes(im.data[16:32]) == raw  # byte for byte, undecoded bit included


def test_swap_with_an_empty_slot_and_with_itself():
    im = img.Image()
    im.set_channel(1, _chan("AAA", 122_500_000))
    im.swap_channels(1, 200)
    assert im.channel(1) is None and im.channel(200).name == "AAA"
    before = bytes(im.data)
    im.swap_channels(5, 5)
    assert bytes(im.data) == before


@pytest.mark.parametrize("a, b", [(0, 1), (1, 201), (-1, 2), (1, "2")])
def test_swap_channels_refuses_out_of_range(a, b):
    with pytest.raises((ValueError, TypeError)):
        img.Image().swap_channels(a, b)


def _names(im, first, last):
    return [
        None if im.channel(n) is None else im.channel(n).name
        for n in range(first, last + 1)
    ]


def test_insert_into_free_slots_moves_nothing():
    im = img.Image()
    im.set_channel(9, _chan("KEEP", 118_000_000))
    im.insert_channels(5, [_chan(f"N{i}", 120_000_000) for i in range(3)])
    assert _names(im, 5, 9) == ["N0", "N1", "N2", None, "KEEP"]


def test_insert_uses_the_free_places_then_moves_every_following_channel():
    # User rule: 10 to add, 3 free places, the 7 others move all the next channels.
    im = img.Image()
    for i, n in enumerate(range(8, 13)):  # A..E on 8..12, gap 13-14, F on 15
        im.set_channel(n, _chan("ABCDE"[i], 118_000_000))
    im.set_channel(15, _chan("F", 118_000_000))
    im.data[7 * 16 + 14] |= 0x08  # undecoded bit of A: follows the channel
    raw_a = bytes(im.data[7 * 16 : 8 * 16])
    im.insert_channels(5, [_chan(f"N{i}", 120_000_000) for i in range(10)])
    assert _names(im, 5, 14) == [f"N{i}" for i in range(10)]
    # shift = 10 - 3 free places = 7, the two empty places after E are kept
    assert _names(im, 15, 22) == ["A", "B", "C", "D", "E", None, None, "F"]
    assert bytes(im.data[14 * 16 : 15 * 16]) == raw_a


def test_insert_without_room_changes_nothing():
    im = img.Image()
    for n in range(2, 201):
        im.set_channel(n, _chan("X", 118_000_000))
    before = bytes(im.data)
    with pytest.raises(ValueError):
        im.insert_channels(1, [_chan("A", 120_000_000), _chan("B", 120_000_000)])
    assert bytes(im.data) == before


@pytest.mark.parametrize("start", [0, 201, "3"])
def test_insert_refuses_a_bad_start(start):
    with pytest.raises((ValueError, TypeError)):
        img.Image().insert_channels(start, [_chan("A", 120_000_000)])


def _four(names=("A", "B", "C", "D")):
    im = img.Image()
    for n, name in enumerate(names, 1):
        im.set_channel(n, _chan(name, 118_000_000 + n * 1000))
    return im


def test_move_block_down_and_up_swaps_the_neighbour_to_the_other_side():
    im = _four()
    im.data[14] |= 0x08  # undecoded bit of channel 1: follows it
    raw_a = bytes(im.data[0:16])
    im.move_block(1, 2, 1)  # A B down one place
    assert _names(im, 1, 4) == ["C", "A", "B", "D"]
    assert bytes(im.data[16:32]) == raw_a
    im.move_block(2, 3, -1)  # and back up
    assert _names(im, 1, 4) == ["A", "B", "C", "D"]


def test_move_block_over_several_places_crosses_empty_channels_too():
    im = img.Image()
    for n, name in ((1, "A"), (2, "B"), (5, "E")):
        im.set_channel(n, _chan(name, 118_000_000))
    im.move_block(1, 2, 3)  # A B go to 4 5, E goes to 1..3 side
    assert _names(im, 1, 6) == [None, None, "E", "A", "B", None]


@pytest.mark.parametrize(
    "lo, hi, step", [(1, 2, -1), (199, 200, 1), (3, 2, 1), (0, 1, 1), (1, 1, 200)]
)
def test_move_block_refuses_what_leaves_the_list(lo, hi, step):
    im = _four()
    before = bytes(im.data)
    with pytest.raises(ValueError):
        im.move_block(lo, hi, step)
    assert bytes(im.data) == before
