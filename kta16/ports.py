"""USB serial adapters the programming cable can show up as."""

from typing import NamedTuple

# Prolific PL2303: the chip of the KT-A16 programming cable (README).
RECOMMENDED = {(0x067B, 0x2303)}


class Adapter(NamedTuple):
    device: str
    label: str
    recommended: bool


def _clean(text):
    """Printable characters only, cut short: the text comes from the USB device."""
    return "".join(c for c in str(text or "") if c.isprintable())[:60]


def list_adapters(comports=None):
    """USB serial ports, the recommended cable first."""
    if comports is None:
        from serial.tools import list_ports

        comports = list_ports.comports
    found = []
    for p in comports():
        if p.vid is None:  # motherboard UARTs (ttyS*) have no USB id
            continue
        name = " ".join(
            _clean(x) for x in (p.manufacturer, p.description) if x and x != "n/a"
        )
        parts = (_clean(p.device), name, f"{p.vid:04x}:{(p.pid or 0):04x}")
        label = "  ".join(x for x in parts if x)
        found.append(Adapter(p.device, label, (p.vid, p.pid) in RECOMMENDED))
    return sorted(found, key=lambda a: not a.recommended)  # stable: keeps port order
