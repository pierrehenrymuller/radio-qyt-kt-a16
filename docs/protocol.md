# KT-A16 CPS serial protocol

Source: static analysis of `vendor/cps/KT_A16_CPS.exe` (native VB6, SHA-256
`741fa6630dc0525e9f6d4bc84c8fbe8aff4e76cf5f8958969767b519468cf11c`),
disassembly with `objdump -d -M intel` annotated with the imports of `msvbvm60.dll`,
Ghidra 12.1.4 via REA. Addresses are VAs of the binary (base 0x400000).
Any statement without an address is marked "unverified hypothesis".

The evidence files cited below (`captures/`, and the `re/` scripts that
produced them: Wine sandbox, USB capture decoders, real-radio tools) are not
published: they hold personal radio data and vendor-derived material.

## Link

- 9600 bauds, 8N1: string `9600,N,8,1` (VA 0x426074) assigned to `Settings`
  in 12 places (0x4681bb, 0x49153d, ...).
- The MSComm properties are called through late binding (`__vbaLateIdSt`,
  `__vbaLateIdCallLd`). DISPIDs read from the typelib of `MSCOMM32.OCX`:
  0x19 `Output`, 0x1a `Input`, 0xc `InBufferCount`, 0x14 `PortOpen`,
  0x1b `CommEvent`, 0x17 `Settings`, 0x9 `DTREnable`, 0x16 `RTSEnable`.
- `Output` always receives a one-byte array (variant 0x2011,
  `VT_ARRAY|VT_UI1`): send routine 0x48f370, loop over the word buffer
  `[form+0x94]` up to the length `[form+0xa0]`, one `Output` per byte.
- No checksum is computed by the send routine 0x48f370:
  it copies the bytes as they are.
- After each send, a guard timer is armed at 2000 ms (0x48f497,
  `push 0x7d0`). Its expiry matches the message "Communication
  fault." (unverified hypothesis: link between timer and message not traced).
- Reception in the `OnComm` event: test `CommEvent == 2`
  (`comEvReceive`) at 0x47ffb8, then wait for `InBufferCount` to exceed a
  threshold before reading byte by byte (`Input`, `InputLen` = 1 assumed:
  unverified hypothesis).

## Session opening (handshake)

Fixed 8-byte frame written when the MDI window loads into the global
array `[0x577160]` (0x4644f1 to 0x46456d):

    55 20 23 04 26 FF DC 02

The CPS of the QYT 8R (listed by Radtel for the RT-4B) builds the same
frame with other middle bytes, `55 20 17 07 03 FF DC 02` (0x4645e1 to
0x46465d of `8R_VIP_CPS.exe`); the radio side of those bytes is not
established.

It is copied into the send buffer of each communication window
(example 0x47d19a, length 8 set at 0x47d1cf) and then sent.

Expected response (channels: 0x481fc7 to 0x482296):

- the CPS waits for `InBufferCount > 0x31` then reads 50 bytes;
- frame valid if `b[0] == 0x06` and `b[0x31] == 0x55`, or if
  `b[0] == 0x01` and `b[0x30] == 0x55` (0x482260 to 0x482296);
- if `b[0] == 0x06`, the CPS shifts the buffer by one byte (0x482394 to
  0x48248f): the payload P[0..47] follows the ACK and ends with 0x55.

After a valid identification, the CPS sends the ACK `06` (0x48229c,
`Output` of one byte 0x06), runs a wait loop of 40000 turns
(0x48233e, 0x9c40), then proceeds to the reads.

### Identification payload

Each byte carries a decimal digit (0x4824a0: `100*P0 + 10*P1 + P2`).

| Bytes P | Meaning | Variable | Proof |
|---|---|---|---|
| 0..2 | band A, low limit (MHz) | 0x57721c | 0x482494 |
| 3..5 | band A, high limit (MHz) | 0x577224 | 0x4824e0 |
| 0x10..0x12 | band B, low limit | 0x57722c | 0x48252d |
| 0x13..0x15 | band B, high limit | 0x577234 | 0x48257a |
| 0x20..0x22 | band C, low limit | 0x57723c | 0x4825c7 |
| 0x23..0x25 | band C, high limit | 0x577244 | 0x482614 |
| 0x0a..0x0f | 6-character text | | 0x48263d, 0x4826f6 |
| 0x1a..0x1f | 6-character text | | 0x4827b0 |
| 0x26..0x2f | 10-character text | | 0x4828ff, 0x48296b |

The three texts are ASCII characters (`Chr$`: ord608 of
`msvbvm60.dll`). CPS status bar against the emulator
(`captures/tb5s.png`): P[0x0a..0x0f] = Model, P[0x1a..0x1f] =
MCU-Version, P[0x26..0x2f] = S I M.

## Reading a block (channel window)

Request of 4 bytes (0x481494 to 0x48160d, length 4 at 0x48160d):

    53 AH AL 40

