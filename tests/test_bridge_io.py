"""Tests for bridge_io.py and the bridge inside link.py, with fake virtual ports and a fake Swing.

Run with: python -m unittest discover -s tests
"""
import time
import unittest

from fakes import FakeSwing
from swing_editor import bridge_io, link, midi_win
from swing_editor.protocol import SwingSettings
from test_bridge import MMC_PLAY, button
from test_link import Clock


class FakeVirtualPort:
    def __init__(self, name):
        self.name = name
        self.short, self.sysex = [], []
        self.on_short = None
        self.closed = False

    def send_short(self, status, d1=0, d2=0):
        self.short.append((status, d1, d2))

    def send(self, data):
        self.sysex.append(bytes(data))

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, available=("Swing to DAW", "DAW to Swing")):
        self.available = available
        self.ports = {}

    def __call__(self, in_name=None, out_name=None):
        name = in_name or out_name
        if name not in self.available:
            raise midi_win.MidiError(f"MIDI port '{name}' not found")
        port = FakeVirtualPort(name)
        self.ports[name] = port
        return port


def wait_until(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.005)
    return False


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.opener = FakeOpener()
        self.runner = bridge_io.BridgeRunner(opener=self.opener)
        self.runner.open()
        self.addCleanup(self.runner.close)
        self.to_daw = self.opener.ports["Swing to DAW"]
        self.from_daw = self.opener.ports["DAW to Swing"]
        self.swing = FakeVirtualPort("swing")
        self.runner.attach(self.swing)

    def test_forwards_both_ways_through_the_thread(self):
        self.runner.from_swing_short(0x90, 60, 100)
        self.from_daw.on_short(0xF8, 0, 0)          # the DAW's clock, from a winmm callback
        self.from_daw.on_short(0x90, 40, 100)       # a DAW note: not passed to the Swing
        self.assertTrue(wait_until(lambda: self.to_daw.short and self.swing.short))
        time.sleep(0.05)
        self.assertEqual(self.to_daw.short, [(0x90, 60, 100)])
        self.assertEqual(self.swing.short, [(0xF8, 0, 0)])
        self.assertEqual(self.runner.counts["filtered"], 1)

    def test_mmc_passes_and_status_does_not(self):
        self.runner.from_swing_sysex(MMC_PLAY)
        self.runner.from_swing_sysex(button(0x0F))
        self.assertTrue(wait_until(lambda: self.to_daw.sysex))
        time.sleep(0.05)
        self.assertEqual(self.to_daw.sysex, [MMC_PLAY])

    def test_detach_sends_panic_to_the_daw(self):
        self.runner.from_swing_short(0x90, 48, 100)
        self.runner.detach()
        self.assertTrue(wait_until(lambda: (0x80, 48, 0) in self.to_daw.short))
        self.assertTrue(wait_until(lambda: (0xBF, 123, 0) in self.to_daw.short))
        self.assertIsNone(self.runner.swing)

    def test_close_closes_the_virtual_ports(self):
        self.runner.close()
        self.assertTrue(self.to_daw.closed and self.from_daw.closed)
        self.assertIsNone(self.from_daw.on_short)

    def test_send_errors_are_kept_not_raised(self):
        def broken(*args):
            raise midi_win.MidiError("loopMIDI closed")
        self.to_daw.send_short = broken
        self.runner.process(("swing", 0x90, 60, 100))
        self.assertIn("loopMIDI", str(self.runner.last_error))


class MissingPortTests(unittest.TestCase):
    def test_missing_loopmidi_port(self):
        opener = FakeOpener(available=("Swing to DAW",))
        runner = bridge_io.BridgeRunner(opener=opener)
        with self.assertRaises(midi_win.MidiError):
            runner.open()
        self.assertTrue(opener.ports["Swing to DAW"].closed)   # nothing left open


class LinkWithBridgeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.swing = FakeSwing()
        self.link = link.SwingLink(opener=lambda: self.swing,
                                   lister=lambda: (["Behringer Swing"], ["Behringer Swing"]), clock=self.clock)
        self.opener = FakeOpener()
        self.runner = bridge_io.BridgeRunner(opener=self.opener)
        self.runner.open()
        self.addCleanup(self.runner.close)
        self.to_daw = self.opener.ports["Swing to DAW"]

    def test_bridge_set_before_linking(self):
        self.link.set_bridge(self.runner)
        self.link.step()
        self.assertIs(self.runner.swing, self.link.port)
        self.swing.on_short(0x90, 62, 80)            # the Swing plays a note
        self.assertTrue(wait_until(lambda: (0x90, 62, 80) in self.to_daw.short))

    def test_bridge_set_after_linking_and_status_reaches_the_bridge(self):
        self.link.step()
        self.link.set_bridge(self.runner)
        # Arp + Rec while linked: the status arrives in the port's queue, the leaked Rec CC after it
        self.swing.inbox += [button(0x19), button(0x1D), button(0x1A)]
        self.link.step()
        self.swing.on_short(0xB0, 50, 127)
        self.swing.on_short(0x90, 60, 90)
        self.assertTrue(wait_until(lambda: (0x90, 60, 90) in self.to_daw.short))
        self.assertNotIn((0xB0, 50, 127), self.to_daw.short)

    def test_settings_writes_still_work_with_the_bridge(self):
        self.link.set_bridge(self.runner)
        self.link.step()
        self.link.push(SwingSettings().set("led_brightness", 9))
        self.clock.now += link.WRITE_DELAY
        self.link.step()
        self.assertEqual(self.swing.values[0x57], 9)

    def test_unplug_sends_panic(self):
        self.link.set_bridge(self.runner)
        self.link.step()
        self.swing.on_short(0x90, 50, 99)
        self.assertTrue(wait_until(lambda: (0x90, 50, 99) in self.to_daw.short))
        self.link.lister = lambda: ([], [])
        self.clock.now += link.POLL_INTERVAL
        self.link.step()
        self.assertTrue(wait_until(lambda: (0x80, 50, 0) in self.to_daw.short))

    def test_turning_the_bridge_off(self):
        self.link.set_bridge(self.runner)
        self.link.step()
        self.link.set_bridge(None)
        self.assertIsNone(self.swing.on_short)
        self.assertIsNone(self.runner.swing)


if __name__ == "__main__":
    unittest.main()
