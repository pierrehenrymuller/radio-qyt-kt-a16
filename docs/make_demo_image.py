"""Write a demo memory image (channels and band limits) for screenshots, no radio needed.

PYTHONPATH=. python docs/make_demo_image.py demo.img
python -m kta16 --emulator demo.img
"""

import sys

from kta16 import aero, calibration, channels, image

# VHF0, VHF1, UHF0, UHF1 as the radio reports them (docs/protocol.md)
BAND_LIMITS = ((108, 136), (137, 174), (400, 520), (300, 336))


def channel(name, rx_hz, tx_hz, **kw):
    fields = {
        "rx_tone": "OFF", "tx_tone": "OFF", "power": "LOW", "narrow": False,
        "ptt_id": "OFF", "busy_lock": False, "scan_add": True, "sig_code": None,
        "opt_signal": "OFF", "sp_mute": "QT", "scrambler": False,
    }  # fmt: skip
    fields.update(kw)
    return channels.Channel(rx_hz=rx_hz, tx_hz=tx_hz, name=name, **fields)


def aero_channel(hit):
    """Channel of an aeronautical line, with the TX rule of the channel form."""
    rx = round(hit["mhz"] * 1e6)
    if aero.is_beacon(hit):
        tx = None
    elif aero.is_atis(hit):
        tx = channels.TX_OFF_HZ
    else:
        tx = rx
    return channel(hit["name"], rx, tx)


def build():
    im = image.Image()
    for row, (low, high) in enumerate(BAND_LIMITS):
        digits = [int(c) for c in f"{low:03d}{high:03d}"]
        a = calibration.BAND_LIMITS_ADDR + 16 * row
        im.data[a : a + 8] = bytes([*digits, 0, 1])
    first = {}  # the first frequency of each LFPG service: ATIS, TWR, GND, APP...
    for hit in aero.search(aero.load(), "LFPG"):
        first.setdefault(hit["name"].split()[-1], hit)
    hits = list(first.values())[:8] + aero.search(aero.load(), "VOR")[:2]
    demo = [aero_channel(h) for h in hits]
    demo += [
        channel("RANDO", 145_500_000, 145_500_000, rx_tone="88.5", tx_tone="88.5"),
        channel("BALISE", 145_600_000, 145_600_000, power="HIGH", narrow=True),
    ]
    for number, ch in enumerate(demo, 1):
        im.set_channel(number, ch)
    return im


if __name__ == "__main__":
    build().save(sys.argv[1] if len(sys.argv) > 1 else "demo.img")
