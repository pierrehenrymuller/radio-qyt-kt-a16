"""Serial session with the radio: handshake, block reads and writes."""

import termios
import time

from kta16 import protocol
from kta16.protocol import ProtocolError

# Watchdog timer of the CPS after each frame (VA 0x48f497, 2000 ms).
DEFAULT_TIMEOUT = 2.0

# Port lost (cable pulled, adapter renumbered): termios.error is not an OSError.
PORT_ERRORS = (OSError, termios.error)


def open_port(path, dtr=True, rts=False):
    """Open the serial port once (opening it does not restart the radio; ending a session does).

    Line states of the vendor CPS during a session (USB capture under
    Windows: SET_CONTROL_LINE_STATE 0x01): DTR high, RTS low.
    """
    import serial

    ser = serial.Serial()
    ser.port = path
    ser.baudrate = 9600
    ser.bytesize, ser.parity, ser.stopbits = 8, "N", 1
    ser.timeout = 0.1
    ser.dtr, ser.rts = dtr, rts
    ser.open()
    return ser


class Radio:
    def __init__(self, ser, timeout=DEFAULT_TIMEOUT):
        self.ser = ser
        self.timeout = timeout
        self.ident = None
        self._wrote = False
        # True from a successful handshake to the first error: the radio leaves
        # the session (and restarts) about 1.7 s after the last frame.
        self.session_alive = False

    def _read_exact(self, size, what):
        data = b""
        deadline = time.monotonic() + self.timeout
        while len(data) < size:
            chunk = self.ser.read(size - len(data))
            if chunk:
                data += chunk
            elif time.monotonic() > deadline:
                raise ProtocolError(
                    f"timeout waiting for {what}: got {len(data)}/{size} bytes "
                    f"{data[:16].hex(' ')}"
                )
        return data

    def _drain(self, quiet=0.05):
        """Discard bytes that follow a reply (the CPS clears InBufferCount)."""
        end = time.monotonic() + quiet
        while time.monotonic() < end:
            if self.ser.read(64):
                end = time.monotonic() + quiet

    def connect(self, attempts=1, interval=5.0):
        """Handshake, identification, then ACK at once.

        The radio leaves the session (and prints a demo banner) if the ACK
        does not follow the identification within about 1.5 s. Like the
        vendor CPS, the handshake can be repeated every `interval` seconds:
        the radio stays silent while it restarts or shows its warning screen.
        """
        error = None
        self.session_alive = False
        for attempt in range(attempts):
            started = time.monotonic()
            try:
                return self._handshake()
            except ProtocolError as exc:
                error = exc
            if attempt + 1 < attempts:
                time.sleep(max(0.0, interval - (time.monotonic() - started)))
        raise ProtocolError(f"no answer to {attempts} handshakes: {error}")

    def _handshake(self):
        self.ser.reset_input_buffer()
        self.ser.write(protocol.HANDSHAKE)
        raw = self._read_exact(protocol.IDENT_SIZE + 2, "identification")
        self.ident = protocol.parse_ident(raw)
        self._wrote = False
        self.ser.write(protocol.ACK)
        self._drain()  # tail byte of the identification
        self.session_alive = True
        return self.ident

    def _require_session(self):
        if self.ident is None:
            raise ProtocolError("no session: call connect() first")

    def read_block(self, addr, size=protocol.READ_SIZE):
        """Request, 58-header reply, ACK, and the radio's 06 in return."""
        try:
            data = self._read_block(addr, size)
        except (ProtocolError, *PORT_ERRORS):
            self.session_alive = False
            raise
        self._wrote = (
            False  # acknowledged: a write now is a first frame, no ACK in front
        )
        return data

    def _read_block(self, addr, size):
        self._require_session()
        self.ser.write(protocol.read_request(addr, size=size))
        reply = self._read_exact(4 + size, f"block {addr:#06x}")
        data = protocol.parse_read_reply(reply, size, addr)
        self.ser.write(protocol.ACK)
        try:
            confirm = self._read_exact(1, f"ACK of block {addr:#06x}")
        except ProtocolError as exc:
            raise ProtocolError(
                f"radio did not confirm the ACK of {addr:#06x}"
            ) from exc
        if confirm != protocol.ACK:
            raise ProtocolError(f"bad ACK after {addr:#06x}: {confirm.hex()}")
        return data

    def write_block(self, addr, data):
        try:
            self._write_block(addr, data)
        except (ProtocolError, *PORT_ERRORS):
            self.session_alive = False
            raise

    def _write_block(self, addr, data):
        self._require_session()
        # First frame of a session: no leading ACK (the last block read was
        # already acknowledged); afterwards "06 58 ..." like the CPS.
        self.ser.write(protocol.write_frame(addr, data, ack=self._wrote))
        self._wrote = True
        ack = self._read_exact(1, f"ACK of write {addr:#06x}")
        if ack != protocol.ACK:
            raise ProtocolError(f"no ACK after write {addr:#06x}: got {ack.hex()}")

    def read_range(self, start, end, progress=None):
        addrs = range(start, end, protocol.READ_SIZE)
        out = bytearray()
        for i, addr in enumerate(addrs, 1):
            out += self.read_block(addr)
            if progress:
                progress(i, len(addrs))
        return bytes(out)

    def write_range(self, start, data, progress=None):
        if len(data) % protocol.WRITE_SIZE:
            raise ValueError("data length must be a multiple of 16")
        offsets = range(0, len(data), protocol.WRITE_SIZE)
        for i, off in enumerate(offsets, 1):
            self.write_block(start + off, data[off : off + protocol.WRITE_SIZE])
            if progress:
                progress(i, len(offsets))
