"""Option ("Optional Features") fields, one byte each, value = list index.

Addresses and value lists come from experiments on the vendor CPS against
the emulator (docs/protocol.md, section options): binary-coded reads,
"Default" + "Write", and drop-down lists captured on screen.
"""

from dataclasses import dataclass

from kta16 import channels

COLORS = (
    "White",
    "Red",
    "Blue",
    "Green",
    "Yellow",
    "Indigo",
    "Purple",
    "Gray",
    "Black",
)
OFF_ON = ("OFF", "ON")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    addr: int
    choices: tuple  # label of value 0, 1, ...
    first: int = 0  # value of choices[0] (TMR Return AB stores 10 for "10")
    ascending: bool = False  # show the list by increasing number, not by stored value

    def options(self):
        options = [(self.first + i, c) for i, c in enumerate(self.choices)]
        if self.ascending:
            options.sort(key=lambda option: float(option[1]))
        return options

    def label_of(self, value):
        i = value - self.first
        return self.choices[i] if 0 <= i < len(self.choices) else f"{value:#04x} ?"

    def get(self, data):
        return data[self.addr]

    def set(self, data, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{self.key}: integer expected, got {value!r}")
        if not 0 <= value - self.first < len(self.choices):
            raise ValueError(f"{self.key}: value {value} not in list")
        data[self.addr] = value


FIELDS = (
    Field(
        "tmr",
        "TMR",
        0x0E00,
        ("OFF", "M+A", "M+B", "M+C", "M+A+B", "M+A+C", "M+B+C", "M+A+B+C"),
    ),
    Field("squelch", "Squelch Level", 0x0E02, tuple(str(i) for i in range(10))),
    Field("vox", "VOX", 0x0E03, ("OFF",) + tuple(str(i) for i in range(1, 10))),
    Field("auto_lock", "Auto Lock", 0x0E04, OFF_ON),
    Field(
        "tot",
        "Time Out Timer (s)",
        0x0E05,
        ("OFF",) + tuple(str(15 * i) for i in range(1, 41)),
    ),
    Field("save", "Save", 0x0E06, ("OFF", "1:1", "1:2", "1:3", "1:4")),
    Field("abr", "ABR", 0x0E07, ("OFF",) + tuple(str(i) for i in range(1, 11))),
    Field("beep", "Beep", 0x0E08, OFF_ON),
    Field("bcl", "BCL", 0x0E09, OFF_ON),
    Field("scan_add", "Scan Add", 0x0E0A, OFF_ON),
    Field("scan_rev", "Scan_Rev", 0x0E0B, ("TO", "CO", "SE")),
    Field("voice", "Voice", 0x0E0F, ("OFF", "English", "Chinese")),
    Field("color_above_stat", "Above Stat Fore Color", 0x0E10, COLORS),
    Field("color_main", "Main Fore Color", 0x0E11, COLORS),
    Field("color_main_sub", "Main sub Fore Color", 0x0E12, COLORS),
    Field("color_a", "A - Fore Color", 0x0E13, COLORS),
    Field("color_b", "B - Fore Color", 0x0E14, COLORS),
    Field("color_c", "C - Fore Color", 0x0E15, COLORS),
    Field("color_batt", "BATT Fore Color", 0x0E16, COLORS),
    Field("color_signal", "Signale Fore Color", 0x0E17, COLORS),
    Field("color_menu", "Menu Fore Color", 0x0E18, COLORS),
    Field("color_tx", "TX Fore Color", 0x0E19, COLORS),
    Field("color_rx", "RX Fore Color", 0x0E1A, COLORS),
    Field(
        "tmr_return_ab",
        "TMR Return AB",
        0x0E1F,
        tuple(str(i) for i in range(10, 61)),
        first=10,
    ),
    Field("tx_for_tmr", "TX for TMR", 0x0E20, ("Track", "Fixed")),
)


def _vfo_fields(letter, base):
    key, name = f"vfo_{letter.lower()}", letter
    return (
        Field(
            f"{key}_sp_mute",
            f"{name} Speak Mute",
            base + 0x15,
            ("QT/DQT", "QT/DQT AND OPTSIG", "QT/DQT OR OPTSIG"),
        ),
        Field(
            f"{key}_opt_signal", f"{name} Optional Signal", base + 0x16, ("OFF", "FSK")
        ),
        Field(f"{key}_narrow", f"{name} W/N", base + 0x18, ("WIDE", "NARROW")),
        Field(f"{key}_power", f"{name} TX Power", base + 0x19, ("HIGH", "LOW")),
        Field(f"{key}_sft_d", f"{name} SFT_D", base + 0x1A, ("OFF", "+", "-")),
        Field(
            f"{key}_step",
            f"{name} Step Frequency (kHz)",
            base + 0x1B,
            # 0..5: list of the CPS. 6 = 8.33 kHz, outside the CPS list (confirmed on
            # the radio screen for lines A and C)
            ("2.50", "5.00", "6.25", "10.00", "12.50", "25.00", "8.33"),
            ascending=True,
        ),
    )


# VFO blocks: A at 0x0F00, B at 0x0F20, C at 0x0F40 (checked on the CPS screen)
VFOS = ("A", "B", "C")
FIELDS += tuple(
    f for i, v in enumerate(VFOS) for f in _vfo_fields(v, 0x0F00 + 0x20 * i)
)
FIELD_BY_KEY = {f.key: f for f in FIELDS}

# VFO blocks of 32 bytes: index 0, 1, 2 = A, B, C
VFO_BASE = 0x0F00


def _digits_text(data, a, int_len, frac_len):
    d = data[a : a + int_len + frac_len]
    text = "".join(str(x) if x <= 9 else "?" for x in d)
    return f"{text[:int_len]}.{text[int_len:]}"


def _set_digits(data, a, text, int_len, frac_len):
    whole, _, frac = text.partition(".")
    if len(whole) != int_len or len(frac) != frac_len or not (whole + frac).isdigit():
        raise ValueError(f"expected {'9' * int_len}.{'9' * frac_len}, got {text!r}")
    data[a : a + int_len + frac_len] = bytes(int(c) for c in whole + frac)


def vfo_frequency(data, vfo):
    return _digits_text(data, VFO_BASE + 0x20 * vfo, 3, 5)


def set_vfo_frequency(data, vfo, text):
    _set_digits(data, VFO_BASE + 0x20 * vfo, text, 3, 5)


def vfo_offset(data, vfo):
    return _digits_text(data, VFO_BASE + 0x20 * vfo + 8, 3, 3)


def set_vfo_offset(data, vfo, text):
    _set_digits(data, VFO_BASE + 0x20 * vfo + 8, text, 3, 3)


def _tone_addr(vfo, which):
    return VFO_BASE + 0x20 * vfo + {"rx": 0x10, "tx": 0x12}[which]


def vfo_tone(data, vfo, which):
    """RX or TX tone of a VFO, coded as in the channels (docs/protocol.md)."""
    a = _tone_addr(vfo, which)
    return channels._decode_tone(data[a], data[a + 1])


def set_vfo_tone(data, vfo, which, text):
    if not isinstance(text, str):
        raise TypeError("tone must be a string")
    a = _tone_addr(vfo, which)
    data[a : a + 2] = channels._encode_tone(text.strip().upper())
