"""Tests for protocol.py. Run with: python -m unittest discover -s tests"""
import unittest

import fakes  # noqa: F401  (adds the project to sys.path)
from swing_editor import protocol
from swing_editor.protocol import Ack, ProductInfo, ProtocolError, Status, SwingSettings, Value


class TableTests(unittest.TestCase):
    def test_47_unique_parameters(self):
        self.assertEqual(len(protocol.PARAMS), 47)
        self.assertEqual(len(protocol.BY_ID), 47)
        self.assertEqual(len(protocol.BY_KEY), 47)

    def test_ids_are_the_ones_found_in_the_editor(self):
        expected = {0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x13, 0x14, 0x15, 0x16,
                    0x19, 0x1A, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B,
                    0x2C, 0x2D, 0x46, 0x47, 0x4A, 0x4C, 0x4D, 0x4E, 0x4F, 0x50, 0x57, 0x60, 0x61, 0x62,
                    0x63, 0x64, 0x65, 0x66, 0x67}
        self.assertEqual(set(protocol.BY_ID), expected)

    def test_no_parameter_uses_a_forbidden_command(self):
        self.assertFalse(set(protocol.BY_ID) & protocol.FORBIDDEN_COMMANDS)
        self.assertFalse(set(protocol.BY_ID) & {protocol.CMD_PRODUCT_INFO, protocol.CMD_STATUS})

    def test_every_value_is_a_midi_data_byte(self):
        for p in protocol.PARAMS:
            self.assertTrue(p.values, p.key)
            self.assertTrue(all(0 <= v <= 127 for v in p.allowed), p.key)
            self.assertEqual(len(set(p.allowed)), len(p.allowed), p.key)

    def test_every_parameter_has_a_known_section(self):
        for p in protocol.PARAMS:
            self.assertIn(p.section, protocol.SECTIONS, p.key)

    def test_defaults_read_from_a_real_swing_are_valid(self):
        SwingSettings()   # raises if a default is outside its parameter's values

    def test_labels(self):
        self.assertEqual(protocol.param("output_channel").label_of(0), "1")
        self.assertEqual(protocol.param("sustain_channel").label_of(65), "User")
        self.assertEqual(protocol.param("transpose_channel").label_of(126), "None")
        self.assertEqual(protocol.param("transpose_center").label_of(60), "C3")
        self.assertEqual(protocol.param("mod_cv_max").label_of(12), "12 V")
        self.assertEqual(protocol.param("led_brightness").label_of(200), "? (200)")

    def test_note_names(self):
        self.assertEqual(protocol.note_name(0), "C-2")
        self.assertEqual(protocol.note_name(61), "C#3")
        self.assertEqual(protocol.note_name(127), "G8")

    def test_lookup(self):
        self.assertIs(protocol.param(0x57), protocol.param("led_brightness"))
        for bad in (0x77, 0x00, "nope"):
            with self.assertRaises(ProtocolError):
                protocol.param(bad)


class SettingsTests(unittest.TestCase):
    def test_set_returns_a_validated_copy(self):
        a = SwingSettings()
        b = a.set("led_brightness", 64)
        self.assertEqual((a["led_brightness"], b[0x57]), (127, 64))
        self.assertEqual(b.differences(a), [0x57])
        with self.assertRaises(ProtocolError):
            a.set("output_channel", 16)
        with self.assertRaises(ProtocolError):
            a.set("velocity_curve", True)

    def test_must_be_complete_and_known(self):
        values = dict(protocol.READ_DEFAULTS)
        del values[0x57]
        with self.assertRaises(ProtocolError):
            SwingSettings(values)
        values[0x57] = 1
        values[0x77] = 0
        with self.assertRaises(ProtocolError):
            SwingSettings(values)

    def test_items_follow_the_table(self):
        self.assertEqual([p for p, _ in SwingSettings().items()], list(protocol.PARAMS))


class UnconfirmedTests(unittest.TestCase):
    def test_which_are_unconfirmed(self):
        self.assertEqual({p.id for p in protocol.PARAMS if not p.confirmed}, {0x1A, 0x28, 0x2D})
        self.assertEqual(len(protocol.EDITABLE), 44)

    def test_any_data_byte_is_kept_but_never_written(self):
        settings = SwingSettings({**protocol.READ_DEFAULTS, 0x2D: 100})
        self.assertEqual(settings[0x2D], 100)
        with self.assertRaises(ProtocolError):
            protocol.build_write(0x2D, 0)
        protocol.build_read(0x2D)   # reading is fine
        self.assertEqual(settings.differences(SwingSettings()), [])