- 0x53 = `S`; 0x40 = 64 bytes requested.
- Address = base + n × 64, n = block number (channel - 1): `AH = base_h +
  Int(n / 4)`, `AL = base_l + (n × 64 - Int(n / 4) × 256)` (constants 4.0 at
  0x401310 and 256.0 at 0x401350).
- Second pass: `AH + 16`, i.e. address + 0x1000 (0x481a8c, 16.0 at
  0x401358), alternated by the flag `[0x57729e]`.
- Base `[0x577408]`, `[0x577409]` set to 0 for the channels (0x47d1f8 to 0x47d203).

Response: the CPS waits for `InBufferCount > 0x44` then reads 0x44 = 68 bytes
(0x480df0, loop 0x480ecb). The bytes are stored as they are in the channel
table `[0x5770f4]` or `[0x5770d0]` depending on `[0x57729e]` (0x480f86). The
format of the first 4 bytes (assumed echo of the request) is an unverified
hypothesis. The CPS then answers `06` (0x481094 to 0x4810ca).

Number of blocks read by the channel window: `Int(200 / 4 + 0.9) + 1 = 51`
(0x47d4c5 to 0x47d512, constants 0.9 at 0x401768 and 1.0 at 0x401760), so
0x0000 to 0x0CBF then 0x1000 to 0x1CBF.

## Channel layout

200 channels (`[0x5772a0] = 0xc8`, 0x467c22). Channel n: 16-byte row at
`(n-1)*16`, 8-byte name at `0x1000 + (n-1)*16` (row `0x100 + n - 1`,
0x48b857). Decoder 0x474b20, encoder 0x487280.

| Bytes | Field | Encoding | Proof |
|---|---|---|---|
| 0-3 | RX | little-endian BCD, unit 10 Hz; byte 0 = 0xff: empty channel | 0x518eb0 (weight 1e-5 to 100), 0x474d1a |
| 4-7 | TX | same encoding | 0x47550f to 0x475601 |
| 8-9 | CTCSS/DCS receive | 0/0 or ff/ff = OFF; byte 9 = 0: DCS, table index = byte 8 + 0x32; otherwise (b9×256+b8)/10 Hz | 0x474fb8, 0x4750a2 |
| 10-11 | CTCSS/DCS transmit | same encoding | 0x4758c0 |
| 12 bits 0-3 | SigCode | 0..14, 15 = empty | 0x475ef0 |
| 13 bits 0-3 | optional signal | 0 OFF, 1 DTMF, 2 2TONE, 3 5TONE | 0x476144 to 0x476410 |
| 13 bits 4-7 | Spmute | 0 QT, 1 AND, 2 OR | 0x476501 to 0x476753 |
| 14 bits 4-7 | SCR (scrambler) | 0 OFF, 1 ON | 0x476844 to 0x4769d8 |
| 14 bits 0-2 | power | 0 HIGH, 1 LOW | 0x476acf to 0x476c13 |
| 15 bits 0-1 | PTT-ID | 0 OFF, 1 BOT, 2 EOT, 3 BOTH | 0x476c8c to 0x476f7f |
| 15 bit 2 | Scan_Add | 1 = ON | 0x476ff3 |
| 15 bit 3 | BusyLock | 1 = ON | 0x47710c |
| 15 bit 6 | W/N | 1 = N | 0x477225 |

Tone table `[0x5772f4]` filled at 0x50e56b: index 0 OFF, 1 to 50
CTCSS, 51 to 155 DCS N (D023N at 0x50e8c3), 156 to 260 DCS I; copied into
`kta16/tones.py`. Name: the CPS accepts ASCII codes 0-9 and A-Z (`Asc`, 0x48bc06) and at most 6
characters (VA 0x48b4e2); tested on the real radio (`re/names_probe.py`,
`captures/names-1.log`, 2026-11-11): it shows space (0x20), `-` (0x2d), `+`
(0x2b), `_` (0x5f) and 7 characters; the 8th byte is shown as a number (72 for
`H`), so it stays 0xff; 0xff =
end; the decoder also accepts 0..9 (digits), 0x11..0x25 (+0x30), 0xfb
`+`, 0xfd `-` (0x4777a1 to 0x477b05). The encoding of OFF as `ff ff` is an
unverified hypothesis (writes of 0xff at 0x489fee and 0x48a020).

## Writing a block (channel window)

Frame of 21 bytes (0x480817 to 0x480abb, length 0x15 at 0x480abb):

    06 58 AH AL 10 D0 .. D15

- 0x58 = `X`; 0x10 = 16 bytes of data.
- Address = base + channel × 16 (constants 16.0 and 256.0); second half
  at `AH + 16` (0x480b43), i.e. + 0x1000.
- Data: table `[0x5770ac]`, 16 words per channel (0x480a67).
- The CPS waits for `06` from the radio before the next block (0x4800b5).

