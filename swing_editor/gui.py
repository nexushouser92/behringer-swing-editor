"""Main window (CustomTkinter), with the same look as Orbit Editor.

The Swing stays linked while the window is open (link.py): it is found automatically, its settings
are read, and every change is applied to it a moment after the last edit and verified.
Only the settings confirmed on a real Swing are shown (protocol.EDITABLE).
"""
import time
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import __version__, bridge_io, daw_mode, presets, protocol
from .device import VerifyError
from .midi_win import MidiError
from .i18n import Translator
from .link import SwingLink
from .protocol import ProtocolError, SwingSettings

BG = "#121418"
CARD = "#1b1e24"
CARD_HI = "#262b34"
EDGE = "#333944"
TEXT = "#e9ecf1"
MUTED = "#8a93a3"
ACCENT = "#3d8bfd"
ACCENT_HOVER = "#2f6fd0"
OK = "#2fbf71"
OK_DARK = "#1d6e45"
ERROR = "#ff6159"
FONT = "Segoe UI"

CONTENT_W, CONTENT_H = 660, 590
WRITTEN_SECONDS = 2.0


class Spin(ctk.CTkFrame):
    """[-] number [+]; calls on_change(int) with a value in low..high. Invalid input is put back."""

    def __init__(self, master, low, high, on_change, width=52):
        super().__init__(master, fg_color="transparent")
        self.low, self.high, self.on_change = low, high, on_change
        self.value = None
        style = dict(width=28, height=30, fg_color=CARD_HI, hover_color=EDGE, corner_radius=8)
        self.minus = ctk.CTkButton(self, text="−", command=lambda: self.step(-1), **style)
        self.entry = ctk.CTkEntry(self, width=width, height=30, justify="center", border_width=1,
                                  border_color=EDGE, fg_color=BG, corner_radius=8)
        self.plus = ctk.CTkButton(self, text="+", command=lambda: self.step(1), **style)
        self.minus.pack(side="left")
        self.entry.pack(side="left", padx=4)
        self.plus.pack(side="left")
        self.entry.bind("<Return>", self.commit)
        self.entry.bind("<FocusOut>", self.commit)

    def set(self, value):
        if value != self.value or self.entry.get() != str(value):
            self.value = value
            self.entry.delete(0, "end")
            self.entry.insert(0, str(value))

    def get_text(self):
        return self.entry.get()

    def set_text(self, text):
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def step(self, delta):
        if self.value is None:
            return
        value = min(self.high, max(self.low, self.value + delta))
        if value != self.value:
            self.on_change(value)

    def commit(self, event=None):
        try:
            value = int(self.entry.get())
            if not self.low <= value <= self.high:
                raise ValueError
        except ValueError:
            self.set(self.value if self.value is not None else self.low)
            return
        if value != self.value:
            self.on_change(value)


class Control:
    """The widget for one setting, translating between raw values and what is shown."""

    def __init__(self, app, parent, param):
        self.param = param
        t = app.t
        self.labels = [t.option(label) for _, label in param.values]
        on_label = lambda label: app.set_value(param.key, param.values[self.labels.index(label)][0])
        if param.values is protocol.DATA or param.values is protocol.NOTES:
            self.kind = "slider" if param.key == "led_brightness" else "number"
            if self.kind == "slider":
                self.widget = ctk.CTkFrame(parent, fg_color="transparent")
                self.slider = ctk.CTkSlider(self.widget, from_=0, to=127, number_of_steps=127, width=200,
                                            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                                            progress_color=ACCENT, fg_color=CARD_HI,
                                            command=lambda v: app.set_value(param.key, int(round(v))))
                self.slider.pack(side="left")
                self.value_label = ctk.CTkLabel(self.widget, text="", width=40, font=(FONT, 13, "bold"),
                                                text_color=TEXT)
                self.value_label.pack(side="left", padx=(8, 0))
            else:
                self.widget = ctk.CTkFrame(parent, fg_color="transparent")
                self.spin = Spin(self.widget, 0, 127, lambda v: app.set_value(param.key, v))
                self.spin.pack(side="left")
                self.note_label = None
                if param.values is protocol.NOTES:
                    self.note_label = ctk.CTkLabel(self.widget, text="", width=48, font=(FONT, 14, "bold"),
                                                   text_color=TEXT)
                    self.note_label.pack(side="left", padx=(8, 0))
        elif len(self.labels) <= 3 and sum(len(label) for label in self.labels) <= 30:
            self.kind = "segmented"
            self.widget = app._segmented(parent, self.labels, on_label)
        else:
            self.kind = "option"
            self.widget = app._option(parent, self.labels, on_label,
                                      width=220 if max(len(label) for label in self.labels) > 4 else 110)

    def show(self, value):
        if self.kind == "slider":
            self.slider.set(value)
            self.value_label.configure(text=str(value))
        elif self.kind == "number":
            self.spin.set(value)
            if self.note_label is not None:
                self.note_label.configure(text=protocol.note_name(value))
        else:
            self.widget.set(self.labels[self.param.allowed.index(value)])


