"""Every input example of the READMEs works in the TUI and appears in both."""

import asyncio
from pathlib import Path

import pytest

from kta16.emulator import FakeSerial, RadioEmulator
from kta16.tui import KTA16App

ROOT = Path(__file__).parent.parent
# (input box, text typed, address checked, expected bytes)
EXAMPLES = [
    ("#vfo-freq-0", "145.50000", 0x0F00, bytes([1, 4, 5, 5, 0, 0, 0, 0])),
    ("#vfo-offset-0", "000.600", 0x0F08, bytes([0, 0, 0, 6, 0, 0])),
    ("#vfo-rx-0", "88.5", 0x0F10, b"\x75\x03"),
    ("#vfo-tx-0", "D023N", 0x0F12, b"\x01\x00"),
    ("#tt-edit", "enc 1 1981 1124", 0x2D00, b"\xbd\x07"),
    ("#tt-edit", "dur 600 600 300", 0x2DF0, bytes([60, 60, 30])),
    ("#tt-edit", "reset 6000", 0x2FF0, bytes([59])),
    ("#ft-edit", "enc 1 12345 - - CCIR1", 0x2500, bytes([1, 2, 3, 4, 5])),
    ("#ft-edit", "delays 200 200 200 0", 0x25F0, bytes([20, 20, 20, 0])),
    ("#ft-edit", "dec CCIR1 1 23 6000", 0x25F8, bytes([0, 1, 6, 59])),
    ("#fm-edit", "1 98.3 RADIO", 0x3008, b"RADIO"),
    ("#cal-edit", "vox_threshold 0 127", 0x3DD0, bytes([127])),
    ("#poke", "0e02=06", 0x0E02, b"\x06"),
]

# Accepted commands: the box is emptied once the command is applied
ACCEPTED = [
    ("#tt-edit", "enc 2 -"),
    ("#tt-edit", "tones 1 1000 1500 - -"),
    ("#tt-edit", "dec 1 A-B 1 0 A-C 1 0 A-D 1 0 B-C 1 0"),
    ("#ft-edit", "tone 0 0 1981"),
    ("#ft-edit", "std 0 100 A E"),
    ("#fm-edit", "1 -"),
]


def run(examples):
    async def scenario():
        app = KTA16App(
            serial_factory=lambda: FakeSerial(RadioEmulator(bytearray(0x4000)))
        )
        async with app.run_test(size=(160, 50)) as pilot:
            for selector, text, addr, raw in examples:
                box = app.query_one(selector)
                box.value = text
                await box.action_submit()
                await pilot.pause()
                assert app.image.data[addr : addr + len(raw)] == raw, text

    asyncio.run(scenario())


def test_examples_work():
    run(EXAMPLES)


def test_accepted_examples():
    async def scenario():
        app = KTA16App()
        async with app.run_test(size=(160, 50)) as pilot:
            for selector, text in ACCEPTED:
                box = app.query_one(selector)
                box.value = text
                await box.action_submit()
                await pilot.pause()
                assert box.value == "", text

    asyncio.run(scenario())


@pytest.mark.parametrize("name", ["README.md", "README.fr.md"])
def test_examples_are_in_the_readme(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    texts = [t for _, t, _, _ in EXAMPLES] + [t for _, t in ACCEPTED]
    missing = [t for t in texts if t not in text]
    assert not missing, missing


@pytest.mark.parametrize("name", ["README.md", "README.fr.md"])
def test_relative_links_and_images_exist(name):
    import re

    text = (ROOT / name).read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text)
    missing = [
        link
        for link in links
        if not link.startswith("http") and not (ROOT / link).exists()
    ]
    assert not missing, missing
