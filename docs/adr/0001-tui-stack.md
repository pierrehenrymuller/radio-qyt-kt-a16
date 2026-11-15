# ADR-0001 : TUI stack and reverse-engineering environment

## Context and Problem

The QYT KT-A16 airband handheld is programmed only with a Windows tool (`KT_A16_CPS.exe`, Visual Basic 6, MSComm, `9600,N,8,1` found in its strings). The owner works on Linux (Fedora 44, Wayland) and wants a terminal program with the same functions as the vendor tool, calibration screens included.

1. No Linux tool exists for this model (CHIRP support not confirmed).
2. The serial protocol and memory layout are undocumented.
3. The vendor binary is untrusted and must not run on the host.

## Constraints on the Decision

- Python, `uv` for the venv, `Makefile` driven, dependencies pinned in `pip_requirements.txt`.
- Containers with podman (rootless).
- Writes to the radio must be preceded by an automatic image backup.
- Tests first (red then green), including malformed input and truncated radio answers.

## Options Considered

### Option 1 : Python with Textual
**Advantages**
- Widgets for editable tables (200 channels), forms and dialogs.
- Headless test mode for screens.
- `pyserial` is available and a fake port is easy to write.
**Disadvantages**
- Large dependency tree.

### Option 2 : Python with urwid
**Advantages**
- Smaller.
**Disadvantages**
- Fewer widgets, less active, more code for tables.

### Option 3 : Python with curses
**Advantages**
- Standard library only.
**Disadvantages**
- Most code for a 200-row editable grid; no test harness.

## Decision

Option 1. Protocol discovery runs in a podman container (Wine plus `socat`, no network, vendor files mounted read-only) with a private Xvfb display; the host display is not shared because SELinux denies the container access to the host X socket and disabling SELinux labels would remove confinement of the untrusted binary. The TUI itself runs on the host.

## Consequences

### Positive
- Vendor binary never runs on the host.
- Captured protocol is documented in `docs/protocol.md` and drives the codec tests.

### Negative
- Textual pulls many dependencies.
- Wine-based capture depends on the vendor tool working under Wine.

## References

- QYT download page: https://www.qytradio.com/category/downloads/1_3
