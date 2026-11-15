"""Calibration tables ("Adjust" screen of the CPS), image 0x3C00..0x3DEF.

Found by "Default" + "Write" on the CPS against the emulator and by reading
the screen tabs (docs/protocol.md). One byte per value.
"""

from dataclasses import dataclass

from kta16.i18n import t

BANDS = ("108-176 MHz", "200-270 MHz", "400-520 MHz", "350-390 MHz")
SQL_BANDS = ("100-135 MHz", "136-176 MHz", "400-520 MHz")
BAND_LIMITS_ADDR = 0x3D80  # 4 rows: low (3 digits), high (3 digits), 0, enabled
BAND_LIMIT_NAMES = ("VHF0", "VHF1", "UHF0", "UHF1")


@dataclass(frozen=True)
class Table:
    key: str
    label_key: str  # text of kta16/i18n.py
    addr: int
    length: int = 16
    label_args: tuple = ()  # (name, value) pairs for the text

    @property
    def label(self):
        return t(self.label_key, **dict(self.label_args))

    def get(self, data):
        return list(data[self.addr : self.addr + self.length])

    def set(self, data, index, value):
        if not 0 <= index < self.length:
            raise IndexError(f"{self.key}: index {index} out of 0..{self.length - 1}")
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise ValueError(f"{self.key}: value must be 0..255, got {value!r}")
        data[self.addr + index] = value


TABLES = (
    *(
        Table(
            f"power_high_{i + 1}", "cal_power_high", 0x3C00 + 16 * i, 16, (("band", b),)
        )
        for i, b in enumerate(BANDS)
    ),
    *(
        Table(
            f"power_low_{i + 1}", "cal_power_low", 0x3C40 + 16 * i, 16, (("band", b),)
        )
        for i, b in enumerate(BANDS)
    ),
    *(
        t
        for i, b in enumerate(SQL_BANDS)
        for t in (
            Table(
                f"sql_level_{i + 1}",
                "cal_sql_level",
                0x3C80 + 32 * i,
                10,
                (("band", b),),
            ),
            Table(
                f"sql_freq_{i + 1}", "cal_sql_freq", 0x3C90 + 32 * i, 16, (("band", b),)
            ),
        )
    ),
    Table("am_sql_level", "cal_am_sql_level", 0x3CE0),
    Table("am_sql_freq", "cal_am_sql_freq", 0x3CF0),
    # 4th tab (sandbox: Read, change one list, Write, diff). RF output rows:
    # 020-099, 100-199, 200-299, 300-370, 371-399, 400-499, 500-599 MHz, FSK
    *(
        Table(f"rf_out_{w}_{c}", f"cal_rf_out_{w}", addr, 8, (("column", c),))
        for c, base in ((1, 0x3D00), (2, 0x3D10))
        for w, addr in (("wide", base), ("narrow", base + 8))
    ),
    Table("pa", "cal_pa", 0x3D20),
    # MIC, voice gain, TONE, two gains, volume, ?, ?; MIC shows 2**v; voice,
    # TONE and volume are packed (see unpack_gain)
    Table("audio_wide", "cal_audio_wide", 0x3D30, 8),
    Table("audio_narrow", "cal_audio_narrow", 0x3D38, 8),
    # 5th tab
    Table("vox_threshold", "cal_vox", 0x3DD0, 11),
    Table("limit_mode", "cal_limit_mode", 0x3DDF, 1),
)
TABLE_BY_KEY = {t.key: t for t in TABLES}


def band_limits(data, row):
    """(low MHz, high MHz, enabled) of VHF0, VHF1, UHF0, UHF1 (row 0..3)."""
    a = BAND_LIMITS_ADDR + 16 * row
    d = data[a : a + 8]
    return d[0] * 100 + d[1] * 10 + d[2], d[3] * 100 + d[4] * 10 + d[5], bool(d[7])


def unpack_gain(value):
    """Two CPS lists in one byte: left = 7 - top 3 bits, right = low 5 bits."""
    return 7 - (value >> 5), value & 0x1F


def pack_gain(left, right):
    if not (0 <= left <= 7 and 0 <= right <= 31):
        raise ValueError("gain must be 0..7 and 0..31")
    return (7 - left) << 5 | right
