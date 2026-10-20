"""Tests for midi_win.py with a fake winmm (Windows only: it uses ctypes.WINFUNCTYPE).

Run with: python -m unittest discover -s tests
"""
import unittest
from unittest import mock

from fakes import FakeWinmm, swing_replies
from swing_editor import device, midi_win, protocol

READ = protocol.build_read("led_brightness")
# A long message to test splitting: 47 replies in one go, like a burst from the Swing.
DUMP = protocol.HEADER + bytes([0x57, 0x7F, 0xF7])


class PortListTests(unittest.TestCase):
    def test_list_and_find(self):
        fake = FakeWinmm(ins=["UMC404HD", "Behringer Swing"], outs=["GS Wavetable", "x", "Behringer Swing"])
        ins, outs = midi_win.list_ports(fake)
        self.assertEqual(ins, ["UMC404HD", "Behringer Swing"])
        self.assertEqual(midi_win.find_port(ins), 1)
        self.assertEqual(midi_win.find_port(outs), 2)
        self.assertIsNone(midi_win.find_port(["Maschine MK2 In", None]))
        self.assertEqual(midi_win.find_port(["behringer swing"]), 0)

    def test_open_swing_uses_matching_ports(self):
        fake = FakeWinmm(ins=["A", "Behringer Swing"], outs=["Behringer Swing"])
        with midi_win.open_swing(fake):
            self.assertEqual((fake.opened_in, fake.opened_out), (1, 0))

    def test_open_swing_not_found(self):
        for ins, outs in ((["A"], ["Behringer Swing"]), (["Behringer Swing"], ["B"])):
            with self.assertRaises(midi_win.MidiError):
                midi_win.open_swing(FakeWinmm(ins=ins, outs=outs))


class OpenCloseTests(unittest.TestCase):
    def test_open_prepares_buffers_and_close_releases_everything(self):
        fake = FakeWinmm()
        port = midi_win.open_swing(fake)
        self.assertEqual(len(fake.prepared_in), midi_win.NUM_BUFFERS)
        self.assertEqual(len(fake.available), midi_win.NUM_BUFFERS)
        port.close()
        port.close()  # closing twice is harmless
        self.assertEqual(fake.in_unprepared, midi_win.NUM_BUFFERS)
        self.assertEqual((fake.in_closed, fake.out_closed), (1, 1))

    def test_input_open_failure(self):
        fake = FakeWinmm(in_open=4)
        with self.assertRaises(midi_win.MidiError):
            midi_win.open_swing(fake)
        self.assertEqual((fake.in_closed, fake.out_closed), (0, 0))

    def test_output_open_failure_closes_input(self):
        fake = FakeWinmm(out_open=4)
        with self.assertRaises(midi_win.MidiError):
            midi_win.open_swing(fake)
        self.assertEqual((fake.in_closed, fake.out_closed), (1, 0))

    def test_buffers_returned_by_reset_are_not_reused(self):
        fake = FakeWinmm()
        port = midi_win.open_swing(fake)
        added = fake.added
        port.close()
        self.assertEqual(fake.added, added)


