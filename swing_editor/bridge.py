"""Swing ↔ DAW bridge: the filtering rules, with no MIDI I/O (see research/MESSAGE_FLOW.md).

The editor keeps the Swing's USB port and passes its music on to a virtual port the DAW listens to,
and the DAW's clock back to the Swing. On the way it removes the messages that cause loops or false
actions. Every method returns the messages to send as tuples:
  ("short", status, data1, data2)   ("sysex", bytes)

    Swing → DAW: notes, controllers, aftertouch, pitch bend and MMC pass, except:
      - real-time messages (clock, start, stop): the Swing echoes the DAW's clock back
      - the Swing's own status SysEx: used here to follow the buttons, never forwarded
      - the transport message that leaks when Arp + Rec/Stop/Play is used to pick the clock source
    DAW → Swing: real-time messages only by default (clock, start, continue, stop, song position);
      notes from the DAW would transpose the Swing's sequencer. SysEx from the DAW is never passed.
"""
import time

from . import protocol

CLOCK, START, CONTINUE, STOP, SONG_POSITION = 0xF8, 0xFA, 0xFB, 0xFC, 0xF2
REALTIME_TO_SWING = {CLOCK, START, CONTINUE, STOP, SONG_POSITION}
CC_ALL_NOTES_OFF, CC_SUSTAIN, CC_ALL_SOUND_OFF = 123, 64, 120
MMC_PREFIX = bytes([0xF0, 0x7F])

# Swing status events (command 70, first byte 06): odd = press, even = release.
EVENT_ARP_PRESS, EVENT_ARP_RELEASE = 0x19, 0x1A
EVENT_REC_RELEASE, EVENT_STOP_RELEASE, EVENT_PLAY_RELEASE = 0x12, 0x14, 0x10
# Arp + Rec / Stop / Play choose the clock source INT / MIDI / USB. For each: the button whose
# release must be swallowed, its release event, and the transport setting with its CC.
CLOCK_COMBOS = {
    0x1D: ("rec", EVENT_REC_RELEASE),
    0x1E: ("stop", EVENT_STOP_RELEASE),
    0x1F: ("play", EVENT_PLAY_RELEASE),
}
SWALLOW_TIMEOUT = 5.0   # give up waiting for the button release after this many seconds
RELEASE_GRACE = 0.15    # keep filtering this long after the release event


class Bridge:
    def __init__(self, settings=None, notes_to_swing=False, clock=time.monotonic):
        self.settings = settings or protocol.SwingSettings()
        self.notes_to_swing = notes_to_swing
        self.clock = clock
        self.held = set()            # (channel, note) sounding in the DAW, sent by the Swing
        self.sustain = set()         # channels whose sustain (CC 64) is down
        self._swallow = None         # (button, release event, until) while a clock combo is pending

    # ------------------------------------------------------------- Swing → DAW
    def from_swing_short(self, status, data1=0, data2=0):
        if status >= 0xF0:
            return []                # clock and other real-time: echoes of the DAW's own clock
        kind, channel = status & 0xF0, status & 0x0F
        if kind == 0xB0 and self._is_swallowed_cc(channel, data1):
            return []
        if kind == 0x90 and data2 > 0:
            self.held.add((channel, data1))
        elif kind == 0x80 or kind == 0x90:
            self.held.discard((channel, data1))
        elif kind == 0xB0 and data1 == CC_SUSTAIN:
            (self.sustain.add if data2 >= 64 else self.sustain.discard)(channel)
        elif kind == 0xB0 and data1 in (CC_ALL_NOTES_OFF, CC_ALL_SOUND_OFF):
            self.held = {k for k in self.held if k[0] != channel}
        return [("short", status, data1, data2)]

    def from_swing_sysex(self, message):
        message = bytes(message)
        if message[:2] == MMC_PREFIX:
            return [] if self._swallowing() else [("sysex", message)]
        reply = protocol.parse(message)
        if isinstance(reply, protocol.Status) and len(reply.data) >= 2 and reply.data[0] == 0x06:
            self._on_button(reply.data[1])
        return []                    # the Swing's own SysEx never reaches the DAW

    def _on_button(self, event):
        if event in CLOCK_COMBOS:
            button, release = CLOCK_COMBOS[event]
            self._swallow = (button, release, self.clock() + SWALLOW_TIMEOUT)
        elif self._swallow is not None and event == self._swallow[1]:
            # That button's release has gone by. Its CC arrives through another winmm path in the
            # same millisecond, in either order, so keep filtering a moment longer.
            button, release, _ = self._swallow
            self._swallow = (button, release, self.clock() + RELEASE_GRACE)

    def _swallowing(self):
        if self._swallow is not None and self.clock() > self._swallow[2]:
            self._swallow = None
        return self._swallow is not None

    def _is_swallowed_cc(self, channel, cc):
        if not self._swallowing():
            return False
        button = self._swallow[0]
        s = self.settings
        return channel == s[f"{button}_channel"] and cc == s[f"{button}_cc"]

    # ------------------------------------------------------------- DAW → Swing
    def from_daw_short(self, status, data1=0, data2=0):
        if status in REALTIME_TO_SWING:
            return [("short", status, data1, data2)]
        if self.notes_to_swing and status < 0xF0:
            return [("short", status, data1, data2)]
        return []

    # ------------------------------------------------------------- panic
    def panic(self):
        """Messages for the DAW that silence everything the Swing may have left on."""
        out = [("short", 0x80 | ch, note, 0) for ch, note in sorted(self.held)]
        for ch in range(16):
            out.append(("short", 0xB0 | ch, CC_SUSTAIN, 0))
            out.append(("short", 0xB0 | ch, CC_ALL_NOTES_OFF, 0))
        self.held.clear()
        self.sustain.clear()
        return out