The role of the `06` at the start of the write frame (ACK of the previous
exchange or part of the command) is an unverified hypothesis.

## Dynamic validation against the emulator

The CPS runs under Wine in the sandbox, its COM1 connected by socat to
`re/emu_stdio.py` (emulator `kta16/emulator.py`), without radio.

- Under Wine, MSComm never triggers `OnComm` on a pty:
  `TIOCGICOUNT` and `TIOCMGET` fail ("Inappropriate ioctl for device",
  `captures/wine-serial.log` lines 57 to 60). The shim `re/ptyshim.c`
  (`LD_PRELOAD`) answers these two ioctls; with it, the CPS processes the
  responses.
- The CPS lowers DTR after opening (`IOCTL_SERIAL_CLR_DTR`, same
  log line 37) and does not touch RTS.
- Options window, Read button: the CPS accepts the emulated identification,
  shows Model = P[0x0a..0x0f] and MCU-Version = P[0x1a..0x1f] in the
  status bar, Band-A/B/C = 136-174, 400-480, 220-260 (capture
  `captures/emu-read2.png`). It then reads 8 blocks `53 0E 00 40` to
  `53 0F C0 40`, each followed by `06`, and shows "Complete reading the
  data from transceiver." (`captures/opt-zero.png`).
- From the 3rd block on, the CPS waits for `InBufferCount > 0x44`, that is
  69 bytes (0x4b9f30 to 0x4b9f4a): the real capture shows that the 69th
  is the `06` by which the radio answers the ACK from the PC (see "Protocol observed on the real radio").
- Band-D shows "9036--5408": source not identified (unverified hypothesis:
  bytes beyond the 48-byte payload).

## Password block (0x3DF0)

Before the channels, the channel window reads 16 bytes: request `53 3D F0 10`
(emulator log, `captures/emu/emu.log`). Expected response of
`InBufferCount > 0x13` bytes (0x481ff7); the CPS looks for byte 0x58 in
the first 0x14 (0x483525), concludes that the response starts with
`58 AH AL LEN` (header `X`, hypothesis extended to 64-byte responses),
and copies the 16 data bytes into `[0x5771d0]` (0x483735).

- Bytes 0..5: password 1, ASCII; six spaces (0x20) = none
  (0x4837f0 to 0x4837ff).
- Bytes 6..11: password 2, same rule (0x4838c1 to 0x4838c7).
- Comparison with the password typed in the CPS `[0x577198]`
  (0x4839ad to 0x4839c4): the check is done by the PC, the radio checks
  nothing (according to this code; unverified hypothesis on the radio side).
- Respective role of the two passwords (read, write): unverified hypothesis.

## Options ("Optional Features", 0x0E00 to 0x0FFF)

Terminology: the blocks at 0x0F00, 0x0F20 and 0x0F40 are called "VFO A, B, C"
in this document; the CPS calls them "A Frequency model parameters" and so on.
On the radio they are the three frequency lines A, B and C of the screen
(confirmed by the user, 2026-11-11: the 8.33 kHz step was set on the first
line). The CPS also has "A, B, C - Fore Color" and "A, B, C Channel Disp Way",
one per line. In the TUI they are shown as "Line A, B, C".

Addresses found by reading coded binary values (`captures/opt-bit*.png`)
then confirmed by "Default" + "Write" (`captures/optw-*.img`):
value = index in the CPS list, unless stated otherwise.

| Address | Field | Values |
|---|---|---|
| 0x0E00 | TMR | OFF, M+A, M+B, M+C, M+A+B, M+A+C, M+B+C, M+A+B+C |
| 0x0E02 | Squelch Level | 0..9 (end of list: unverified hypothesis) |
| 0x0E03 | VOX | OFF, 1, 2... |
| 0x0E04 | Auto Lock | OFF, ON |
| 0x0E05 | TOT | OFF, 15, 30... seconds (default 4 = 60) |
| 0x0E06 | Save | OFF, 1:1, 1:2, 1:3, 1:4 |
| 0x0E07 | ABR | OFF, ... (labels after OFF: unverified hypothesis) |
| 0x0E08 | Beep | OFF, ON |
| 0x0E09 | BCL | OFF, ON |
| 0x0E0A | Scan Add | OFF, ON |
| 0x0E0B | Scan_Rev | TO, CO, SE |
| 0x0E0C..0x0E0E | A/B/C Channel Disp Way | default 2 = Channel+Frequency; other values not established |
| 0x0E0F | Voice | OFF, English, Chinese |
| 0x0E10..0x0E1A | 11 colors | White, Red, Blue, Green, Yellow, Indigo, Purple, Gray, Black |
| 0x0E1F | TMR Return AB | value = number displayed (default 10) |
| 0x0E20 | TX for TMR | Track, Fixed |
| 0x0F00 | VFO A, frequency | 8 bytes, one decimal digit per byte (136.02500 = 01 03 06 00 02 05 00 00) |
| 0x0F08 | VFO A, offset | 6 digits (010.650) |
| 0x0F10, 0x0F12 | VFO A, RX, TX tones | like the channels, OFF = 00 00 |
| 0x0F15 | VFO A, Speak Mute | QT/DQT, AND OPTSIG, OR OPTSIG |
| 0x0F16 | VFO A, Optional Signal | OFF, FSK |
| 0x0F18 | VFO A, W/N | WIDE, NARROW |
| 0x0F19 | VFO A, TX Power | HIGH, LOW |
| 0x0F1A | VFO A, SFT_D | OFF, +, - |
| 0x0F1B | VFO A, step | 2.50, 5.00, 6.25, 10.00, 12.50, 25.00 kHz (values 0..5, CPS list); 6 = 8.33 kHz, outside the CPS list (confirmed on the radio screen for lines A and C); the CPS rewrites 6 as 5 (25 kHz) |
| 0x0F20, 0x0F40 | VFO B, C | same structure as A, checked on the CPS screen (`captures/vfo-all.png`) |
| 0x0F60 | 4th block | written by "Default", no button in the CPS: role not established |
| 0x0FE0 | Model | 16 ASCII characters |

