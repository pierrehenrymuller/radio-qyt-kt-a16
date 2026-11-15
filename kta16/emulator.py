"""Simulated radio, built from what the CPS expects (docs/protocol.md).

Used by the tests and, through a pty, to check that the vendor CPS accepts
our understanding of the protocol. Behaviour copied from the real radio
(USB capture of the vendor CPS under Windows, captures/win-read1-flow.txt):
identification 06 + 48 bytes + 55 + 05, read replies 58 AH AL LEN + data,
and 06 in answer to the ACK that follows each data block.
"""

from kta16 import protocol


def default_ident():
    """Identification payload: bands 136-174, 400-480, 220-260 MHz."""
    p = bytearray(protocol.IDENT_SIZE)
    p[0:6] = bytes([1, 3, 6, 1, 7, 4])
    p[0x10:0x16] = bytes([4, 0, 0, 4, 8, 0])
    p[0x20:0x26] = bytes([2, 2, 0, 2, 6, 0])
    p[0x0A:0x10] = b"KTA16 "
    p[0x1A:0x20] = b"EMUL  "
    p[0x26:0x30] = b"EMULATOR  "
    return bytes(p)


class RadioEmulator:
    """Byte-stream radio: feed() takes what the PC sends, returns the reply."""

    def __init__(
        self,
        image,
        ident=None,
        silent=False,
        handshake_reply=None,
        write_ack=protocol.ACK,
        ack_reply=protocol.ACK,
    ):
        if len(image) != protocol.IMAGE_SIZE:
            raise ValueError("image must be 16 KiB")
        self.image = image
        self.ident = ident or default_ident()
        self.silent = silent
        self.handshake_reply = handshake_reply
        self.write_ack = write_ack
        # Real radio: it answers 06 to the ACK that follows a data block.
        self.ack_reply = ack_reply
        self.acks_answered = 0
        self._block_sent = False
        self.connected = False
        self.log = []  # frames received, in order
        self._buf = b""

    def feed(self, data):
        self._buf += data
        out = b""
        while self._buf:
            frame, reply = self._step()
            if frame is None:
                break
            self.log.append(frame)
            if not self.silent:
                out += reply
        return out

    def _step(self):
        buf = self._buf
        if buf.startswith(protocol.HANDSHAKE):
            self._buf = buf[len(protocol.HANDSHAKE) :]
            self.connected = True
            reply = self.handshake_reply
            if reply is None:
                reply = (
                    protocol.ACK + self.ident + bytes([protocol.IDENT_TRAILER, 0x05])
                )
            return protocol.HANDSHAKE, reply
        if protocol.HANDSHAKE.startswith(buf):
            return None, b""  # wait for the rest of the handshake
        if buf[0] == protocol.ACK[0]:
            self._buf = buf[1:]
            if self._block_sent:
                self._block_sent = False
                self.acks_answered += 1
                return protocol.ACK, self.ack_reply
            return protocol.ACK, b""
        if buf[0] == protocol.CMD_READ and self.connected:
            if len(buf) < 4:
                return None, b""
            frame, self._buf = buf[:4], buf[4:]
            addr = frame[1] << 8 | frame[2]
            data = bytes(self.image[addr : addr + frame[3]])
            # Header: 'X' + address + length (the CPS searches for 0x58).
            header = bytes([protocol.REPLY_HEADER]) + frame[1:]
            self._block_sent = True
            return frame, header + data
        if buf[0] == protocol.CMD_WRITE and self.connected:
            if len(buf) < 4 + protocol.WRITE_SIZE:
                return None, b""
            frame, self._buf = buf[:20], buf[20:]
            addr = frame[1] << 8 | frame[2]
            self.image[addr : addr + protocol.WRITE_SIZE] = frame[4:]
            return frame, self.write_ack
        # Unknown byte: dropped, as a real radio would most likely do.
        frame, self._buf = buf[:1], buf[1:]
        return frame, b""


class FakeSerial:
    """Minimal pyserial stand-in wired to a RadioEmulator."""

    def __init__(self, emulator):
        self.emulator = emulator
        self.timeout = None
        self._rx = b""

    def write(self, data):
        self._rx += self.emulator.feed(bytes(data))
        return len(data)

    def read(self, size=1):
        chunk, self._rx = self._rx[:size], self._rx[size:]
        return chunk

    def reset_input_buffer(self):
        self._rx = b""

    def flush(self):
        pass

    def close(self):
        pass
