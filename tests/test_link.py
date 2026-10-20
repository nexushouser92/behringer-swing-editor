"""Tests for link.py with a fake Swing; the link is stepped by hand. Run with: python -m unittest discover -s tests"""
import unittest

from fakes import VERSIONS, FakeSwing
from swing_editor import link, midi_win, protocol
from swing_editor.protocol import SwingSettings


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.swing = FakeSwing()
        self.present = True
        self.opened = 0
        self.link = link.SwingLink(opener=self.opener, lister=self.lister, clock=self.clock)

    def opener(self):
        self.opened += 1
        return self.swing

    def lister(self):
        names = ["Behringer Swing"] if self.present else []
        return ["UMC404HD"] + names, names

    def events(self):
        out = []
        while not self.link.events.empty():
            out.append(self.link.events.get_nowait())
        return out

    def kinds(self):
        return [k for k, _ in self.events()]

    def later(self, seconds=link.WRITE_DELAY):
        self.clock.now += seconds
        self.link.step()

    def test_links_and_reads_automatically(self):
        self.link.step()
        events = self.events()
        self.assertEqual([k for k, _ in events], ["linked", "info", "settings"])
        self.assertEqual(events[1][1], VERSIONS)
        self.assertEqual(events[2][1], SwingSettings())
        self.assertEqual(self.swing.writes, [])

    def test_waits_for_the_swing(self):
        self.present = False
        self.link.step()
        self.assertEqual((self.kinds(), self.opened), ([], 0))
        self.present = True
        self.link.step()   # polls only once per interval
        self.assertEqual(self.opened, 0)
        self.later(link.POLL_INTERVAL)
        self.assertEqual(self.kinds()[0], "linked")

    def test_open_failure_keeps_searching(self):
        def busy():
            raise midi_win.MidiError("in use by Control Tribe")
        self.link.opener = busy
        self.link.step()
        kind, error = self.events()[0]
        self.assertEqual(kind, "searching")
        self.assertIn("Control Tribe", str(error))
        self.assertFalse(self.link.linked)

    def test_changes_are_written_after_a_pause_and_only_what_changed(self):
        self.link.step()
        self.events()
        self.link.push(SwingSettings().set("led_brightness", 20).set("output_channel", 2))
        self.link.step()
        self.assertEqual(self.swing.writes, [])
        self.later()
        self.assertEqual([m[6] for m in self.swing.writes], [0x16, 0x57])
        self.assertEqual(self.kinds(), ["writing", "written"])
        self.assertFalse(self.link.has_pending)
        self.assertEqual(self.link.on_swing[0x57], 20)

    def test_quick_changes_make_one_write_each(self):
        self.link.step()
        settings = SwingSettings()
        for value in (10, 20, 30):
            settings = settings.set("led_brightness", value)
            self.link.push(settings)
            self.later(link.WRITE_DELAY / 2)
        self.later()
        self.assertEqual([m[7] for m in self.swing.writes], [30])

    def test_no_change_writes_nothing(self):
        self.link.step()
        self.events()
        self.link.push(SwingSettings())
        self.later()
        self.assertEqual((self.swing.writes, self.kinds()), ([], []))
        self.assertFalse(self.link.has_pending)

    def test_changes_made_while_away_are_applied_on_link(self):
        """The window's settings win, as in Orbit Editor; unconfirmed values stay as the Swing has them."""
        self.present = False
        self.link.push(SwingSettings().set("tie_mode", 0))
        self.link.step()
        self.present = True
        self.swing.values[0x57] = 5
        self.swing.values[0x28] = 1
        self.later(link.POLL_INTERVAL)
        self.later()
        self.assertEqual([m[6] for m in self.swing.writes], [0x2C, 0x57])
        self.assertEqual((self.swing.values[0x2C], self.swing.values[0x57], self.swing.values[0x28]), (0, 127, 1))

    def test_unplug_and_replug(self):
        self.link.step()
        self.events()
        self.present = False
        self.later(link.POLL_INTERVAL)
        self.assertEqual(self.kinds(), ["searching"])
        self.assertTrue(self.swing.closed)
        self.present = True
        self.later(link.POLL_INTERVAL)
        self.assertEqual(self.kinds(), ["linked", "info", "settings"])

    def test_write_error_keeps_the_change_for_later(self):
        self.link.step()
        self.swing.respond = False
        self.link.push(SwingSettings().set("led_brightness", 1))
        self.later()
        kinds = self.kinds()
        self.assertIn("write_failed", kinds)
        self.assertEqual(kinds[-1], "searching")
        self.assertTrue(self.link.has_pending)
        self.swing.respond = True
        self.later(link.POLL_INTERVAL)
        self.later()
        self.assertEqual(self.swing.values[0x57], 1)

    def test_verify_mismatch_is_reported_and_read_again(self):
        self.link.step()
        self.events()
        self.swing.apply_writes = False
        self.link.push(SwingSettings().set("led_brightness", 1))
        self.later()
        self.assertEqual(self.kinds(), ["writing", "write_failed"])
        self.assertFalse(self.link.has_pending)
        self.link.step()
        self.assertEqual(self.kinds(), ["settings"])

    def test_read_request_and_stop_flushes(self):
        self.link.step()
        self.events()
        self.link.request_read()
        self.link.step()
        self.assertEqual(self.kinds(), ["settings"])
        self.link.push(SwingSettings().set("led_brightness", 77))
        self.link.stop()
        self.assertEqual(self.swing.values[0x57], 77)
        self.assertTrue(self.swing.closed)

    def test_only_allowed_messages_are_sent(self):
        self.link.step()
        self.link.push(SwingSettings().set("led_brightness", 3).set("gate_output", 2))
        self.later()
        for message in self.swing.sent:
            protocol.check_outgoing(message)


if __name__ == "__main__":
    unittest.main()