Not assigned: 0x0E01 (default 03), 0x0E21 (0c), 0x0E23 (01), 0x0E84
(1f 01), 0x0ED0..0x0EFF (digit strings, probably ANI / alarm /
DTMF; unverified hypothesis), DTMF-ST.

## Hidden CPS menus

The menus `fm_chann_edit` (FM-Radio), `sig_edit` (Signal: DTMF, 2 TONE,
5 TONE, WDC1200, WDC2400), `frm_adj` (Adjust), `PC_PassWord`,
`Language_Setup` and `about` are hidden in the data of the MDI window
(file VA 0x83e6 to 0x8668): property 0x02 = Visible at 0, property
0x05 = Enabled at 0. A modified copy of the executable, in the sandbox
only (bytes set to 0xff), makes them accessible; the original is not
modified (SHA-256 unchanged).

## DTMF (0x2900 to 0x2AFF)

One digit per byte: `1`..`9` = 1..9, `0` = 0x0a, `*` = 0x0b, `#` = 0x0c,
`A`..`C` = 0x0d..0x0f, `D` = 0; 0xff ends (CPS "Default" +
"Write", `captures/dtmf-written.img` and `captures/dtmf-default.png`).

| Address | Field |
|---|---|
| 0x2900 + 16×(n-1), n 1..15 | encoding codes (16 digits at most) |
| 0x29F0, 0x29F1 | DTMF Speed On / Off: 50 + 10×v ms (seen: 3 = 80) |
| 0x2A00..0x2A50 | Inspection, Monitor, Alarm, Stun, Kill, Revive |
| 0x2AD0, 0x2AE0 | Master Control ID, Vice Control ID |
| 0x2AF0 | "master and vice ID" checkbox |
| 0x2AF1, 0x2AF2 | master / vice rights: bits 0..4 Inspection, Monitor, Stun, Kill, Revive (each checkbox ticked alone in the sandbox: Stun 0x04, Kill 0x08, Revive 0x10) |
| 0x2AF3 | State: bit 0 RX Disable, bit 1 TX Disable (sandbox) |
| 0x2AF4, 0x2AF5 | Group Code, Space Code (DTMF digit code) |
| 0x2AF6 | Reset Time: 15600 + 100×v ms (4 = 16000, 5 = 16100, measured on the CPS list) |
| 0x2AF7 | Delay: 100×(v − 154) ms (159 = 500, 160 = 600) |

## 2-tone (0x2D00 to 0x2FFF)

Frequencies in whole Hz, 16 bits little-endian, 0xffff = empty, 300 to
3000 Hz (`captures/2tone-written.img`, `captures/2tone-tabs.png`).

| Address | Field |
|---|---|
| 0x2D00 + 16×(n-1), n 1..15 | encoding code: bytes 0-1 = 1st frequency, 8-9 = 2nd |
| 0x2DF0..0x2DF2 | durations of 1st tone, 2nd tone, interval, unit 10 ms |
| 0x2E00 + 16×(n-1) | decoding: 4 triplets (pair A-B=0 … D-C=11, response 0 None 1 Alert 2 Transpond 3 Alert+Transpond, alert) |
| 0x2F00 + 16×(n-1) | tones A, B, C, D then 4 coefficients `int(Hz×4096/18466 + 0.5)` (1981 gives 439) |
| 0x2FF0 | Reset_Time: 100×(v+1) ms, CPS list 100..8000 ms (sandbox writes: 100 = 0, 7300 = 0x48, 8000 = 0x4f); 0xff displays 8000 |

## 5-tone (0x2000 to 0x25FF)

