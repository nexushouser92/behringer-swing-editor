"""Test doubles: a fake Swing (port level) and a fake winmm.dll. No MIDI device is needed."""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swing_editor import midi_win, protocol  # noqa: E402

STATUS = bytes.fromhex("f0 00 20 32 7f 42 70 00 01 05 f7")   # sent by a real Swing on its own
VERSIONS = ((1, 0, 0), (1, 1, 52))


class FakeSwing:
    """A port (send/receive/drain/close) that answers like the real Swing (research/PROTOCOL.md).

    respond=False: silent. apply_writes=False: acknowledges writes but ignores them.
    no_ack: does not acknowledge writes. status_every_read: adds a status message before each reply.
    values: raw settings by id (defaults to the values read from a real Swing).
    """

    def __init__(self, values=None, respond=True, apply_writes=True, no_ack=False,
                 status_every_read=False, silent_reads=0):
        self.values = dict(protocol.READ_DEFAULTS if values is None else values)
        self.respond, self.apply_writes, self.no_ack = respond, apply_writes, no_ack
        self.status_every_read = status_every_read
        self.silent_reads = silent_reads   # number of reads to ignore before answering
        self.sent, self.inbox = [], []
        self.closed = False

    def reply(self, *body):
        return protocol.HEADER + bytes(body) + bytes([0xF7])

    def send(self, data):
        data = bytes(data)
        self.sent.append(data)
        if not self.respond:
            return
        cmd = data[6]
        if len(data) == 8 and cmd == protocol.CMD_PRODUCT_INFO:
            self.inbox.append(self.reply(0, *VERSIONS[0], *VERSIONS[1]))
        elif len(data) == 8:
            if self.silent_reads:
                self.silent_reads -= 1
                return
            if self.status_every_read:
                self.inbox.append(STATUS)
            self.inbox.append(self.reply(cmd, self.values[cmd]))
        elif len(data) == 9:
            if self.apply_writes:
                self.values[cmd] = data[7]
            if not self.no_ack:
                self.inbox.append(self.reply(cmd))

    def receive(self, timeout):
        return self.inbox.pop(0) if self.inbox else None

    def drain(self):
        self.inbox.clear()

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def writes(self):
        return [m for m in self.sent if len(m) == 9]


class FakeWinmm:
    """Stands in for winmm.dll. Arguments passed with ctypes.byref() are reached through ._obj.

    on_send(fake, data) is called for every SysEx sent, and can answer with fake.deliver().
    """

    def __init__(self, ins=("Behringer Swing",), outs=("Behringer Swing",), on_send=None,
                 in_open=0, out_open=0, long_msg=0, still_playing=0):
        self.ins, self.outs = list(ins), list(outs)
        self.on_send = on_send
        self.in_open_res, self.out_open_res, self.long_msg_res = in_open, out_open, long_msg
        self.still_playing = still_playing
        self.callback = None
        self.available = []       # input headers the "driver" may fill
        self.prepared_in = []
        self.sent = []
        self.added = self.out_resets = 0
        self.in_closed = self.out_closed = 0
        self.out_prepared = self.out_unprepared = 0
        self.in_unprepared = 0
        self.opened_in = self.opened_out = None
        self.short_sent, self.short_res = [], 0

    # --- device lists
    def midiInGetNumDevs(self):
        return len(self.ins)

    def midiOutGetNumDevs(self):
        return len(self.outs)

    def midiInGetDevCapsW(self, i, caps_ref, size):
        caps_ref._obj.szPname = self.ins[i]
        return 0

    def midiOutGetDevCapsW(self, i, caps_ref, size):
        caps_ref._obj.szPname = self.outs[i]
        return 0

    # --- input
    def midiInOpen(self, handle_ref, index, callback, instance, flags):
        if self.in_open_res:
            return self.in_open_res
        handle_ref._obj.value = 0x100
        self.callback, self.opened_in = callback, index
        return 0

    def midiInPrepareHeader(self, h, hdr_ref, size):
        self.prepared_in.append(hdr_ref._obj)
        return 0

    def midiInAddBuffer(self, h, hdr_ref, size):
        self.available.append(hdr_ref._obj)
        self.added += 1
        return 0

    def midiInStart(self, h):
        return 0

    def midiInStop(self, h):
        return 0

    def midiInReset(self, h):
        # The real driver hands every queued buffer back with 0 bytes recorded.
        while self.available:
            hdr = self.available.pop(0)
            hdr.dwBytesRecorded = 0
            self.callback(0x100, midi_win.MIM_LONGDATA, 0, ctypes.addressof(hdr), 0)
        return 0

    def midiInUnprepareHeader(self, h, hdr_ref, size):
        self.in_unprepared += 1
        return 0

    def midiInClose(self, h):
        self.in_closed += 1
        return 0

    def deliver(self, data, chunk=None):
        """Simulate bytes arriving from the device, in buffers of at most `chunk` bytes."""
        chunk = chunk or len(data)
        for start in range(0, len(data), chunk):
            piece = data[start:start + chunk]
            hdr = self.available.pop(0)
            ctypes.memmove(hdr.lpData, piece, len(piece))
            hdr.dwBytesRecorded = len(piece)
            self.callback(0x100, midi_win.MIM_LONGDATA, 0, ctypes.addressof(hdr), 0)

    # --- output
    def midiOutOpen(self, handle_ref, index, callback, instance, flags):
        if self.out_open_res:
            return self.out_open_res
        handle_ref._obj.value = 0x200
        self.opened_out = index
        return 0

    def midiOutPrepareHeader(self, h, hdr_ref, size):
        self.out_prepared += 1
        return 0

    def midiOutLongMsg(self, h, hdr_ref, size):
        if self.long_msg_res:
            return self.long_msg_res
        hdr = hdr_ref._obj
        data = ctypes.string_at(hdr.lpData, hdr.dwBufferLength)
        self.sent.append(data)
        if self.on_send:
            self.on_send(self, data)
        return 0

    def midiOutShortMsg(self, h, message):
        self.short_sent.append(message)
        return self.short_res

    def midiOutUnprepareHeader(self, h, hdr_ref, size):
        if self.still_playing:
            self.still_playing -= 1
            return midi_win.MIDIERR_STILLPLAYING
        self.out_unprepared += 1
        return 0

    def midiOutReset(self, h):
        self.out_resets += 1
        self.still_playing = 0
        return 0

    def midiOutClose(self, h):
        self.out_closed += 1
        return 0


def swing_replies(fake, data):
    """on_send handler for FakeWinmm: answer product info and reads like a Swing with default values."""
    if len(data) == 8:
        cmd = data[6]
        body = [0, *VERSIONS[0], *VERSIONS[1]] if cmd == 0 else [cmd, protocol.READ_DEFAULTS[cmd]]
        fake.deliver(protocol.HEADER + bytes(body) + bytes([0xF7]))
