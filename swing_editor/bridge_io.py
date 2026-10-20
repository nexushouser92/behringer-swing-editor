"""Runs the Swing ↔ DAW bridge (bridge.py) over real MIDI ports.

- The DAW side uses two loopMIDI virtual ports: the bridge writes to "Swing to DAW" and listens to
  "DAW to Swing".
- Windows forbids calling MIDI functions from inside a MIDI input callback, so callbacks only queue
  messages and one forwarding thread sends them.
- TappedPort wraps the Swing's port for link.py: every SysEx it receives (Swing status, MMC) is also
  handed to the bridge, including the ones device.py skips while reading or writing settings.
"""
import queue
import threading

from . import midi_win
from .bridge import Bridge

TO_DAW_NAME = "Swing to DAW"
FROM_DAW_NAME = "DAW to Swing"


class BridgeRunner:
    def __init__(self, opener=midi_win.open_by_name, settings=None, to_daw=TO_DAW_NAME, from_daw=FROM_DAW_NAME):
        self.opener, self.to_daw_name, self.from_daw_name = opener, to_daw, from_daw
        self.bridge = Bridge(settings)
        self.daw_out = self.daw_in = None
        self.swing = None
        self.last_error = None
        self.counts = {"to_daw": 0, "to_swing": 0, "filtered": 0}
        self._queue = queue.Queue()
        self._thread = None

    # ------------------------------------------------------------- lifecycle
    def open(self):
        """Open both virtual ports and start forwarding. Raises midi_win.MidiError if they are missing."""
        try:
            self.daw_out = self.opener(out_name=self.to_daw_name)
            self.daw_in = self.opener(in_name=self.from_daw_name)
        except BaseException:
            self.close()
            raise
        self.daw_in.on_short = lambda status, d1, d2: self._queue.put(("daw", status, d1, d2))
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def close(self):
        if self._thread is not None:
            self._queue.put(None)
            self._thread.join(2)
            self._thread = None
        for port in (self.daw_in, self.daw_out):
            if port is not None:
                port.on_short = None
                try:
                    port.close()
                except (midi_win.MidiError, OSError):
                    pass
        self.daw_in = self.daw_out = None

    def attach(self, swing_port):
        self.swing = swing_port

    def detach(self):
        """The Swing went away: silence anything it left on in the DAW."""
        self.swing = None
        self.panic()

    # ------------------------------------------------------------- inputs (any thread)
    def from_swing_short(self, status, data1, data2):
        self._queue.put(("swing", status, data1, data2))

    def from_swing_sysex(self, message):
        self._queue.put(("swing_sysex", message))

    def panic(self):
        self._queue.put(("panic",))

    # ------------------------------------------------------------- forwarding thread
    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            self.process(item)

    def process(self, item):
        """Route one queued item (called by the forwarding thread, or directly by tests)."""
        kind, args = item[0], item[1:]
        b = self.bridge
        if kind == "swing":
            out, target = b.from_swing_short(*args), self.daw_out
        elif kind == "swing_sysex":
            out, target = b.from_swing_sysex(*args), self.daw_out
        elif kind == "daw":
            out, target = b.from_daw_short(*args), self.swing
        else:
            out, target = b.panic(), self.daw_out
        if not out:
            if kind in ("swing", "daw") or (kind == "swing_sysex" and args[0][:2] == bytes([0xF0, 0x7F])):
                self.counts["filtered"] += 1
            return
        if target is None:
            return
        try:
            for message in out:
                if message[0] == "short":
                    target.send_short(*message[1:])
                else:
                    target.send(message[1])
                self.counts["to_swing" if target is self.swing else "to_daw"] += 1
        except (midi_win.MidiError, OSError) as e:
            self.last_error = e


class TappedPort:
    """A Swing port that also gives every SysEx it receives to a bridge (when one is set)."""

    def __init__(self, port):
        self.port = port
        self.bridge = None

    def set_bridge(self, runner):
        self.bridge = runner
        self.port.on_short = runner.from_swing_short if runner is not None else None

    def send(self, data):
        self.port.send(data)

    def send_short(self, *message):
        self.port.send_short(*message)

    def receive(self, timeout):
        message = self.port.receive(timeout)
        if message is not None and self.bridge is not None:
            self.bridge.from_swing_sysex(message)
        return message

    def pump(self):
        """Hand everything waiting to the bridge (link.py calls this between other work)."""
        while self.receive(0) is not None:
            pass

    def drain(self):
        if self.bridge is not None:
            self.pump()
        self.port.drain()

    def close(self):
        self.port.on_short = None
        self.port.close()