Standards s = 0..14 (CCIR1 … MODAT), 16 tones each
(`captures/5tone-written.img`): low byte of the frequency at 0x2000+16s,
high byte at 0x2100+16s, low/high coefficient at 0x2200 /
0x2300 (same formula as the 2-tone), 0x2400+16s = period (20 + 10×v ms),
group tone, repeat tone (hexadecimal digits). Encoding codes at
0x2500+16(n-1): three frames of 5 hexadecimal digits
then the standard index. 0x25F0..0x25F3: Delay 1..3 and First Digit
Extend (unit 10 ms); 0x25F8 decoding standard; 0x25F9 / 0x25FA:
"Decode Call" / "Decode Disp" frames (bits 0..2); 0x25FB Reset,
same formula as the 2-tone (6000 = 59, 6500 = 0x40 written in the sandbox).

## FM (0x3000 to 0x30FF)

16 rows: bytes 0-7 = frequency, one digit per byte (088.90000); bytes
8-15 = ASCII name padded with 0xff; empty = digits 0 and name 0xff
(`captures/fm-written.img`). The FM window reads the password block
(`53 3D F0 10`) again before writing.

## Calibration ("Adjust", 0x3C00 to 0x3DEF, plus 0x3B90)

One byte per value (`captures/adj-written.img`, tabs
`captures/adj-tab*.png`, Chinese labels badly rendered under Wine).

| Address | Table |
|---|---|
| 0x3C00 + 16×b | high power, bands 108-176, 200-270, 400-520, 350-390 MHz, 16 points |
| 0x3C40 + 16×b | low power, same bands |
| 0x3C80 / 0x3CA0 / 0x3CC0 | squelch, levels 0..9, bands 100-135, 136-176, 400-520 |
| 0x3C90 / 0x3CB0 / 0x3CD0 | squelch, correction per frequency (16 points) |
| 0x3CE0 / 0x3CF0 | AM SQL levels 1..16 / correction per frequency |
| 0x3D00 / 0x3D08 | 4th tab, "射频输出" (RF output) column 1, wide band (宽带) / narrow band (窄带): 8 rows 020-099, 100-199, 200-299, 300-370, 371-399, 400-499, 500-599 MHz, FSK; displayed value 0..7 |
| 0x3D10 / 0x3D18 | same table, column 2 |
| 0x3D20 | 4th tab, "PA": 16 points 108..138 MHz, displayed value |
| 0x3D30 / 0x3D38 | 4th tab, audio wide / narrow: MIC (displayed 2^v), voice and TONE (two lists in one byte: left = 7 − 3 high bits, right = 5 low bits), two gains (displayed value), volume (packed like the voice); 0x3D36, 0x3D37 (100) and 0x3D3E..0x3D3F without readable label |
| 0x3D80 + 16×r | limits VHF0, VHF1, UHF0, UHF1: 3 low digits, 3 high digits, 0, checkbox ticked |
| 0x3DD0 | 5th tab, "声控等级 / 起控值": VOX trigger threshold of levels 0..10 (127, 20, 32 … 117) |
| 0x3DDF | 5th tab, "功能选择": 0 = TX and RX, 1 = Only RX (application of the frequency limits; unverified hypothesis on the radio) |
| 0x3B90 | 16 bytes also sent by the Adjust write (`20 12 23 34 45 56 67 78 00…`), role not identified |

"Default" on this screen also writes the passwords 0x3DF0 = "123456"
and 0x3DF6 = "303688" (5th tab: user password, super password according to the labels). Chinese labels read by decoding in GBK the
text displayed by Wine. Measurements: Read, one list changed, Write, diff
(`captures/def/adj-t4a.img`, `adj-t4b.img`); with `RE_EMU_TRAILER`, the
last byte of each 64-byte block read by this screen arrives as 0 (sandbox
artifact).

## Default and Clear buttons of the screens

Measured in the sandbox (2026-11-11), CPS unlocked against the emulator:
Read, Default, Write from two different images (real image,
then the same with each ambiguous byte modified); a byte written the
same way both times is fixed by Default, the others come from the radio.
Images in `captures/def/` (not versioned), values in
`kta16/defaults.py`.

| Screen | Bytes fixed by Default |
|---|---|
| Options | 0x0E00..0x0E23, 0x0E61..0x0E68, 0x0E81, 0x0E84..0x0E85, 0x0ED0..0x0F1B, 0x0F20..0x0F3B, 0x0F40..0x0F5B, 0x0F60..0x0F7B; the Model text (0x0FE0) is rewritten shifted by the CPS, left aside |
| DTMF | the whole area 0x2900..0x2AFF (`captures/dtmf-written.img`) |
| 2-tone | the whole area 0x2D00..0x2FFF |
| 5-tone | the whole area except 0x24s3..0x24sF (s = 0..14) and 0x24E3..0x24FF |
| FM | the whole area 0x3000..0x30FF; Clear sets the area to 0x00 |
| Adjust | 0x3B90..0x3B9F, 0x3C00..0x3DFF, including the passwords 123456 and 303688 |
| Channels | Clear: rows and names to 0xff. Default: channels 0 to 6 replaced (110.025 to 117.025 MHz), bytes 8..11 of each channel to 0xff, power changed, a channel added in row 100 erased; rule not established and destructive, not transposed (user decision, 2026-11-11) |

