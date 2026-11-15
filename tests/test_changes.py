"""What a write would change: image against what the radio holds."""

from kta16 import changes, image, settings
from kta16.channels import Channel


def base():
    return image.Image()


def channel(name="LFPX", rx=122_500_000, power="LOW"):
    return Channel(
        rx, None, "OFF", "OFF", power, False, "OFF", False, True, None, "OFF", "QT",
        False, name,
    )  # fmt: skip


def test_no_change_no_entry():
    a = base()
    assert changes.diff(a, base(), {r.name for r in image.DATA_REGIONS}) == []


def test_channel_fields_listed_one_by_one():
    radio, cur = base(), base()
    radio.set_channel(3, channel(name="OLD", power="HIGH"))
    cur.set_channel(3, channel())
    found = changes.diff(cur, radio, {"channels"})
    fields = {c.field for c in found if c.zone == "channels"}
    assert {"name", "power"} <= fields
    name = next(c for c in found if c.field == "name")
    assert (name.item, name.old, name.new) == ("2", "OLD", "LFPX")


def test_new_channel_is_one_entry_with_its_name():
    radio, cur = base(), base()
    cur.set_channel(3, channel())
    found = [c for c in changes.diff(cur, radio, {"channels"}) if c.zone == "channels"]
    assert len(found) == 1 and (found[0].field, found[0].new) == ("canal", "LFPX")


def test_channel_deleted_is_one_entry():
    radio, cur = base(), base()
    radio.set_channel(3, channel())
    found = [c for c in changes.diff(cur, radio, {"channels"}) if c.zone == "channels"]
    assert len(found) == 1 and found[0].new == "(vide)"


def test_option_change_uses_cps_labels_and_values():
    radio, cur = base(), base()
    cur.data[0x0E02] = 6  # squelch 5 -> 6 on the real radio
    radio.data[0x0E02] = 5
    found = changes.diff(cur, radio, {"options"})
    entry = next(c for c in found if c.field == settings.FIELD_BY_KEY["squelch"].label)
    assert (entry.old, entry.new) == ("5", "6")


def test_other_zone_counts_bytes():
    radio, cur = base(), base()
    cur.data[0x2900:0x2905] = bytes([1, 2, 3, 4, 5])
    found = changes.diff(cur, radio, {"dtmf"})
    assert [(c.zone, c.field, c.new) for c in found] == [("dtmf", "octets", "5")]


def test_zone_never_read_is_announced_not_compared():
    cur = base()
    cur.data[0x2900] = 1
    found = changes.diff(cur, base(), set())
    dtmf = [c for c in found if c.zone == "dtmf"]
    assert len(dtmf) == 1 and dtmf[0].field == "jamais lue"


def test_passwords_and_calibration_are_not_listed():
    cur, radio = base(), base()
    cur.data[0x3DF0:0x3DF6] = b"123456"
    cur.data[0x3C00] = 9
    names = {
        c.zone for c in changes.diff(cur, radio, {r.name for r in image.DATA_REGIONS})
    }
    assert "password" not in names and "calibration" not in names


def test_frequencies_are_shown_in_mhz():
    radio, cur = base(), base()
    cur.set_channel(3, channel(rx=122_500_000))
    radio.set_channel(3, channel(rx=121_500_000))
    rx = next(c for c in changes.diff(cur, radio, {"channels"}) if c.field == "rx_hz")
    assert (rx.old, rx.new) == ("121.50000", "122.50000")


def test_tx_off_frequency_is_listed_as_disabled():
    radio, cur = base(), base()
    radio.set_channel(3, channel())
    ch = channel()
    cur.set_channel(3, Channel(**{**ch.__dict__, "tx_hz": 200_000_000}))
    (c,) = [c for c in changes.diff(cur, radio, {"channels"}) if c.field == "tx_hz"]
    assert c.new == "TX désactivé"
