# Release notes

## 1.1.0

- Aero names with several frequencies are numbered in the search list
  (`BD APP1`, `BD APP2`...), so a name is one frequency.
- `u` on the Channels tab: channels named like an aero line take its current
  frequency (TX follows only if it was equal to RX); a dialog lists the
  changes, shown in the pending changes. Run `make aero` before starting.
  The first update also renames a channel kept under a plain name (`BD APP`)
  to its numbered name (`BD APP2`) when its RX is one of that name's frequencies.

## 1.0.0

First public version.

- Read and write the QYT KT-A16 over its USB programming cable, with the
  serial sequence of the vendor software (one handshake per session,
  DTR high, RTS low).
- Every screen of the vendor software: channels, options and VFOs, DTMF,
  2-tone, 5-tone, FM stations, calibration ("Adjust"), passwords, and a hex
  view of each memory zone, in a sidebar grouped as Memories, Settings,
  Signalling and Advanced, under a status bar (port, last read).
- "To write" panel: every change not yet in the radio, before and after,
  zones never read listed once; changed channel rows are marked.
- Channel edit: two columns, segmented buttons for power and modulation,
  switches for busy lock, scan and scrambler, a non-blocking warning when TX
  is outside the bands the radio reports, buttons always visible.
- Two themes, Atelier (dark, default) and Papier (light), switched with `t`.
- French and English interface, from the locale or `--lang`; English for any
  locale that is not French.
- "Default" and "Clear" of the vendor screens, with the values measured on
  the vendor software (the "Default" of the channel window is left out:
  it overwrites channels 0 to 6).
- Batch write of every changed zone in one session (one radio restart).
- Files: raw `.img`, the `.dat` of the vendor software, and the `.adj` of
  its calibration screen.
- Safety: backup of the image before every write (owner-only folder),
  typed confirmation for calibration writes, calibration and password
  bytes refused in the hex view, confirmation before quitting with
  unsaved changes.
- Aero search in the channel edit: French aeronautical frequencies (radio
  services of 441 aerodromes, VOR, flight information such as Paris
  Information) from the SIA eAIP and VAC charts, with 7-character names
  (`PX GND`, `PX TWR`, `PX ATIS`). Name and RX are filled in, TX = RX (200 MHz for an ATIS, empty for a
  VOR, see the transmit inhibition below). `make aero` rebuilds `kta16/aero.json` from the current AIRAC
  cycle and fails if the VAC layout changed.
- The band warning is not shown when the band limits are unknown (image never
  read from the radio, or a file).
- Tested against a radio emulator; batch write, options and channel writes
  checked on a real radio.

- Port choice at start: without `--port`, a list of the USB-serial adapters,
  the Prolific PL2303 cable (`067b:2303`) first and marked recommended; Esc
  starts without a port. A port error (cable pulled, adapter renumbered)
  closes the port and opens the list again instead of crashing.
- The identification of the radio is accepted when its band fields are not
  decimal digits (seen on the real radio); the bands are then shown as `?`.
- The session stays open while the application runs: a read of the password
  block every second keeps the radio in it, so reads follow each other
  without a restart (measured: 100 s of keep-alive around two full reads in one
  session). A write ends the session: the radio leaves it 1.7 s after the
  write and restarts, as with the vendor software, so the status bar says so
  and the next action waits for the warning screen. `l` releases the radio,
  quitting does too.
- Opening the port does not restart the radio (measured: 15 s with the port
  open and no frame, no restart). The radio restarts when a session ends (a
  write, `l`, a lost session): the next read or write then waits, in a window,
  for you to go past its warning screen before the handshake.
- Transmit inhibition per channel, from measurements on the real radio (an
  empty TX still transmits, a TX at 200 MHz does not, the VOR band never
  does): a "Transmit (TX)" switch on every channel form. Off writes 200 MHz,
  never shown (blank in the channel list, "TX désactivé" in the pending
  changes); in the beacon band (108 to 117.975 MHz) Off leaves TX empty.
  Picking an ATIS or a VOR/ILS in the aero search sets it to Off; an
  aerodrome with "VOR" in its name (AVORD) keeps TX = RX.
- Aero search with several lines ticked (Space): one channel per line from the
  current channel on, with the form settings and the TX rule of each line.
  The free channels at the current place are used first, then every channel
  after them moves on by the missing number of places; nothing changes if the
  last channel would go past 199.
- Channel list: Space picks a channel up, the arrows move it, Space or Enter
  drops it, Esc puts it back. Shift+arrows or a click then Shift+click select
  a block of channels to move together.
- `make demo`: the emulated radio with demo channels, for screenshots.
