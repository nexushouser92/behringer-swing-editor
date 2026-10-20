"""Tests for device.py with a fake Swing. Run with: python -m unittest discover -s tests"""
import unittest

from fakes import STATUS, VERSIONS, FakeSwing
from swing_editor import device, protocol
from swing_editor.protocol import SwingSettings

FAST = dict(timeout=0.01)


class ReadTests(unittest.TestCase):
    def test_product_info(self):
        swing = FakeSwing()
        self.assertEqual(device.read_product_info(swing), VERSIONS)
        self.assertEqual(swing.sent, [protocol.build_product_info_request()])

    def test_read_all(self):
        values = {**protocol.READ_DEFAULTS, 0x57: 10, 0x2B: 48}
        swing = FakeSwing(values)
        progress = []
        settings = device.read_all(swing, progress=lambda d, t: progress.append((d, t)))
        self.assertEqual(settings, SwingSettings(values))
        self.assertEqual(swing.sent, [protocol.build_read(p.id) for p in protocol.PARAMS])
        self.assertEqual(progress[-1], (47, 47))

    def test_status_messages_are_skipped(self):
        swing = FakeSwing(status_every_read=True)
        self.assertEqual(device.read_all(swing), SwingSettings())

    def test_retries_a_lost_reply(self):
        swing = FakeSwing(silent_reads=1)
        self.assertEqual(device.read_param(swing, "led_brightness", **FAST), 127)
        self.assertEqual(swing.sent, [protocol.build_read(0x57)] * 2)

    def test_no_answer(self):
        swing = FakeSwing(respond=False)
        with self.assertRaises(device.DeviceError):
            device.read_product_info(swing, **FAST)
        with self.assertRaises(device.DeviceError):
            device.read_all(swing, **FAST)
        self.assertEqual(len(swing.sent), 1 + device.RETRIES + 1 + device.RETRIES)

    def test_unknown_value_is_refused(self):
        swing = FakeSwing({**protocol.READ_DEFAULTS, 0x4F: 3})
        with self.assertRaises(device.DeviceError):
            device.read_all(swing)


class WriteTests(unittest.TestCase):
    def test_write_ack_and_verify(self):
        swing = FakeSwing()
        self.assertEqual(device.write_param(swing, "led_brightness", 64), 64)
        self.assertEqual(swing.values[0x57], 64)
        self.assertEqual(swing.sent, [protocol.build_write(0x57, 64), protocol.build_read(0x57)])

    def test_mismatch(self):
        swing = FakeSwing(apply_writes=False)
        with self.assertRaises(device.VerifyError) as ctx:
            device.write_param(swing, 0x57, 64)
        self.assertEqual((ctx.exception.sent, ctx.exception.received), (64, 127))

    def test_missing_ack(self):
        with self.assertRaises(device.DeviceError):
            device.write_param(FakeSwing(no_ack=True), 0x57, 64, **FAST)

    def test_invalid_value_is_never_sent(self):
        swing = FakeSwing()
        with self.assertRaises(protocol.ProtocolError):
            device.write_param(swing, "mod_cv_max", 13)
        self.assertEqual(swing.sent, [])

    def test_write_only_what_changed(self):
        swing = FakeSwing()
        current = SwingSettings()
        wanted = current.set("led_brightness", 30).set("output_channel", 4)
        written = device.write_settings(swing, wanted, current)
        self.assertEqual(written, [0x16, 0x57])
        self.assertEqual(SwingSettings(swing.values), wanted)
        self.assertEqual(len(swing.writes), 2)

    def test_write_everything(self):
        swing = FakeSwing()
        self.assertEqual(len(device.write_settings(swing, SwingSettings())), len(protocol.EDITABLE))
        self.assertEqual(len(swing.writes), len(protocol.EDITABLE))

    def test_unconfirmed_settings_are_read_but_never_written(self):
        swing = FakeSwing({**protocol.READ_DEFAULTS, 0x1A: 3, 0x28: 9})   # values this app does not know
        current = device.read_all(swing)
        self.assertEqual((current[0x1A], current[0x28]), (3, 9))
        with self.assertRaises(protocol.ProtocolError):
            device.write_param(swing, 0x28, 0)
        wanted = SwingSettings({**protocol.READ_DEFAULTS, 0x57: 1})
        device.write_settings(swing, wanted, current)
        self.assertEqual([m[6] for m in swing.writes], [0x57])
        self.assertEqual(swing.values[0x28], 9)

    def test_only_allowed_messages_reach_the_swing(self):
        swing = FakeSwing()
        device.read_product_info(swing)
        settings = device.read_all(swing)
        device.write_settings(swing, settings.set("led_brightness", 1), settings)
        for message in swing.sent:
            protocol.check_outgoing(message)
            self.assertNotIn(message[6], protocol.FORBIDDEN_COMMANDS)


if __name__ == "__main__":
    unittest.main()
