"""Tests for i18n.py and gui.py with a fake Swing. No MIDI device is needed.

The window is created hidden; the link is stepped by hand instead of on a thread.
Run with: python -m unittest discover -s tests
"""
import os
import tempfile
import tkinter as tk
import unittest

import customtkinter as ctk

from fakes import FakeSwing
from swing_editor import daw_mode, gui, i18n, link, presets, protocol
from swing_editor.protocol import SwingSettings
from test_link import Clock


class TranslationTests(unittest.TestCase):
    def test_same_keys_in_both_languages(self):
        self.assertEqual(set(i18n.TEXTS["es"]), set(i18n.TEXTS["en"]))

    def test_every_setting_and_section_has_texts(self):
        for p in protocol.PARAMS:
            self.assertIn(p.key, i18n.PARAM_TEXTS)
        for section in protocol.SECTIONS:
            self.assertIn(section, i18n.TEXTS["es"])
        for p in protocol.EDITABLE:
            self.assertTrue(i18n.PARAM_TEXTS[p.key][0] and i18n.PARAM_TEXTS[p.key][2], p.key)

    def test_spanish_options(self):
        t = i18n.Translator("es")
        self.assertEqual(t.option("All"), "Todos")
        self.assertEqual(t.option("24 ppq"), "24 ppq")
        self.assertEqual(i18n.Translator("en").option("All"), "All")

    def test_every_word_option_is_translated(self):
        for p in protocol.EDITABLE:
            for _, label in p.values:
                if label[:1].isalpha() and not label.endswith(" V") and label not in ("Gate", "Toggle", "MMC",
                                                                                      "MIDI CC", "Aftertouch"):
                    if p.values is not protocol.NOTES:
                        self.assertIn(label, i18n.OPTION_ES, f"{p.key}: {label}")


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = ctk.CTk()
        except tk.TclError as e:
            self.skipTest(f"no display: {e}")
        self.root.withdraw()
        self.addCleanup(self.close_root)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.clock = Clock()
        self.swing = FakeSwing()
        self.present = True
        self.link = link.SwingLink(opener=lambda: self.swing, lister=self.lister, clock=self.clock)
        self.answers = []
        self.answer = True

    def lister(self):
        names = ["Behringer Swing"] if self.present else []
        return names, names

    def close_root(self):
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.after_cancel(job)
        self.root.destroy()

    def make_app(self, lang="es", connect=True, **kw):
        def ask(title, text):
            self.answers.append(text)
            return self.answer
        defaults = dict(lang=lang, link=self.link, autostart=False, ask_yes_no=ask, clock=self.clock,
                        backup_path=os.path.join(self.dir, "before_daw_mode.json"))
        defaults.update(kw)
        app = gui.App(self.root, **defaults)
        if connect:
            self.sync(app)
        return app

    def sync(self, app, wait=link.WRITE_DELAY):
        self.link.step()
        self.clock.now += wait
        self.link.step()
        app.process_link_events()

    def status(self, app):
        return app.status_button.cget("text")

    # --- linking
    def test_waits_for_the_swing(self):
        self.present = False
        app = self.make_app()
        self.assertIn("Buscando Swing", self.status(app))
        self.assertIsNone(app.settings)
        self.assertEqual(self.root.title(), "Swing Editor · Proyecto no oficial")
        self.assertEqual(app.action_buttons["save"].cget("state"), "disabled")

    def test_port_used_by_a_daw(self):
        from swing_editor import midi_win
        def busy():
            raise midi_win.MidiError("midiInOpen failed (7); is another program using the device?")
        self.link.opener = busy
        app = self.make_app()
        self.assertIn("en uso por otro programa", self.status(app))
        self.assertIn("Ableton", app.message.cget("text"))
        self.link.opener = lambda: self.swing   # the DAW was closed
        self.clock.now += link.POLL_INTERVAL
        self.sync(app)
        self.assertIn("Swing vinculado", self.status(app))

    def test_links_reads_and_shows_values(self):
        self.swing.values[0x16] = 4
        app = self.make_app()
        self.assertIn("Swing vinculado", self.status(app))
        self.assertEqual(app.firmware_label.cget("text"), "Firmware 1.1.52")
        self.assertEqual(app.controls["output_channel"].widget.get(), "5")
        self.assertEqual(app.controls["transpose_channel"].widget.get(), "Todos")
        self.assertEqual(app.controls["transpose_center"].note_label.cget("text"), "C3")
        self.assertEqual(self.swing.writes, [])

    def test_english(self):
        app = self.make_app(lang="en")
        self.assertIn("Swing linked", self.status(app))
        self.assertEqual(app.controls["transpose_channel"].widget.get(), "All")

    def test_unconfirmed_settings_are_not_shown(self):
        app = self.make_app()
        self.assertEqual(set(app.controls), {p.key for p in protocol.EDITABLE})
        for key in ("tempo_knob", "aftertouch_curve", "arpeggiator_random"):
            self.assertNotIn(key, app.controls)

    # --- live changes
    def test_changes_reach_the_swing(self):
        app = self.make_app()
        app.show_section("transpose")
        app.controls["transpose_channel"].widget._command("Ninguno")
        app.controls["transpose_latch"].widget._command("Apagado")
        app.controls["transpose_center"].spin.step(1)
        self.assertIn("aplicando", self.status(app))
        self.sync(app)
        self.assertEqual((self.swing.values[0x21], self.swing.values[0x26], self.swing.values[0x2B]), (126, 1, 61))
        self.assertIn("cambios aplicados", self.status(app))
        self.assertEqual(app.controls["transpose_center"].note_label.cget("text"), "C#3")

    def test_slider_and_typed_numbers(self):
        app = self.make_app()
        app.controls["led_brightness"].slider._command(64.4)
        spin = app.controls["sustain_cc"].spin
        spin.set_text("200")
        spin.commit()
        self.assertEqual(spin.get_text(), "64")   # out of range: put back
        spin.set_text("11")
        spin.commit()
        self.sync(app)
        self.assertEqual((self.swing.values[0x57], self.swing.values[0x0D]), (64, 11))

    def test_write_error_and_retry(self):
        app = self.make_app()
        self.swing.apply_writes = False
        app.set_value("mod_cc", 1)
        self.sync(app)
        self.assertIn("No se pudo aplicar", self.status(app))
        self.assertIn("El Swing no guardó", app.message.cget("text"))
        self.swing.apply_writes = True
        self.link.step()             # the link reads the Swing again after a mismatch
        app.process_link_events()
        self.assertEqual(app.settings["mod_cc"], 127)
        app.set_value("mod_cc", 1)
        self.sync(app)
        self.assertEqual(self.swing.values[0x14], 1)

    def test_status_click_reads_again(self):
        app = self.make_app()
        self.swing.values[0x57] = 3     # changed on the Swing itself
        app.on_status_click()
        self.sync(app)
        self.assertEqual(app.settings["led_brightness"], 3)

    def test_undo_restores_what_the_swing_had(self):
        app = self.make_app()
        app.set_value("led_brightness", 9)
        app.set_value("note_priority", 2)
        self.sync(app)
        self.answer = False
        app.undo_all()
        self.assertEqual(app.settings["led_brightness"], 9)
        self.answer = True
        app.undo_all()
        self.sync(app)
        self.assertEqual(SwingSettings(self.swing.values), SwingSettings())
        self.assertEqual(len(self.answers), 2)

    # --- DAW mode
    def test_daw_mode_on_and_off(self):
        self.swing.values[0x0E] = 1   # Hold in Toggle, as on the real Swing
        app = self.make_app()
        button = app.action_buttons["daw_on"]
        self.assertEqual(button.cget("text"), "Modo DAW")
        self.answer = False
        app.toggle_daw_mode()
        self.assertEqual(self.swing.writes, [])
        self.answer = True
        app.toggle_daw_mode()
        self.sync(app)
        for key, value in daw_mode.DAW_SETTINGS.items():
            self.assertEqual(self.swing.values[protocol.param(key).id], value, key)
        self.assertEqual(button.cget("text"), "Salir del modo DAW")
        self.assertIn("Sync", app.message.cget("text"))
        app.toggle_daw_mode()
        self.sync(app)
        self.assertEqual(SwingSettings(self.swing.values), SwingSettings().set("hold_mode", 1))
        self.assertEqual(button.cget("text"), "Modo DAW")

    def test_daw_mode_without_backup(self):
        values = dict(protocol.READ_DEFAULTS)
        for key, value in daw_mode.DAW_SETTINGS.items():
            values[protocol.param(key).id] = value
        self.swing.values = values
        app = self.make_app()
        app.toggle_daw_mode()
        self.assertIn("no hay ajustes anteriores", app.message.cget("text"))
        self.assertEqual(self.swing.writes, [])

    def test_daw_mode_needs_the_swing(self):
        self.present = False
        app = self.make_app()
        self.assertEqual(app.action_buttons["daw_on"].cget("state"), "disabled")

    # --- DAW bridge
    def bridge_app(self, available=("Swing to DAW", "DAW to Swing")):
        from test_bridge_io import FakeOpener
        self.virtual = FakeOpener(available)
        from swing_editor import bridge_io
        return self.make_app(bridge_factory=lambda settings: bridge_io.BridgeRunner(opener=self.virtual, settings=settings))

    def test_bridge_on_and_off(self):
        from test_bridge_io import wait_until
        app = self.bridge_app()
        self.assertFalse(hasattr(app, "panic_button"))
        app.bridge_switch.select()
        app.toggle_bridge()
        self.assertIsNotNone(app.bridge)
        self.assertIs(self.link.bridge, app.bridge)
        self.assertIn("Activo", app.bridge_label.cget("text"))
        self.assertIn("Swing to DAW", app.message.cget("text"))
        to_daw = self.virtual.ports["Swing to DAW"]
        self.swing.on_short(0x90, 60, 100)
        self.assertTrue(wait_until(lambda: (0x90, 60, 100) in to_daw.short))
        app.bridge_switch.deselect()
        app.toggle_bridge()
        self.assertIsNone(app.bridge)
        self.assertIsNone(self.link.bridge)
        self.assertTrue(to_daw.closed)
        self.assertTrue(wait_until(lambda: (0x80, 60, 0) in to_daw.short))

    def test_bridge_without_loopmidi(self):
        app = self.bridge_app(available=())
        app.bridge_switch.select()
        app.toggle_bridge()
        self.assertIsNone(app.bridge)
        self.assertEqual(app.bridge_switch.get(), 0)
        self.assertIn("loopMIDI", app.message.cget("text"))

    def test_bridge_follows_the_transport_settings(self):
        app = self.bridge_app()
        app.bridge_switch.select()
        app.toggle_bridge()
        app.set_value("rec_cc", 20)
        self.sync(app)
        self.assertEqual(app.bridge.bridge.settings["rec_cc"], 20)
        app._stop_bridge()

    # --- files
    def test_save_and_open(self):
        app = self.make_app(ask_save=lambda **kw: os.path.join(self.dir, "mine.json"),
                            ask_open=lambda **kw: os.path.join(self.dir, "mine.json"))
        app.set_value("velocity_curve", 2)
        app.save_file()
        app.set_value("velocity_curve", 0)
        app.open_file()
        self.sync(app)
        self.assertEqual(self.swing.values[0x19], 2)
        self.assertIn("Abierto", app.message.cget("text"))

    def test_open_keeps_unconfirmed_values(self):
        self.swing.values[0x28] = 1
        path = os.path.join(self.dir, "p.syx")
        presets.save(path, SwingSettings().set("led_brightness", 50))
        app = self.make_app(ask_open=lambda **kw: path)
        app.open_file()
        self.sync(app)
        self.assertEqual((self.swing.values[0x57], self.swing.values[0x28]), (50, 1))
        self.assertNotIn(0x28, [m[6] for m in self.swing.writes])

    def test_bad_file_changes_nothing(self):
        path = os.path.join(self.dir, "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}")
        app = self.make_app(ask_open=lambda **kw: path)
        before = app.settings
        app.open_file()
        self.assertEqual(app.settings, before)
        self.assertIn("Error", app.message.cget("text"))

    def test_sections(self):
        app = self.make_app()
        for section in protocol.SECTIONS:
            app.show_section(section)
            self.assertEqual(app.section, section)
            self.assertTrue(app.pages[section].winfo_manager())

    def test_close_applies_waiting_change(self):
        app = self.make_app()
        app.set_value("led_brightness", 15)
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.after_cancel(job)
        app.on_close()
        self.assertEqual(self.swing.values[0x57], 15)
        self.assertTrue(self.swing.closed)
        self.root = ctk.CTk()   # on_close destroyed the window; give close_root a fresh one
        self.root.withdraw()


if __name__ == "__main__":
    unittest.main()
