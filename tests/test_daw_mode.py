"""Tests for daw_mode.py. Run with: python -m unittest discover -s tests"""
import json
import os
import tempfile
import unittest

import fakes  # noqa: F401  (adds the project to sys.path)
from swing_editor import daw_mode, protocol
from swing_editor.protocol import ProtocolError, SwingSettings


class DawModeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "sub", "backup.json")

    def test_only_confirmed_settings(self):
        for key in daw_mode.DAW_SETTINGS:
            self.assertTrue(protocol.param(key).confirmed, key)

    def test_turn_on_and_off_round_trip(self):
        start = SwingSettings().set("hold_mode", 1).set("midi_thru", 1).set("led_brightness", 30)
        on = daw_mode.turn_on(start, self.path)
        self.assertTrue(daw_mode.is_active(on))
        self.assertFalse(daw_mode.is_active(start))
        self.assertEqual(on["led_brightness"], 30)          # untouched
        self.assertTrue(daw_mode.has_backup(self.path))
        off = daw_mode.turn_off(on.set("led_brightness", 31), self.path)
        self.assertEqual(off, start.set("led_brightness", 31))
        self.assertFalse(daw_mode.has_backup(self.path))

    def test_second_turn_on_keeps_the_first_backup(self):
        start = SwingSettings()
        on = daw_mode.turn_on(start, self.path)
        daw_mode.turn_on(on, self.path)                      # must not overwrite with DAW values
        self.assertEqual(daw_mode.turn_off(on, self.path), start)

    def test_corrupt_backup_is_an_error_and_changes_nothing(self):
        on = daw_mode.turn_on(SwingSettings(), self.path)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"mod_cc": 500}, f)
        with self.assertRaises(ProtocolError):
            daw_mode.turn_off(on, self.path)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{oops")
        with self.assertRaises(ProtocolError):
            daw_mode.turn_off(on, self.path)


if __name__ == "__main__":
    unittest.main()
