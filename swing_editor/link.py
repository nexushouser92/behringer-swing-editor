"""Keeps the Swing linked while the editor is open.

- Looks for the Swing every POLL_INTERVAL seconds and opens it as soon as it appears.
- On linking, reads the product info and all settings. Changes made in the window while the Swing
  was away are then applied on top of what was read.
- push(settings) schedules the write WRITE_DELAY seconds after the latest change. Only the settings
  that differ from what the Swing has are written, each one verified by reading it back.
- If the Swing is unplugged, the port is closed and the search starts again.

All device work happens in step(), called from one worker thread (or directly by tests).
The window reads the results from `events`, a queue of (kind, payload):
  ("searching", error or None) ("linked", None) ("info", versions) ("settings", SwingSettings)
  ("writing", None) ("written", SwingSettings) ("write_failed", error)
"""
import queue
import threading
import time

from . import device, midi_win

POLL_INTERVAL = 1.0
WRITE_DELAY = 0.3


class SwingLink:
    def __init__(self, opener=midi_win.open_swing, lister=midi_win.list_ports, clock=time.monotonic,
                 write_delay=WRITE_DELAY):
        self.opener, self.lister, self.clock = opener, lister, clock
        self.write_delay = write_delay
        self.events = queue.Queue()
        self.port = None
        self.on_swing = None        # settings the Swing has (last read or written)
        self._lock = threading.Lock()
        self._pending = None        # settings waiting to be written
        self._due = 0.0
        self._want_read = False
        self._next_poll = 0.0
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------- called by the window
    @property
    def linked(self):
        return self.port is not None

    @property
    def has_pending(self):
        return self._pending is not None

    def push(self, settings):
        """Apply these settings soon; a newer push before then replaces it."""
        with self._lock:
            self._pending = settings
            self._due = self.clock() + self.write_delay

    def flush(self):
        with self._lock:
            self._due = 0.0

    def request_read(self):
        self._want_read = True

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout=3.0):
        """Write anything still waiting, then close the port."""
        self.flush()
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        if self.linked and self._pending is not None:
            self.step()
        self._close()

    # ------------------------------------------------------------- worker
    def _run(self):
        while not self._stop.is_set():
            self.step()
            self._stop.wait(0.05)

    def step(self):
        now = self.clock()
        if self.port is None:
            if now >= self._next_poll:
                self._next_poll = now + POLL_INTERVAL
                self._try_link()
            return
        if now >= self._next_poll:
            self._next_poll = now + POLL_INTERVAL
            if not self._present():
                self._drop(None)
                return
        if self._want_read:
            self._want_read = False
            if not self._read():
                return
        with self._lock:
            settings = self._pending if self._pending is not None and now >= self._due else None
        if settings is not None:
            self._write(settings)

    def _present(self):
        try:
            ins, outs = self.lister()
        except OSError:
            return False
        return midi_win.find_port(ins) is not None and midi_win.find_port(outs) is not None

    def _try_link(self):
        if not self._present():
            return
        try:
            port = self.opener()
        except (midi_win.MidiError, OSError) as e:
            self.events.put(("searching", e))   # the Swing is there but its port could not be opened
            return
        self.port = port
        self.events.put(("linked", None))
        try:
            self.events.put(("info", device.read_product_info(port)))
        except (device.DeviceError, midi_win.MidiError, OSError) as e:
            self._drop(e)
            return
        if self._read() and self._pending is not None:
            with self._lock:   # changes made while the Swing was away: apply them over what it has
                self._pending = self.on_swing.with_editable_from(self._pending)
            self.flush()

    def _read(self):
        try:
            self.on_swing = device.read_all(self.port)
        except (device.DeviceError, midi_win.MidiError, OSError) as e:
            self._drop(e)
            return False
        self.events.put(("settings", self.on_swing))
        return True

    def _write(self, settings):
        if not settings.differences(self.on_swing):
            self._clear_pending(settings)
            return
        self.events.put(("writing", None))
        try:
            for pid in settings.differences(self.on_swing):
                device.write_param(self.port, pid, settings[pid])
                self.on_swing = self.on_swing.set(pid, settings[pid])
        except device.VerifyError as e:
            self._want_read = True   # find out what the Swing really has
            self._clear_pending(settings)
            self.events.put(("write_failed", e))
            return
        except (device.DeviceError, midi_win.MidiError, OSError) as e:
            self.events.put(("write_failed", e))
            self._drop(e)   # keep the settings waiting: they are applied once the Swing is back
            return
        self._clear_pending(settings)
        self.events.put(("written", self.on_swing))

    def _clear_pending(self, written):
        with self._lock:
            if self._pending is written:   # unless a newer change arrived meanwhile
                self._pending = None

    def _drop(self, error):
        self._close()
        self._next_poll = self.clock() + POLL_INTERVAL
        self.events.put(("searching", error))

    def _close(self):
        port, self.port = self.port, None
        if port is not None:
            try:
                port.close()
            except (midi_win.MidiError, OSError):
                pass