Other findings:

- The Write of the Options window also sends 16 bytes at 0x3B90:
  `20 12 23 34 45 56 67 78` then the 8 bytes read (Default: 00). The
  TUI does not write 0x3B90 with the options; content of the real radio at
  this address never read.
- Read then Write without Default in Options rewrites 0x0F0C..0x0F0D and
  0x0F1B (VFO A offset and step brought back to the CPS lists).
- File > New, after a full read, changes nothing in what Program > Write to
  radio writes (`captures/def/prog-ref.img` and
  `prog-new.img` identical); this Write only regenerates the 5-tone
  tables 0x2000..0x23EF.
- WDC1200 and WDC2400 remain absent from the Signal menu of the unlocked CPS
  (only DTMF, 2 TONE and 5 TONE are displayed) and have no form
  in the executable: nothing to transpose.
- The DTMF window of the CPS under Wine waits for one more byte after each
  read response: `RE_EMU_TRAILER=1` adds it in
  `re/emu_stdio.py` (sandbox only). DTMF reading by the CPS under
  Windows on the real radio works; cause not established.

## Protocol observed on the real radio

Source: official CPS in a Windows 11 VM (VirtualBox, Prolific driver
4.10.0.0, port COM3), USB traffic of the PL2303 captured by VirtualBox
(`captures/win-read1.pcap`, decoded by `re/usbpcap.py` and `re/usbflow.py`
in `captures/win-read1-flow.txt`). Full read successful
("Complete reading data from the transceiver").

- Lines during the session: DTR high, RTS low (`SET_CONTROL_LINE_STATE`
  0x01 just before the handshake, 438.68 s). The CPS sends one byte per
  packet, spaced about 16 ms apart.
- Handshake `55 20 23 04 26 FF DC 02`, response in 0.02 s: 51 bytes
  `06`, 48 bytes, `55`, `05`, sent at about 10 ms per byte.
- The CPS sends `06` as soon as it holds 50 bytes. Without this ACK, the radio
  leaves the session after about 1.7 s and emits the text "Uart
  functional API interrupt example … Now please input:" (106 bytes,
  sessions of 33 s and 395 s in the capture). This text also follows the end
  of a full read (489.5 s).
- Read: `53 AH AL LEN`; response `58 AH AL LEN` + LEN bytes (LEN =
  0x10 for 0x3DF0, 0x40 otherwise). The PC sends `06`, the radio answers `06`.
  The CPS sometimes sticks this ACK to the next request (`06 53 00 00 40`,
  response `06 58 00 00 40 …`): this is the origin of the 69 bytes expected
  by the options window (0x4b9f30), and not a control byte.
- "Read from radio" read: block 0x3DF0 (16 bytes) then 200 blocks of
  64 bytes from 0x0000 to 0x31C0.
- Actual identification of this radio: bands A, B, C = 155-975; the
  three "texts" are digits (06 04 05 00 00 00, …), not ASCII.
- Without response, the CPS repeats the handshake every 5 s, 4 times
  (`captures/win-read2.txt`).
- Write ("Write to radio", `captures/win-write-flow.txt`): handshake,
  identification, `06`, reading of block 0x3DF0, `06` (response `06`), then
  784 frames from 0x0000 to 0x30F0: the first `58 AH AL 10` + 16 bytes,
  the following ones preceded by `06`; the radio answers `06` to each
  (about 85 ms per block, 67 s in total). The text "Uart functional
  API…" follows 1.7 s after the last frame.
- The CPS does not write what it read for 0x2000..0x23EF: it puts its standard
  5-tone frequency tables there (958 bytes changed from 0xff to the
  default values on this radio).
- The first 6 bytes of the identification follow the frequency of VFO A
  (155.975 then 129.525 after restoration): these are not band limits
  on this radio.
- 2026-11-15, after channel writes: well-formed frame (`06`, 48 bytes,
  `55`) whose three band fields are `00 00 00 00 0f 00` (not digits).
  `kta16` now marks such a band unknown instead of refusing the session;
  refusing it ended the session before the ACK, and the radio restarted.

### From Linux

The scripts cited below that chained several sessions
(`re/writeback.py`, `re/tui_*.py` except `tui_realread.py`,
`re/linestates.py`, `re/probe3.py`) have been deleted: repeated handshakes
make the radio restart in a loop. They remain in the git history
(commit 7e694a7). `re/readall.py` and `re/restore.py` remain, one session and one handshake each.

