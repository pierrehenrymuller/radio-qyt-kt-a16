"""What a write would change: the image against what the radio holds.

The radio content is known only where this session read or wrote it: a zone
never read is announced as a whole, not compared. Passwords and calibration
are not listed: they are written only by their own tabs.
"""

from dataclasses import dataclass, fields

from kta16 import channels, image, settings
from kta16.i18n import t

NEVER_READ = "jamais lue"
COUNT_FIELD = "octets"  # marker of a zone shown as a byte count, not displayed
CHANNEL_ITEM = "canal"  # marker of an added or deleted channel, not displayed


@dataclass(frozen=True)
class Change:
    zone: str  # name of an image zone, e.g. "channels", "options", "dtmf"
    item: str  # "" for a zone, else the channel number (from 0) or the field
    field: str
    old: str
    new: str


def _text(value):
    if value is None:
        return t("chg_empty")
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


def _channel_value(name, value):
    if name == "tx_hz" and value == channels.TX_OFF_HZ:
        return t("chg_tx_off")
    if name.endswith("_hz"):
        return t("chg_empty") if value is None else f"{value / 1e6:.5f}"
    return _text(value)


def _channel_changes(cur, radio, n):
    a, b = cur.channel(n), radio.channel(n)
    if a == b:
        return []
    if a is None or b is None:  # added or deleted: one entry, with the name
        old = t("chg_empty") if b is None else b.name
        new = t("chg_empty") if a is None else a.name
        return [Change("channels", str(n - 1), CHANNEL_ITEM, old, new)]
    out = []
    for f in fields(a):
        old, new = getattr(b, f.name), getattr(a, f.name)
        if old != new:
            out.append(
                Change(
                    "channels",
                    str(n - 1),
                    f.name,
                    _channel_value(f.name, old),
                    _channel_value(f.name, new),
                )
            )
    return out


def _option_changes(cur, radio):
    out = []
    for f in settings.FIELDS:
        old, new = f.get(radio.data), f.get(cur.data)
        if old != new:
            out.append(Change("options", "", f.label, f.label_of(old), f.label_of(new)))
    return out


def _zone_bytes(cur, radio, region):
    count = 0
    for start, end in region.ranges:
        count += sum(cur.data[i] != radio.data[i] for i in range(start, end))
    return count


def diff(cur, radio, known):
    """Changes between the image `cur` and the radio content `radio`.

    `known` names the zones this session read or wrote; the others are
    listed as never read.
    """
    out = []
    for region in image.DATA_REGIONS:
        if region.name not in known:
            if cur.data[region.ranges[0][0] : region.ranges[-1][1]] != bytes(
                radio.data[region.ranges[0][0] : region.ranges[-1][1]]
            ):
                out.append(Change(region.name, "", NEVER_READ, "", COUNT_FIELD))
            continue
        if region is image.CHANNELS:
            for n in range(1, channels.CHANNEL_COUNT + 1):
                out += _channel_changes(cur, radio, n)
        elif region is image.OPTIONS:
            out += _option_changes(cur, radio)
        else:
            count = _zone_bytes(cur, radio, region)
            if count:
                out.append(Change(region.name, "", COUNT_FIELD, "", str(count)))
    return out
