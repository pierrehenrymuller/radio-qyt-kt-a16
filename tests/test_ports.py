"""Listing of the USB serial adapters offered at startup."""

from types import SimpleNamespace

from kta16 import ports


def com(device, vid, pid, description="n/a", manufacturer=None):
    return SimpleNamespace(
        device=device,
        vid=vid,
        pid=pid,
        description=description,
        manufacturer=manufacturer,
    )


def test_empty_list():
    assert ports.list_adapters(list) == []


def test_motherboard_uarts_are_hidden():
    assert ports.list_adapters(lambda: [com("/dev/ttyS0", None, None)]) == []


def test_prolific_is_recommended_and_first():
    found = ports.list_adapters(
        lambda: [
            com("/dev/ttyUSB0", 0x1A86, 0x7523, "USB Serial"),
            com("/dev/ttyUSB1", 0x067B, 0x2303, "USB-Serial Controller D", "Prolific"),
        ]
    )
    assert [a.device for a in found] == ["/dev/ttyUSB1", "/dev/ttyUSB0"]
    assert [a.recommended for a in found] == [True, False]
    assert "067b:2303" in found[0].label


def test_other_brand_is_listed_not_recommended():
    (a,) = ports.list_adapters(lambda: [com("/dev/ttyUSB0", 0x10C4, 0xEA60)])
    assert not a.recommended


def test_missing_pid_does_not_crash():
    (a,) = ports.list_adapters(lambda: [com("/dev/ttyACM0", 0x1234, None)])
    assert not a.recommended


def test_hostile_description_is_cleaned():
    (a,) = ports.list_adapters(
        lambda: [com("/dev/ttyUSB0", 1, 2, "x\x1b[2J\nbad", "A" * 500)]
    )
    assert "\x1b" not in a.label and "\n" not in a.label
    assert len(a.label) < 200