`re/readtest.py` (code `kta16/link.py`, pl2303 kernel driver) read
the identification, block 0x3DF0 and two channel blocks, identical to the
Windows capture (`captures/readtest-1.log`). The following attempts,
as well as a new attempt of the CPS under Windows, got no response
(`captures/readall-*.log`, `captures/linestates-1.log`,
`captures/win-read2.txt`): the radio no longer responds after the end of a
session, whatever the state of DTR and RTS. User observation: it restarts and displays a blue warning screen to pass by
3 presses on Exit. The link between this screen and the silence is an
unverified hypothesis.

Full read successful afterwards (`re/readall.py`, 201 blocks in 44.6 s):
`captures/radio-linux.img` is identical byte for byte to
`captures/radio-real.img` read by the CPS under Windows (same SHA-256,
61fd353f…). The radio therefore started responding again a few minutes after
the previous session.

Write from Linux (`re/writeback.py --restore`,
`captures/writeback-2.log`): after the CPS write, the original image
`captures/radio-real.img` was rewritten by the `kta16` code
(0x0000..0x30FF, 48 s) then read again: identical byte for byte. The radio
answers again about 110 s after a full read and 10 s after
a write (handshake repeated every 5 s).

Same write launched from the TUI interface driven without screen
(`re/tui_realwrite.py`, zone "all", safety copy created in
`~/.local/share/kta16/backups/`): re-read by `re/readall.py`
identical to the backup (`captures/radio-after-tui-write.img`).

Real change through the TUI (`re/tui_lfpx.py`): reading of the channel zone,
channel 3 (empty) set to 122.500 MHz in receive only and named
"LFPX", writing of the channel zone. Re-read
(`captures/radio-lfpx.img`): 16 bytes changed, all in the row of
channel 3 (0x0020..0x002F) and its name (0x1020..0x1023), decoded
as expected. User observation on the radio screen: "LFPX" on
ch002 (the radio and the CPS number from 0; the TUI now displays this
number), frequency not displayed. Backup restored
afterwards and re-read identically (`captures/writeback-3.log`).

Real change of the options (`re/tui_squelch.py`): squelch changed from
5 to 6 through the TUI list, writing of the options zone; re-read
(`captures/radio-squelch6.img`): only one byte changed, 0x0E02 (5 → 6).
The user reported during these sessions that the radio restarted in
a loop; it restarts at the end of each session and four sessions
followed one another (link not verified). Backup restored and re-read
identically (`captures/writeback-4.log`).

Errors corrected by this capture: the response header is indeed `58`;
the "DTR low, RTS high" setting of my first probes was the opposite
of the CPS one; the identification bytes that I judged inconsistent
are the real identification; the "flow" of 363,811 bytes seen with this
wrong setting is not explained (unverified hypothesis: the
firmware returns the received characters, as its text announces).

### Batch write and reads in the calibration zone (2026-11-11)

Four sessions of one handshake each, each after the user's agreement:
batch write by the TUI (`re/tui_batch.py`, channel and options zones,
`captures/batch-1.log`), re-read (`captures/batch.img`,
`captures/batch-2.log`), restoration (`re/restore.py`,
`captures/batch-3.log`), control re-read identical to the backup
(`captures/control2.img`, `cmp -l` with no difference).

- Differences read after the write: 0x0E02 (squelch 5 → 6), channel 3 and
  its name (LFPX), as expected; plus 0x0E61 (0 → 1) and 0x0E65 (1 → 2),
  not written by the TUI (dry run). Verified afterwards: side A set by the
  user to channel mode on WX01 (ch190), re-read
  (`captures/state-190.img`): 0x0E61 = 1 and 0x0E65 = 190, no other
  byte changed. The radio stores its display state there: 0x0E65 = current
  channel of side A, 0x0E61 = 1 in channel mode (value 0 seen
  on the original image, mode not identified). 0x0E62..0x0E64 and
  0x0E66..0x0E68 are probably sides B and C (unverified hypothesis). A write of the options zone resets these bytes to the value
  of the image, as the CPS does. The identification of the radio also
  carries the displayed frequency (`0016255000` on WX01).
- 0x3B90 read on the radio: `20 12 23 34 45 56 67 78 20 20 20 20 00 00 00
  ff`, the constant that the CPS already writes there; nothing to reproduce in the
  TUI.
- Band limits read (0x3D80): VHF0 108-136, VHF1 137-174, UHF0
  400-520, UHF1 300-336 MHz, all active (same values as the
  CPS Default).

### Transmit inhibition per channel (2026-11-15)

Measured by the user on the real radio with a PortaPack receiver, PTT pressed
on a channel with RX 123.450 MHz:

| TX bytes | Result |
|---|---|
| `FF FF FF FF` (empty) | carrier received: the radio transmits |
| 200.000 MHz | no signal on 123.450 or 200.000, radio stays out of the red PTT screen |
| any TX, RX in the VOR range | the radio never transmits |

The tool therefore writes 200 MHz (`channels.TX_OFF_HZ`) as "no transmit" on
voice channels (ATIS) and leaves TX empty on beacons (VOR, ILS). One channel,
low power; other power levels and other channels not tested.