class App(ctk.CTkFrame):
    def __init__(self, master, lang=None, link=None, autostart=True,
                 ask_yes_no=messagebox.askyesno, ask_open=filedialog.askopenfilename,
                 ask_save=filedialog.asksaveasfilename, clock=time.monotonic, backup_path=None,
                 bridge_factory=bridge_io.BridgeRunner):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.bridge_factory = bridge_factory
        self.bridge = None            # bridge_io.BridgeRunner while the DAW bridge is on
        self.backup_path = backup_path or daw_mode.default_backup_path()
        self.t = Translator(lang)
        self.link = link or SwingLink()
        self.ask_yes_no, self.ask_open, self.ask_save, self.clock = ask_yes_no, ask_open, ask_save, clock
        self.settings = None          # what the window shows and wants on the Swing
        self.original = None          # what the Swing had when it was linked (for "Undo changes")
        self.section = protocol.SECTIONS[0]
        self.controls = {}
        self._shown = {}              # last value pushed to each widget, to avoid redrawing (flicker)
        self._reading = False
        self._busy = False            # the Swing is there but another program has its port
        self._writing = False
        self._failed = False
        self._written_at = -100.0

        self.master.title(self.t("title"))
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build()
        self.pack(fill="both", expand=True)
        self.refresh()
        if autostart:
            self.link.start()
            self.after(40, self._poll)

    # ------------------------------------------------------------------ layout helpers
    def _card(self, parent, **kw):
        return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=16, border_width=1, border_color="#232730", **kw)

    def _segmented(self, parent, values, command, **kw):
        return ctk.CTkSegmentedButton(parent, values=values, command=command, selected_color=ACCENT,
                                      selected_hover_color=ACCENT_HOVER, unselected_color=CARD_HI,
                                      unselected_hover_color=EDGE, fg_color=CARD_HI, corner_radius=8,
                                      font=(FONT, 12), height=30, **kw)

    def _option(self, parent, values, command, width=110):
        return ctk.CTkOptionMenu(parent, values=values, command=command, width=width, height=30,
                                 fg_color=CARD_HI, button_color=CARD_HI, button_hover_color=EDGE,
                                 corner_radius=8, dynamic_resizing=False, font=(FONT, 12))

    def _show(self, key, value, apply):
        """Call apply(value) only if value changed since last time (prevents flicker)."""
        if self._shown.get(key, object()) != value:
            self._shown[key] = value
            apply(value)

    # ------------------------------------------------------------------ build
    def _build(self):
        t = self.t
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(16, 12))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", padx=(0, 28))
        ctk.CTkLabel(titles, text=t("heading"), font=(FONT, 22, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(titles, text=t("subheading"), font=(FONT, 12), text_color=MUTED).pack(anchor="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        plain = dict(height=36, fg_color=CARD_HI, hover_color=EDGE, corner_radius=10, font=(FONT, 13))
        self.action_buttons = {}
        for key, command, width in (("open", self.open_file, 80), ("save", self.save_file, 86),
                                    ("undo_all", self.undo_all, 132), ("daw_on", self.toggle_daw_mode, 140)):
            button = ctk.CTkButton(actions, text=t(key), width=width, command=command, **plain)
            button.pack(side="left", padx=(0, 6))
            self.action_buttons[key] = button
        ctk.CTkFrame(actions, fg_color="transparent", width=6, height=1).pack(side="left")
        self.status_button = ctk.CTkButton(actions, text="", width=290, height=36, corner_radius=18,
                                           font=(FONT, 13, "bold"), command=self.on_status_click)
        self.status_button.pack(side="left")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22)

        nav = self._card(body)
        nav.pack(side="left", fill="y")
        self.nav_buttons = {}
        for section in protocol.SECTIONS:
            button = ctk.CTkButton(nav, text=t(section), width=180, height=36, anchor="w", corner_radius=10,
                                   font=(FONT, 13), fg_color="transparent", hover_color=CARD_HI,
                                   text_color=TEXT, command=lambda s=section: self.show_section(s))
            button.pack(padx=12, pady=(12 if section == protocol.SECTIONS[0] else 2, 0))
            self.nav_buttons[section] = button
        self.firmware_label = ctk.CTkLabel(nav, text="", font=(FONT, 11), text_color=MUTED)
        self.firmware_label.pack(side="bottom", pady=(6, 14))
        daw_box = ctk.CTkFrame(nav, fg_color=CARD_HI, corner_radius=12)
        daw_box.pack(side="bottom", fill="x", padx=12, pady=(10, 0))
        self.bridge_switch = ctk.CTkSwitch(daw_box, text=t("bridge"), font=(FONT, 13), text_color=TEXT,
                                           progress_color=ACCENT, command=self.toggle_bridge)
        self.bridge_switch.pack(anchor="w", padx=12, pady=(10, 2))
        self.bridge_label = ctk.CTkLabel(daw_box, text=t("bridge_off_hint"), font=(FONT, 10), text_color=MUTED,
                                         justify="left", wraplength=170, anchor="w")
        self.bridge_label.pack(fill="x", padx=12)
        self.content = self._card(body, width=CONTENT_W, height=CONTENT_H)
        self.content.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.content.pack_propagate(False)
        self.placeholder = ctk.CTkLabel(self.content, text=t("no_swing"), font=(FONT, 15), text_color=MUTED,
                                        justify="center")
        self.pages = {}
        for section in protocol.SECTIONS:
            self.pages[section] = self._build_page(section)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(10, 12))
        self.message = ctk.CTkLabel(footer, text="", font=(FONT, 12), text_color=MUTED, anchor="w")
        self.message.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(footer, text=f"{t('disclaimer')}   v{__version__}", font=(FONT, 11),
                     text_color="#5d6573").pack(side="right")

    def _build_page(self, section):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(page, text=self.t(section), font=(FONT, 17, "bold"), text_color=TEXT,
                     anchor="w").pack(fill="x", padx=22, pady=(18, 6))
        for param in protocol.EDITABLE:
            if param.section != section:
                continue
            row = ctk.CTkFrame(page, fg_color="transparent")
            row.pack(fill="x", padx=22, pady=6)
            texts = ctk.CTkFrame(row, fg_color="transparent")
            texts.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(texts, text=self.t.param_label(param), font=(FONT, 13), text_color=TEXT,
                         anchor="w", height=22).pack(fill="x")
            help_text = self.t.param_help(param)
            if help_text:
                ctk.CTkLabel(texts, text=help_text, font=(FONT, 11), text_color=MUTED, anchor="w",
                             justify="left", wraplength=340, height=16).pack(fill="x")
            control = Control(self, row, param)
            control.widget.pack(side="right")
            self.controls[param.key] = control
        return page

    # ------------------------------------------------------------------ actions
    def show_section(self, section):
        self.section = section
        self.refresh()

    def set_value(self, key, value):
        if self.settings is None:
            return
        try:
            new = self.settings.set(key, value)
        except ProtocolError as e:
            self.show(self.t("error", err=e), ERROR)
            self.refresh()
            return
        if new != self.settings:
            self.settings = new
            self._failed = False
            self.link.push(new)
        self.refresh()

    def refresh(self):
        for section, button in self.nav_buttons.items():
            selected = section == self.section
            self._show(("nav", section), selected, lambda s, b=button: b.configure(
                fg_color=ACCENT if s else "transparent", hover_color=ACCENT_HOVER if s else CARD_HI))
        page = self.pages[self.section] if self.settings is not None else self.placeholder
        self._show("page", page, self._place_page)
        if self.settings is not None:
            for key, control in self.controls.items():
                self._show(("value", key), self.settings[key], control.show)
        state = "normal" if self.settings is not None else "disabled"
        self._show("save_state", state, lambda s: self.action_buttons["save"].configure(state=s))
        undo = "normal" if self.original is not None and self.link.linked else "disabled"
        self._show("undo_state", undo, lambda s: self.action_buttons["undo_all"].configure(state=s))
        bridge_on = self.bridge is not None
        self._show("bridge", (bridge_on, self.link.linked), lambda b:
            self.bridge_label.configure(text=self.t("bridge_on_hint" if b[0] else "bridge_off_hint"),
                                        text_color=(OK if b[1] else MUTED) if b[0] else MUTED))
        active = self.settings is not None and daw_mode.is_active(self.settings)
        daw = ("disabled" if self.settings is None else "normal", active)
        self._show("daw", daw, lambda d: self.action_buttons["daw_on"].configure(
            state=d[0], text=self.t("daw_off" if d[1] else "daw_on"),
            fg_color=ACCENT if d[1] else CARD_HI, hover_color=ACCENT_HOVER if d[1] else EDGE))
        self._draw_status()

    def _place_page(self, page):
        for child in self.content.winfo_children():
            child.pack_forget()
            child.place_forget()
        if page is self.placeholder:
            page.place(relx=0.5, rely=0.5, anchor="center")
        else:
            page.pack(fill="both", expand=True)

    def show(self, text, color=MUTED):
        self.message.configure(text=text, text_color=color)

    # ------------------------------------------------------------------ link events
    def _poll(self):
        self.process_link_events()
        self.after(40, self._poll)

    def process_link_events(self):
        while not self.link.events.empty():
            kind, payload = self.link.events.get_nowait()
            if kind == "linked":
                self._reading, self._new_link, self._busy = True, True, False
                self.show(self.t("reading"))
            elif kind == "info":
                self.firmware_label.configure(text=self.t("firmware", v=".".join(map(str, payload[1]))))
            elif kind == "settings":
                self._reading = False
                if self.bridge is not None:
                    self.bridge.bridge.settings = payload   # it follows the transport channel and CCs
                if getattr(self, "_new_link", False):
                    self._new_link = False
                    self.original = payload
                if self.settings is None or not self.link.has_pending:
                    self.settings = payload
                else:
                    self.settings = payload.with_editable_from(self.settings)
                if not self._failed:
                    self.show(self.t("read_ok"), OK)
            elif kind == "writing":
                self._writing = True
            elif kind == "written":
                self._writing, self._failed = False, False
                if self.bridge is not None:
                    self.bridge.bridge.settings = payload
                self._written_at = self.clock()
            elif kind == "write_failed":
                self._writing, self._failed = False, True
                self.show(self.t("verify_error", err=payload) if isinstance(payload, VerifyError)
                          else self.t("write_error", err=payload), ERROR)
            elif kind == "searching":
                self._reading = self._writing = False
                busy = isinstance(payload, MidiError) and "open" in str(payload).lower()
                if busy and not self._busy:
                    self.show(self.t("port_busy"), ERROR)
                elif not busy and self._busy:
                    self.show("")
                self._busy = busy
        self.refresh()

    def _status(self):
        if not self.link.linked:
            if self._busy:
                return "status_busy", "#5c2422", "#ffd6d3"
            return "status_searching", CARD_HI, MUTED
        if self._reading:
            return "status_reading", OK_DARK, "#ffffff"
        if self._failed:
            return "status_failed", "#5c2422", "#ffd6d3"
        if self._writing or self.link.has_pending:
            return "status_writing", ACCENT, "#ffffff"
        if self.clock() - self._written_at < WRITTEN_SECONDS:
            return "status_written", OK, "#ffffff"
        return "status_linked", OK_DARK, "#ffffff"

    def _draw_status(self):
        key, bg, fg = self._status()
        self._show("status", key, lambda _: self.status_button.configure(
            text=self.t(key), fg_color=bg, hover_color=bg, text_color=fg))

    def on_status_click(self):
        """After an error, apply the settings again; otherwise read the Swing again."""
        if not self.link.linked:
            return
        if self._failed and self.settings is not None:
            self._failed = False
            self.link.push(self.settings)
            self.link.flush()
        else:
            self.link.request_read()
            self._reading = True
        self.refresh()

    # ------------------------------------------------------------------ files and undo
    def _file_types(self):
        return [(self.t("file_types_json"), "*.json"), (self.t("file_types_syx"), "*.syx")]

    def open_file(self):
        path = self.ask_open(filetypes=self._file_types())
        if not path:
            return
        try:
            loaded = presets.load(path)
        except (ProtocolError, OSError) as e:
            self.show(self.t("error", err=e), ERROR)
            return
        base = self.settings if self.settings is not None else SwingSettings()
        self.settings = base.with_editable_from(loaded)
        self.link.push(self.settings)
        self.show(self.t("opened", path=path), OK)
        self.refresh()

    def save_file(self):
        if self.settings is None:
            return
        path = self.ask_save(filetypes=self._file_types(), defaultextension=".json")
        if not path:
            return
        try:
            presets.save(path, self.settings)
            self.show(self.t("saved", path=path), OK)
        except (ProtocolError, OSError) as e:
            self.show(self.t("error", err=e), ERROR)

    def toggle_daw_mode(self):
        """Put the Swing in DAW mode, or back to the settings it had before."""
        if self.settings is None:
            return
        try:
            if daw_mode.is_active(self.settings):
                if not daw_mode.has_backup(self.backup_path):
                    self.show(self.t("daw_no_backup"))
                    return
                if not self.ask_yes_no(self.t("daw_off"), self.t("daw_off_confirm")):
                    return
                self.settings = daw_mode.turn_off(self.settings, self.backup_path)
                self.show(self.t("daw_off_done"), OK)
            else:
                if not self.ask_yes_no(self.t("daw_on"), self.t("daw_on_confirm")):
                    return
                self.settings = daw_mode.turn_on(self.settings, self.backup_path)
                self.show(self.t("daw_on_done"), OK)
        except (ProtocolError, OSError) as e:
            self.show(self.t("error", err=e), ERROR)
            return
        self._failed = False
        self.link.push(self.settings)
        self.refresh()

    # ------------------------------------------------------------------ DAW bridge
    def toggle_bridge(self):
        if self.bridge_switch.get():
            runner = self.bridge_factory(settings=self.link.on_swing or self.settings)
            try:
                runner.open()
            except (MidiError, OSError) as e:
                self.bridge_switch.deselect()
                self.show(self.t("bridge_missing", err=e), ERROR)
                return
            self.bridge = runner
            self.link.set_bridge(runner)
            self.show(self.t("bridge_on_done"), OK)
        else:
            self._stop_bridge()
            self.show(self.t("bridge_off_done"))
        self.refresh()

    def _stop_bridge(self):
        runner, self.bridge = self.bridge, None
        if runner is not None:
            self.link.set_bridge(None)
            runner.panic()
            runner.close()

    def undo_all(self):
        if self.original is None or self.settings is None:
            return
        if not self.ask_yes_no(self.t("undo_title"), self.t("undo_confirm")):
            return
        self.settings = self.settings.with_editable_from(self.original)
        self.link.push(self.settings)
        self.show(self.t("undo_done"))
        self.refresh()

    def on_close(self):
        self._stop_bridge()
        self.link.stop()   # applies any change still waiting before closing the port
        self.master.destroy()


def main(lang=None):
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk(fg_color=BG)
    root.resizable(False, False)
    App(root, lang=lang)
    root.mainloop()


if __name__ == "__main__":
    main()
