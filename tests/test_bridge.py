"""Tests for bridge.py, replaying message sequences recorded from the real Swing (research/*.log).

Run with: python -m unittest discover -s tests
"""
import unittest

import fakes  # noqa: F401  (adds the project to sys.path)
from swing_editor import bridge, protocol
from swing_editor.protocol import SwingSettings
from test_link import Clock

MMC_PLAY = bytes.fromhex("f0 7f 7f 06 02 f7")
MMC_REC_STROBE = bytes.fromhex("f0 7f 7f 06 06 f7")
MMC_REC_EXIT = bytes.fromhex("f0 7f 7f 06 07 f7")


def status(*data):
    """A Swing status message (command 70) carrying data, packed 8-in-7 like the real ones."""
    packed = bytearray()
    for start in range(0, len(data), 7):
        group = data[start:start + 7]
        packed.append(sum(((b >> 7) & 1) << i for i, b in enumerate(group)))
        packed.extend(b & 0x7F for b in group)
    return protocol.HEADER + bytes([protocol.CMD_STATUS]) + bytes(packed) + bytes([0xF7])


def button(event):
    return status(0x06, event)


class StatusHelperTests(unittest.TestCase):
    def test_round_trip_with_the_real_parser(self):
        self.assertEqual(protocol.parse(button(0x1D)), protocol.Status(bytes([0x06, 0x1D])))
        tempo = status(0x04, 0x4A, 0x0C, 0xF0, 0x42, 0x05, 0xFC)
        self.assertEqual(protocol.parse(tempo).data, bytes([0x04, 0x4A, 0x0C, 0xF0, 0x42, 0x05, 0xFC]))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        # DAW mode transport: channel 16, CC 54 / 51 / 50
        settings = SwingSettings().set("play_channel", 15).set("stop_channel", 15).set("rec_channel", 15)
        self.b = bridge.Bridge(settings, clock=self.clock)

    def to_daw(self, *messages):
        """Feed ("s", status, d1, d2) short messages and SysEx bytes from the Swing; return what reaches the DAW."""
        out = []
        for m in messages:
            out += self.b.from_swing_sysex(m) if isinstance(m, bytes) else self.b.from_swing_short(*m)
        return out

    # --- music passes
    def test_notes_controllers_and_pitch_pass(self):
        msgs = [(0x90, 60, 100), (0x80, 60, 0), (0xB0, 1, 64), (0xD0, 40, 0), (0xE0, 0, 64)]
        self.assertEqual(self.to_daw(*msgs), [("short", *m) for m in msgs])

    def test_transport_passes_when_no_combo(self):
        out = self.to_daw((0xBF, 54, 127), MMC_PLAY, button(0x0F), (0xBF, 54, 0), button(0x10))
        self.assertEqual(out, [("short", 0xBF, 54, 127), ("sysex", MMC_PLAY), ("short", 0xBF, 54, 0)])

    # --- loops
    def test_clock_echoed_by_the_swing_never_goes_back(self):
        self.assertEqual(self.to_daw((0xFA,), (0xF8,), (0xF8,), (0xFC,), (0xFE,)), [])

    def test_swing_status_sysex_is_never_forwarded(self):
        self.assertEqual(self.to_daw(status(0x01, 0x05), status(0x04, 0x4A, 0x0C, 0xF0, 0x42, 0x05, 0xFC),
                                     button(0x19)), [])

    def test_daw_sends_only_real_time_to_the_swing(self):
        self.assertEqual(self.b.from_daw_short(0xFA), [("short", 0xFA, 0, 0)])
        self.assertEqual(self.b.from_daw_short(0xF8), [("short", 0xF8, 0, 0)])
        self.assertEqual(self.b.from_daw_short(0xF2, 0, 4), [("short", 0xF2, 0, 4)])
        self.assertEqual(self.b.from_daw_short(0x90, 48, 100), [])   # would transpose the sequencer
        self.assertEqual(self.b.from_daw_short(0xB0, 1, 3), [])
        self.assertEqual(self.b.from_daw_short(0xFE), [])

    def test_notes_to_swing_can_be_allowed(self):
        b = bridge.Bridge(notes_to_swing=True)
        self.assertEqual(b.from_daw_short(0x90, 48, 100), [("short", 0x90, 48, 100)])

    # --- Arp + Rec/Stop/Play (sync_test.log)
    def test_arp_rec_does_not_start_recording_in_the_daw(self):
        # 24.610 Arp press, 24.930 Arp+Rec (INT), 26.830 Arp release, 26.850 CC 50 + MMC + Rec release
        out = self.to_daw(button(0x19), button(0x1D), button(0x1A),
                          (0xBF, 50, 127), MMC_REC_EXIT, button(0x12))
        self.assertEqual(out, [])

    def test_release_event_may_arrive_before_the_cc(self):
        out = self.to_daw(button(0x19), button(0x1D), button(0x1A), button(0x12), (0xBF, 50, 127), MMC_REC_STROBE)
        self.assertEqual(out, [])
        self.clock.now += bridge.RELEASE_GRACE + 0.01
        self.assertEqual(self.to_daw((0xBF, 50, 127)), [("short", 0xBF, 50, 127)])   # a real Rec again

    def test_arp_play_release_is_swallowed(self):
        # 32.289 Arp, 32.789 Arp+Play (USB), 34.929 Arp release, 34.949 CC 54 = 0 + Play release
        self.assertEqual(self.to_daw(button(0x19), button(0x1F), button(0x1A), (0xBF, 54, 0), button(0x10)), [])

    def test_only_the_combo_button_is_swallowed(self):
        out = self.to_daw(button(0x19), button(0x1D), (0x90, 60, 90), (0xBF, 54, 127), (0xBF, 123, 0))
        self.assertEqual(out, [("short", 0x90, 60, 90), ("short", 0xBF, 54, 127), ("short", 0xBF, 123, 0)])

    def test_swallowing_gives_up_after_a_timeout(self):
        self.to_daw(button(0x19), button(0x1D))
        self.clock.now += bridge.SWALLOW_TIMEOUT + 1
        self.assertEqual(self.to_daw((0xBF, 50, 127)), [("short", 0xBF, 50, 127)])

    def test_follows_the_transport_settings(self):
        b = bridge.Bridge(SwingSettings().set("rec_cc", 20), clock=self.clock)   # channel 1, CC 20
        out = b.from_swing_sysex(button(0x1D)) + b.from_swing_short(0xB0, 20, 127) + b.from_swing_short(0xB0, 50, 127)
        self.assertEqual(out, [("short", 0xB0, 50, 127)])

    # --- stuck notes
    def test_panic_releases_what_is_held(self):
        self.to_daw((0x90, 48, 100), (0x90, 55, 90), (0x80, 48, 0), (0xB0, 64, 127))
        out = self.b.panic()
        self.assertEqual(out[0], ("short", 0x80, 55, 0))
        self.assertIn(("short", 0xB0, 64, 0), out)
        self.assertIn(("short", 0xBF, 123, 0), out)
        self.assertEqual(len(out), 1 + 16 * 2)
        self.assertEqual(self.b.held, set())

    def test_note_on_velocity_zero_and_all_notes_off_clear_held_notes(self):
        self.to_daw((0x90, 48, 100), (0x90, 48, 0), (0x91, 50, 70), (0x90, 52, 80), (0xB0, 123, 0))
        self.assertEqual(self.b.held, {(1, 50)})

    def test_hold_releases_with_own_note_off(self):
        # key_test_3.log: Hold kept C2 from 29.188 and sent its note off at 34.081
        self.to_daw((0x90, 48, 119), button(0x09), button(0x0A), (0x80, 48, 0))
        self.assertEqual(self.b.held, set())


if __name__ == "__main__":
    unittest.main()