### Keeping the session open (2026-11-15)

Measured by a probe outside the repository, one port open and one handshake:
30 reads of block 0x3DF0 (16 bytes) one second apart all answered, then a
full read (0x0000..0x3100, 43 s) succeeded in the same session, with no byte
left on the line and no "Uart functional API" text. The radio screen showed
"Read" from time to time. `kta16` keeps the session this way (`KEEPALIVE_S`) and releases it on `l` or quit.

Second probe, same day (one port open, one handshake): 10 s of keep-alive, a
full read (43 s), 60 s of keep-alive, a second full read, 20 s of keep-alive:
nothing lost, no restart. Then block 0x0000 written back with the bytes just
read (content unchanged): the next keep-alive read, 1.7 s after the write,
got `55 61 72 74` ("Uart") instead of the `58` reply header, and the radio
sent "interrupt example / Board receives characters then sends them out / Now
please input:". So a write ends the session, whatever the keep-alive: the
radio leaves it 1.7 s after its last accepted write frame and restarts, as in
the vendor software capture. Reads keep the session, writes end it.

Third probe: the port opened as `kta16` does (DTR high, RTS low) and left
open 15 s without any frame: the radio did not restart, at the opening, while
waiting or at the closing. Fourth probe: open, handshake 5 s later from the
normal screen (answered at once), 20 s of keep-alive, then silence with the port
still open: 1.1 s after the last frame the radio sent "Uart functional API
interrupt example…" and restarted (the user saw the restart right then). So the
restart comes from the end of a session, not from opening the port.

### Real image

`captures/radio-real.img` (rebuilt by `re/flow2img.py`): channels 1 and
2 at 121.500 MHz, channels 191 to 200 named `  WX01` to `  WX10` (spaces
0x20 in front, displayed "WX01" by the CPS), empty passwords (spaces),
DTMF, 2-tone, 5-tone, FM and calibration zones at 0xff, VFO A at 129.525 MHz.

## Address space above 0x3FFF (probe of 2026-11-11)

`re/probe_beyond.py`, real radio, one session, `S` frames only (log
`captures/beyond-20261111-234710.log`). The read command takes a 16-bit
address, so 0x0000..0xFFFF can be asked. The radio answers every request
with a valid reply (`58 AH AL 40` + 64 bytes, ACK answered by `06`) but
masks the address to 14 bits:

| Request | Content returned |
|---|---|
| 0x4000, 0x8000, 0xC000 | same 64 bytes as 0x0000 |
| 0x4040 | 64 bytes of 0x0040 |
| 0x3FC0 and 0xFFC0 | 64 bytes of 0x30 (ASCII `0`), an area the CPS never reads |

The memory served is the 16 KB configuration image only. The firmware code
is not reachable with this command, and the CPS contains no update routine
(see "Sources" in the README). Reading 0x0000
again at the end of the session gave the same bytes.

## Open points

- Behavior of the radio after a session (restart, blue screen,
  silence): to be observed with the user.
- Disp Way A/B/C and DTMF-ST: the CPS does not write them and does not
  read them back. In the writes `captures/optw-1.img` and `optw-2.img`, made
  with these lists on "Channel" then "Channel+Name" and OFF then ON
  (`captures/optw-1.png`, `optw-2.png`), no byte varies outside the
  fields of the table; in reading, 0x0E0C..0x0E0E do not change the
  display. These settings are therefore inert in the CPS.
- Bytes 0x0E01, 0x0E0C..0x0E0E, 0x0E21, 0x0E23, 0x0E84,
  0x0ED0..0x0EFF, block 0x0F60: kept as they are, role not established.
  Hypothesis not verified: they belong to settings of the QYT 8R CPS
  that the KT-A16 CPS does not show (ANI, alarm, emergency, language,
  display sub, DTMF gain, power-on message); see
  the QYT 8R CPS listed in the README.
- Calibration: 0x3B90, 0x3D36..0x3D37 and 0x3D3E..0x3D3F without readable label
  in the CPS.
- Files: the channel and options windows of the CPS save the complete `.dat`
  (1025 lines, `captures/chanwin.dat` produced under Windows, re-read
  and rewritten identically by `kta16/cpsfile.py`). In the sandbox, the
  DTMF, 2-tone, 5-tone and FM windows also save the complete `.dat`
  (`captures/def/sigd.dat`, `tt.dat`, `ft.dat`, `fmw.dat`);
  Adjust saves an `.adj` of 32 lines of 16 values without header,
  CR LF, bytes 0x3C00..0x3DFF (`captures/def/cal.adj`, 505 bytes out of
  512 equal to the image read; the other 7, last byte of each block of
  64, come from the CPS buffer).
- The official CPS crashes ("Run-time error 380") when opening its DTMF
  window when the radio's DTMF zone is at 0xff (seen under Windows with
  the data of the real radio).