class SendTests(unittest.TestCase):
    def test_send_sysex(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            port.send(READ)
        self.assertEqual(fake.sent, [READ])
        self.assertEqual(fake.out_prepared, fake.out_unprepared)

    def test_only_complete_sysex(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            for bad in (b"", b"\x90\x24\x7f", b"\xf0\x00\x01"):
                with self.assertRaises(midi_win.MidiError):
                    port.send(bad)
        self.assertEqual(fake.sent, [])

    def test_waits_while_still_playing(self):
        fake = FakeWinmm(still_playing=3)
        with midi_win.open_swing(fake) as port:
            port.send(READ)
        self.assertEqual(fake.out_unprepared, 1)
        self.assertEqual(fake.out_resets, 0)

    def test_driver_that_never_finishes(self):
        fake = FakeWinmm(still_playing=10 ** 9)
        with mock.patch.object(midi_win, "SEND_TIMEOUT", 0.02), midi_win.open_swing(fake) as port:
            with self.assertRaises(midi_win.MidiError):
                port.send(READ)
        self.assertEqual(fake.out_resets, 1)
        self.assertEqual(fake.out_unprepared, 1)

    def test_quiet_time_after_receiving(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            now, pauses = [100.0], []
            port._clock, port._sleep = lambda: now[0], pauses.append
            port.send(READ)  # nothing received yet: no pause
            fake.deliver(DUMP)
            self.assertEqual(port.receive(1), DUMP)
            now[0] = 100.05
            port.send(READ)
            now[0] = 101.0
            port.send(READ)  # long after the dump: no pause
        self.assertEqual(len(pauses), 1)
        self.assertAlmostEqual(pauses[0], midi_win.QUIET_AFTER_RECEIVE - 0.05)
        self.assertEqual(len(fake.sent), 3)

    def test_long_msg_error(self):
        fake = FakeWinmm(long_msg=11)
        with midi_win.open_swing(fake) as port:
            with self.assertRaises(midi_win.MidiError):
                port.send(READ)
        self.assertEqual(fake.out_unprepared, 1)


class ShortMessageTests(unittest.TestCase):
    def test_send_short_packs_bytes(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            port.send_short(0xFA)
            port.send_short(0xF8)
            port.send_short(0xB0, 64, 127)
        self.assertEqual(fake.short_sent, [0xFA, 0xF8, 0xB0 | (64 << 8) | (127 << 16)])

    def test_send_short_rejects_bad_bytes_and_reports_errors(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            for bad in ((0x40,), (0xB0, 128), (0x90, 1, 200)):
                with self.assertRaises(midi_win.MidiError):
                    port.send_short(*bad)
            fake.short_res = 11
            with self.assertRaises(midi_win.MidiError):
                port.send_short(0xF8)
        self.assertEqual(fake.short_sent, [0xF8])


class OneSidedPortTests(unittest.TestCase):
    def test_open_output_only(self):
        fake = FakeWinmm(ins=["Swing to DAW"], outs=["GS", "Swing to DAW"])
        with midi_win.open_by_name(out_name="swing to daw", winmm=fake) as port:
            port.send_short(0x90, 60, 100)
        self.assertEqual((fake.opened_in, fake.opened_out), (None, 1))
        self.assertEqual(fake.short_sent, [0x90 | (60 << 8) | (100 << 16)])
        self.assertEqual((fake.in_closed, fake.out_closed), (0, 1))

    def test_open_input_only(self):
        fake = FakeWinmm(ins=["UMC", "DAW to Swing"], outs=["DAW to Swing"])
        with midi_win.open_by_name(in_name="DAW to Swing", winmm=fake) as port:
            got = []
            port.on_short = lambda *m: got.append(m)
            fake.callback(0x100, midi_win.MIM_DATA, 0, 0xF8, 0)
            with self.assertRaises(midi_win.MidiError):
                port.send_short(0xF8)
        self.assertEqual(got, [(0xF8, 0, 0)])
        self.assertEqual((fake.opened_in, fake.opened_out), (1, None))
        self.assertEqual((fake.in_closed, fake.out_closed), (1, 0))

    def test_missing_virtual_port(self):
        with self.assertRaises(midi_win.MidiError):
            midi_win.open_by_name(out_name="Swing to DAW", winmm=FakeWinmm())


class ReceiveTests(unittest.TestCase):
    def test_whole_message(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            fake.deliver(DUMP)
            self.assertEqual(port.receive(1), DUMP)
            self.assertEqual(len(fake.available), midi_win.NUM_BUFFERS)  # buffer given back

    def test_message_split_over_buffers(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            fake.deliver(DUMP, chunk=3)
            self.assertEqual(port.receive(1), DUMP)

    def test_two_messages_and_junk(self):
        fake = FakeWinmm()
        other = bytes([0xF0, 0x7E, 0x00, 0x06, 0x02, 0xF7])
        with midi_win.open_swing(fake) as port:
            fake.deliver(b"\x12\x34" + other + DUMP)
            self.assertEqual(port.receive(1), other)
            self.assertEqual(port.receive(1), DUMP)
            self.assertIsNone(port.receive(0.01))

    def test_timeout(self):
        with midi_win.open_swing(FakeWinmm()) as port:
            self.assertIsNone(port.receive(0.02))

    def test_drain(self):
        fake = FakeWinmm()
        with midi_win.open_swing(fake) as port:
            fake.deliver(DUMP[:4])
            fake.deliver(DUMP)
            port.drain()
            self.assertEqual(len(fake.available), midi_win.NUM_BUFFERS)
            self.assertIsNone(port.receive(0.01))
            fake.deliver(DUMP[5:])  # tail of an old message without its start: ignored
            self.assertIsNone(port.receive(0.01))


class WithDeviceTests(unittest.TestCase):
    def test_read_through_winmm(self):
        fake = FakeWinmm(on_send=swing_replies)
        with midi_win.open_swing(fake) as port:
            self.assertEqual(device.read_product_info(port, timeout=1), ((1, 0, 0), (1, 1, 52)))
            self.assertEqual(device.read_all(port, timeout=1), protocol.SwingSettings())
        self.assertEqual(len(fake.sent), 48)


if __name__ == "__main__":
    unittest.main()
