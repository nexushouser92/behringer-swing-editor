"""Tests for presets.py. Run with: python -m unittest discover -s tests"""
import json
import os
import tempfile
import unittest

import fakes  # noqa: F401  (adds the project to sys.path)
from swing_editor import presets, protocol
from swing_editor.protocol import ProtocolError, SwingSettings


def custom():
    return SwingSettings().set("led_brightness", 40).set("transpose_channel", 126).set("velocity_curve", 2)


class JsonTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(presets.from_dict(presets.to_dict(custom())), custom())

    def test_readable(self):
        data = presets.to_dict(custom())
        self.assertEqual(data["settings"]["transpose_channel"], {"value": 126, "label": "None"})
        self.assertEqual(data["settings"]["velocity_curve"]["label"], "Anti-logarithmic")
        self.assertEqual(len(data["settings"]), len(protocol.EDITABLE))
        self.assertNotIn("tempo_knob", data["settings"])

    def test_partial_preset_keeps_defaults(self):
        data = {"format": presets.FORMAT_NAME, "version": 1, "settings": {"led_brightness": 5}}
        self.assertEqual(presets.from_dict(data), SwingSettings().set("led_brightness", 5))

    def test_rejects_bad_presets(self):
        good = presets.to_dict(custom())
        bad = [
            {**good, "format": "orbit-editor-preset"},
            {**good, "version": 2},
            {**good, "settings": {"nope": 1}},
            {**good, "settings": {"mod_cv_max": {"value": 20}}},
            {"format": presets.FORMAT_NAME, "version": 1},
        ]
        for data in bad:
            with self.assertRaises(ProtocolError):
                presets.from_dict(data)


class UnconfirmedTests(unittest.TestCase):
    def test_unconfirmed_keys_in_a_preset_are_ignored(self):
        data = {"format": presets.FORMAT_NAME, "version": 1,
                "settings": {"tempo_knob": {"value": 1}, "led_brightness": {"value": 9}}}
        loaded = presets.from_dict(data)
        self.assertEqual(loaded[0x28], protocol.READ_DEFAULTS[0x28])
        self.assertEqual(loaded[0x57], 9)

    def test_applying_a_preset_keeps_the_swings_unconfirmed_values(self):
        on_swing = SwingSettings({**protocol.READ_DEFAULTS, 0x28: 9})
        merged = on_swing.with_editable_from(custom())
        self.assertEqual(merged[0x28], 9)
        self.assertEqual(merged[0x57], 40)


class SyxTests(unittest.TestCase):
    def test_round_trip(self):
        data = presets.to_syx(custom())
        self.assertEqual(len(data), len(protocol.EDITABLE) * 9)
        self.assertEqual(presets.from_syx(data), custom())

    def test_every_message_is_allowed(self):
        data = presets.to_syx(custom())
        for i in range(0, len(data), 9):
            protocol.check_outgoing(data[i:i + 9])

    def test_rejects_bad_files(self):
        full = presets.to_syx(custom())
        for data in (full[:-9], full + full[:9], full[:-1],
                     full + bytes.fromhex("f0 00 20 32 7f 42 77 f7")):
            with self.assertRaises(ProtocolError):
                presets.from_syx(data)


class FileTests(unittest.TestCase):
    def test_save_and_load_both_formats(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.json", "b.syx"):
                path = os.path.join(d, name)
                presets.save(path, custom())
                self.assertEqual(presets.load(path), custom())
            with open(os.path.join(d, "a.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["format"], presets.FORMAT_NAME)

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            with self.assertRaises(ProtocolError):
                presets.load(path)


if __name__ == "__main__":
    unittest.main()
