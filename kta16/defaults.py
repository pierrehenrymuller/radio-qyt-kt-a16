"""Values set by the "Default" button of each screen of the vendor CPS.

Measured in the RE sandbox against the emulator: Read, Default, Write from
two different radio images; bytes written alike both times are set by
Default, the others are kept from the radio (docs/protocol.md). The
calibration Default also sets the passwords to 123456 and 303688.
"""

from kta16 import fivetone

ZONES = {
    "options": (
        (
            0x0E00,
            bytes.fromhex(
                "00 03 05 00 00 04 01 00 01 00 01 00 02 02 02 00 05 01 01 00 00 "
                "00 04 05 04 06 03 00 00 00 00 0a 00 0c 00 01 "
            ),
        ),
        (0x0E61, bytes.fromhex("00 00 00 00 00 00 00 00 ")),
        (0x0E81, bytes.fromhex("00 ")),
        (0x0E84, bytes.fromhex("1f 01 ")),
        (
            0x0ED0,
            bytes.fromhex(
                "08 00 08 00 08 ff ff ff ff ff ff ff ff ff ff ff 01 02 03 04 05 "
                "ff ff ff ff ff ff ff ff ff ff ff 09 08 07 06 05 ff ff ff ff ff "
                "ff ff ff ff ff ff 01 03 06 00 02 05 00 00 00 01 00 06 05 00 00 "
                "00 00 00 00 00 00 00 00 00 00 00 00 00 "
            ),
        ),
        (
            0x0F20,
            bytes.fromhex(
                "01 01 05 06 02 05 00 00 00 00 01 06 02 05 00 00 00 00 00 00 0e "
                "00 00 00 00 00 00 00 "
            ),
        ),
        (
            0x0F40,
            bytes.fromhex(
                "01 01 06 00 02 05 00 00 00 01 00 06 05 05 00 00 00 00 00 00 00 "
                "00 00 00 00 00 00 00 "
            ),
        ),
        (
            0x0F60,
            bytes.fromhex(
                "04 06 00 06 02 05 00 00 00 00 01 06 02 05 00 00 00 00 00 00 0e "
                "00 00 00 00 00 00 00 "
            ),
        ),
    ),
    "5-tone": (
        (0x2000, fivetone.DEFAULT_TABLES),
        (
            0x23F0,
            bytes.fromhex("ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff 08 0a 0e"),
        ),
        (0x2410, bytes.fromhex("05 0a 0e ")),
        (0x2420, bytes.fromhex("05 0a 0e ")),
        (0x2430, bytes.fromhex("05 0a 0e ")),
        (0x2440, bytes.fromhex("05 0a 0e ")),
        (0x2450, bytes.fromhex("05 0a 0e ")),
        (0x2460, bytes.fromhex("05 0a 0e ")),
        (0x2470, bytes.fromhex("05 0a 0e ")),
        (0x2480, bytes.fromhex("05 0a 0e ")),
        (0x2490, bytes.fromhex("02 0a 0e ")),
        (0x24A0, bytes.fromhex("01 0a 0e ")),
        (0x24B0, bytes.fromhex("08 0a 0e ")),
        (0x24C0, bytes.fromhex("05 0a 0e ")),
        (0x24D0, bytes.fromhex("05 0a 0e ")),
        (0x24E0, bytes.fromhex("02 0a 0e ")),
        (
            0x2500,
            bytes.fromhex(
                "01 02 03 04 05 03 04 05 06 07 05 06 07 08 09 00 ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff 02 03 04 05 06 04 05 "
                "06 07 08 06 07 08 09 00 0e 14 14 14 00 ff ff ff ff 00 01 06 3b "
                "ff ff ff ff "
            ),
        ),
    ),
    "dtmf": (
        (
            0x2900,
            bytes.fromhex(
                "02 0a 02 0a 02 ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff 03 0a 03 0a 03 ff ff "
                "ff ff ff ff ff ff ff ff ff 03 03 ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff 02 0a 02 ff ff ff ff ff ff ff ff ff ff ff ff ff 03 "
                "0a 03 ff ff ff ff ff ff ff ff ff ff ff ff ff 01 01 09 ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff 05 0a 05 ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff 06 06 06 ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "07 07 07 ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff 06 0a 06 0a 06 ff ff ff ff ff ff ff ff ff ff ff 07 0a 07 "
                "0a 07 ff ff ff ff ff ff ff ff ff ff ff 01 1f 03 00 0b 0c 04 9f "
                "ff ff ff ff ff ff ff ff "
            ),
        ),
    ),
    "2-tone": (
        (
            0x2D00,
            bytes.fromhex(
                "bd 07 ff ff ff ff ff ff 64 04 ff ff ff ff ff ff 4e 05 ff ff ff "
                "ff ff ff a6 05 ff ff ff ff ff ff 04 06 ff ff ff ff ff ff 68 06 "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff 98 08 ff ff ff ff ff ff ca 03 ff ff ff "
                "ff ff ff 24 04 ff ff ff ff ff ff 88 04 ff ff ff ff ff ff 78 05 "
                "ff ff ff ff ff ff fa 05 ff ff ff ff ff ff 86 06 ff ff ff ff ff "
                "ff 26 07 ff ff ff ff ff ff 3c 3c 1e ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff 00 01 01 04 02 02 08 03 03 09 00 04 ff ff ff ff 00 "
                "01 01 04 02 02 08 03 03 09 00 04 ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff 00 01 01 04 02 02 08 03 03 09 00 04 ff ff ff ff 09 00 04 "
                "08 03 03 04 02 02 00 01 01 ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff bd 07 64 04 ad 04 fb 04 b7 01 f9 00 0a "
                "01 1b 01 4e 05 a6 05 04 06 68 06 2d 01 41 01 56 01 6c 01 ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff "
                "ff ff ff ff ff ff 98 08 ca 03 24 04 88 04 e8 01 d7 00 eb 00 01 "
                "01 78 05 fa 05 86 06 26 07 37 01 53 01 72 01 96 01 3b ff ff ff "
                "ff ff ff ff ff ff ff ff ff ff ff ff "
            ),
        ),
    ),
    "fm": (
        (
            0x3000,
            bytes.fromhex(
                "00 08 08 09 00 00 00 00 51 5a 4e 45 57 ff ff ff 00 09 00 04 00 "
                "00 00 00 43 43 54 56 31 ff ff ff 00 00 00 00 00 00 00 00 ff ff "
                "ff ff ff ff ff ff 00 09 02 03 00 00 00 00 4a 54 5a 53 32 ff ff "
                "ff 00 00 00 00 00 00 00 00 ff ff ff ff ff ff ff ff 00 09 05 05 "
                "00 00 00 00 51 5a 42 42 43 ff ff ff 00 00 00 00 00 00 00 00 ff "
                "ff ff ff ff ff ff ff 00 09 06 09 00 00 00 00 43 43 54 56 34 ff "
                "ff ff 00 00 00 00 00 00 00 00 ff ff ff ff ff ff ff ff 00 09 08 "
                "03 00 00 00 00 46 4a 51 58 ff ff ff ff 00 00 00 00 00 00 00 00 "
                "ff ff ff ff ff ff ff ff 01 00 03 09 00 00 00 00 43 43 54 56 36 "
                "ff ff ff 00 00 00 00 00 00 00 00 ff ff ff ff ff ff ff ff 01 00 "
                "00 07 00 00 00 00 44 4e 5a 53 33 ff ff ff 00 00 00 00 00 00 00 "
                "00 ff ff ff ff ff ff ff ff 01 00 05 09 00 00 00 00 43 43 54 56 "
                "39 ff ff ff "
            ),
        ),
    ),
    "calibration": (
        (0x3B90, bytes.fromhex("20 12 23 34 45 56 67 78 00 00 00 00 00 00 00 ff ")),
        (
            0x3C00,
            bytes.fromhex(
                "0c 0d 0d 0d 0d 0d 0e 0f 0f 0f 0f 0f 0f 0f 0f 0f 0c 0d 0d 0d 0d "
                "0d 0e 0f 0f 0f 0f 0f 0f 0f 0f 0f 0c 0d 0d 0d 0d 0d 0e 0f 0f 0f "
                "0f 0f 0f 0f 0f 0f 0c 0d 0d 0d 0d 0d 0e 0f 0f 0f 0f 0f 0f 0f 0f "
                "0f 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 "
                "05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 "
                "05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 05 "
                "05 05 00 58 5a 5c 5e 60 62 64 66 68 6c 6c 6c 6c 6c 6c 08 08 08 "
                "05 05 05 02 02 00 00 00 00 00 00 00 00 00 58 5a 5c 5e 60 62 64 "
                "66 68 6c 6c 6c 6c 6c 6c 01 01 01 01 00 00 00 00 00 00 00 00 00 "
                "00 00 00 00 58 5a 5c 5e 60 62 64 66 68 6c 6c 6c 6c 6c 6c 01 01 "
                "01 01 00 00 00 00 00 00 00 00 00 00 00 00 0a 0b 0c 0d 0e 0f 10 "
                "11 12 12 14 15 16 17 18 19 00 00 00 00 00 00 00 00 00 00 00 00 "
                "00 00 00 00 07 07 07 07 07 07 07 07 05 05 05 05 05 05 05 05 07 "
                "07 07 07 07 07 07 07 05 05 05 05 05 05 05 05 01 02 03 04 05 06 "
                "07 08 09 0a 0b 0c 0d 0e 0f 00 03 79 79 2d 1e 9e 00 64 03 bd bd "
                "41 2a bd bd bd 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
                "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
                "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
                "00 00 00 00 00 00 01 00 08 01 03 06 00 01 00 00 00 00 00 00 00 "
                "00 01 03 07 01 07 04 00 01 00 00 00 00 00 00 00 00 04 00 00 05 "
                "02 00 00 01 00 00 00 00 00 00 00 00 03 00 00 03 03 06 00 01 00 "
                "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
                "00 00 7f 14 20 2a 34 3e 48 54 5f 6a 75 00 00 00 00 00 00 00 00 "
                "00 00 00 00 00 00 00 00 00 00 00 00 00 31 32 33 34 35 36 33 30 "
                "33 36 38 38 00 00 00 00 "
            ),
        ),
    ),
}


def apply(data, zone):
    """Set the bytes the CPS "Default" button sets for `zone`."""
    for start, values in ZONES[zone]:
        data[start : start + len(values)] = values