class OutgoingTests(unittest.TestCase):
    def test_exact_bytes(self):
        self.assertEqual(protocol.build_product_info_request().hex(" "), "f0 00 20 32 7f 42 00 f7")
        self.assertEqual(protocol.build_read("led_brightness").hex(" "), "f0 00 20 32 7f 42 57 f7")
        self.assertEqual(protocol.build_write(0x57, 64).hex(" "), "f0 00 20 32 7f 42 57 40 f7")

    def test_write_validates(self):
        for key, value in (("mod_cv_max", 4), ("led_brightness", 128), ("velocity_curve", 4)):
            with self.assertRaises(ProtocolError):
                protocol.build_write(key, value)

    def test_guard_accepts_only_the_three_kinds(self):
        for good in (protocol.build_product_info_request(), protocol.build_read(0x07),
                     protocol.build_write(0x2B, 0)):
            protocol.check_outgoing(good)
        bad = [
            protocol.HEADER + bytes([0x77, 0xF7]),          # bootloader mode
            protocol.HEADER + bytes([0x74, 0xF7]),          # bootloader status
            protocol.HEADER + bytes([0x73, 0x00, 0xF7]),    # clear sequence 1
            protocol.HEADER + bytes([0x57, 0x80, 0xF7]),    # value not a data byte
            protocol.HEADER + bytes([0x4F, 0x04, 0xF7]),    # value outside the range
            protocol.HEADER + bytes([0x01, 0xF7]),          # unknown parameter
            protocol.HEADER + bytes([0x00, 0x00, 0xF7]),    # product info does not take a value
            bytes.fromhex("f0 00 20 32 00 42 57 f7"),       # other device id
            bytes.fromhex("f0 7e 7f 06 01 f7"),              # not a Swing message
            protocol.HEADER + bytes([0x6F, 0x00, 0x10, 0x00, 0x00, 0xF7]),  # sequencer write
            protocol.HEADER + bytes([0x28, 0x00, 0xF7]),    # write of an unconfirmed setting
        ]
        for message in bad:
            with self.assertRaises(ProtocolError, msg=message.hex(" ")):
                protocol.check_outgoing(message)


class IncomingTests(unittest.TestCase):
    def test_product_info(self):
        reply = protocol.parse(bytes.fromhex("f0 00 20 32 7f 42 00 01 00 00 01 01 34 f7"))
        self.assertEqual(reply, ProductInfo(((1, 0, 0), (1, 1, 52))))

    def test_value_and_ack(self):
        self.assertEqual(protocol.parse(bytes.fromhex("f0 00 20 32 7f 42 0a 41 f7")), Value(0x0A, 65))
        self.assertEqual(protocol.parse(bytes.fromhex("f0 00 20 32 7f 42 57 f7")), Ack(0x57))

    def test_any_device_id_is_accepted(self):
        self.assertEqual(protocol.parse(bytes.fromhex("f0 00 20 32 00 42 57 40 f7")), Value(0x57, 64))

    def test_status_from_a_real_swing(self):
        self.assertEqual(protocol.parse(bytes.fromhex("f0 00 20 32 7f 42 70 00 01 05 f7")),
                         Status(bytes([1, 5])))

    def test_unpack_7bit(self):
        self.assertEqual(protocol.unpack_7bit(bytes([0b0000101, 1, 2, 3])), bytes([0x81, 2, 0x83]))
        packed = bytes([0x7F]) + bytes(range(7)) + bytes([0x01, 0x10])
        self.assertEqual(protocol.unpack_7bit(packed),
                         bytes([0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x90]))

    def test_other_messages_are_ignored(self):
        for hexstr in ("f0 7e 7f 06 02 f7", "f0 00 20 32 7f 43 57 40 f7", "f0 00 20 32 7f 42 6f 00 10 00 00 f7",
                       "f0 00 20 32 7f 42 57 01 02 f7", "90 3c 40"):
            self.assertIsNone(protocol.parse(bytes.fromhex(hexstr)), hexstr)


if __name__ == "__main__":
    unittest.main()
