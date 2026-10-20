"""Behringer Swing SysEx protocol (see research/PROTOCOL.md): parameter table, message building
and parsing, value validation. Pure data, no MIDI I/O.

Every message the app sends is built here, and only three kinds exist: product info (command 00),
read one known parameter, write one known parameter with a value inside its range.
"""
from dataclasses import dataclass

MANUFACTURER = bytes([0x00, 0x20, 0x32])   # Behringer
DEVICE_ALL = 0x7F
MODEL = 0x42                               # Swing
HEADER = bytes([0xF0]) + MANUFACTURER + bytes([DEVICE_ALL, MODEL])
SYSEX_END = 0xF7

CMD_PRODUCT_INFO = 0x00
CMD_STATUS = 0x70
# Never sent by this app: bootloader mode (77), bootloader status (74), clear a sequence (73).
FORBIDDEN_COMMANDS = frozenset({0x73, 0x74, 0x77})


class ProtocolError(Exception):
    """A value, preset or message does not follow the protocol."""


@dataclass(frozen=True)
class Param:
    """One global setting. `values` maps each allowed raw value to the label shown for it.

    confirmed: the meaning of the values was checked on a real Swing. Unconfirmed settings are read
    and kept (any data byte is accepted for them) but never written and not shown in the window.
    """
    id: int
    key: str
    section: str
    label: str
    values: tuple          # ((raw value, label), ...)
    confirmed: bool = False

    @property
    def allowed(self):
        return tuple(v for v, _ in self.values)

    def label_of(self, value):
        for v, text in self.values:
            if v == value:
                return text
        return f"? ({value})"

    def validate(self, value):
        allowed = self.allowed if self.confirmed else range(128)
        if not isinstance(value, int) or isinstance(value, bool) or value not in allowed:
            raise ProtocolError(f"{self.key}: value {value!r} is not allowed")


def _numbers(lo, hi):
    return tuple((v, str(v)) for v in range(lo, hi + 1))


def _choices(*labels):
    return tuple(enumerate(labels))


NOTE_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B")


def note_name(n):
    """MIDI note number in the Swing editor's naming, where 60 is C3."""
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 2}"


CHANNELS = tuple((v, str(v + 1)) for v in range(16))
CH_USER = CHANNELS + ((65, "User"),)
CH_ALL_NONE = CHANNELS + ((65, "All"), (126, "None"))
NOTES = tuple((n, note_name(n)) for n in range(128))
DATA = _numbers(0, 127)
OFF_ON = _choices("Off", "On")
GATE_TOGGLE = _choices("Gate", "Toggle")
HOLD_FUNCTION = ((1, "Hold keys"), (2, "Sustain message"), (3, "Both"))   # starts at 1
RANDOM_MODE = _choices("Total", "Pattern", "Brownian")
C = True   # values checked on a real Swing with Control Tribe (research/snapshots)

_P = Param
PARAMS = (
    _P(0x16, "output_channel", "midi", "Output channel", CHANNELS, C),
    _P(0x07, "midi_in_channel", "midi", "MIDI In channel", CH_USER, C),
    _P(0x08, "midi_thru", "midi", "MIDI Thru", OFF_ON, C),

    _P(0x19, "velocity_curve", "keyboard", "Velocity curve",
       _choices("Linear", "Logarithmic", "Anti-logarithmic"), C),
    _P(0x29, "velocity_mode", "keyboard", "Velocity", _choices("As played", "Fixed"), C),
    _P(0x2A, "fixed_velocity", "keyboard", "Fixed velocity", DATA, C),
    _P(0x1A, "aftertouch_curve", "keyboard", "Aftertouch curve",
       _choices("Linear", "Logarithmic", "Anti-logarithmic")),  # Soft as a 4th option? (to check)

    _P(0x10, "sustain_function", "pedals", "Sustain pedal function", HOLD_FUNCTION, C),
    _P(0x09, "sustain_mode", "pedals", "Sustain pedal mode", GATE_TOGGLE, C),
    _P(0x0A, "sustain_channel", "pedals", "Sustain message channel", CH_USER, C),
    _P(0x0D, "sustain_cc", "pedals", "Sustain CC number", DATA, C),
    _P(0x0B, "sustain_cc_low", "pedals", "Sustain CC value (released)", DATA, C),
    _P(0x0C, "sustain_cc_high", "pedals", "Sustain CC value (pressed)", DATA, C),
    _P(0x0F, "hold_function", "pedals", "Hold switch function", HOLD_FUNCTION, C),
    _P(0x0E, "hold_mode", "pedals", "Hold switch mode", GATE_TOGGLE, C),

    _P(0x13, "mod_channel", "mod_pitch", "Mod MIDI channel", CH_USER, C),
    _P(0x14, "mod_cc", "mod_pitch", "Mod CC number", DATA, C),
    _P(0x15, "pitch_bend_channel", "mod_pitch", "Pitch bend MIDI channel", CH_USER, C),

    _P(0x20, "clock_mode", "clock", "Clock input",
       _choices("1 step (gate)", "1 step (clock)", "1 pulse (Korg)", "24 ppq", "48 ppq"), C),
    _P(0x23, "clock_start", "clock", "Clock start", _choices("On clock", "On gate start"), C),
    _P(0x22, "tap_tempo_count", "clock", "Tap tempo", _choices("2 taps", "3 taps", "4 taps"), C),
    _P(0x28, "tempo_knob", "clock", "Tempo knob", _choices("Jump", "Pickup")),  # did not change with Control Tribe's Tempo mode

    _P(0x24, "next_sequence", "sequencer", "Next sequence",
       _choices("At the end", "Instant reset", "Instant continue"), C),
    _P(0x25, "arm_to_start", "sequencer", "Arm to start", OFF_ON, C),
    _P(0x2C, "tie_mode", "sequencer", "Tie mode", _choices("Tie to previous", "Tie to next"), C),
    _P(0x2D, "arpeggiator_random", "sequencer", "Arpeggiator random mode", RANDOM_MODE),  # not shown by Control Tribe

    _P(0x27, "transpose_port", "transpose", "Transposition input", _choices("USB", "MIDI", "USB and MIDI"), C),
    _P(0x21, "transpose_channel", "transpose", "Transposition channel", CH_ALL_NONE, C),
    _P(0x26, "transpose_latch", "transpose", "Transposition latch", ((0, "On"), (1, "Off")), C),   # 0 is On
    _P(0x2B, "transpose_center", "transpose", "Transposition center note", NOTES, C),

    _P(0x47, "gate_output", "cv", "Gate output level", _choices("S-trig", "V-trig 5 V", "V-trig 12 V"), C),
    _P(0x46, "pitch_output", "cv", "Pitch CV mode", _choices("Volts per octave", "Hertz per volt"), C),
    _P(0x4C, "pitch_0v_note", "cv", "Note at 0 V", NOTES, C),
    _P(0x4A, "pitch_1v_note", "cv", "Note at 1 V", NOTES, C),
    _P(0x4D, "note_priority", "cv", "Note priority", _choices("Low", "High", "Last"), C),
    _P(0x50, "pitch_range", "cv", "Pitch range", DATA, C),
    _P(0x4E, "mod_cv_source", "cv", "Mod output source", _choices("Mod strip", "Velocity", "Aftertouch"), C),
    _P(0x4F, "mod_cv_max", "cv", "Mod output max voltage", tuple((v, f"{v} V") for v in range(5, 13)), C),

    _P(0x60, "transport_mode", "transport", "Transport messages", _choices("Off", "MIDI CC", "MMC", "Both"), C),
    _P(0x67, "play_pause", "transport", "Play/Pause button", _choices("Pause", "Reset"), C),
    _P(0x63, "play_channel", "transport", "Play MIDI channel", CHANNELS, C),
    _P(0x66, "play_cc", "transport", "Play CC number", DATA, C),
    _P(0x61, "stop_channel", "transport", "Stop MIDI channel", CHANNELS, C),
    _P(0x64, "stop_cc", "transport", "Stop CC number", DATA, C),
    _P(0x62, "rec_channel", "transport", "Rec MIDI channel", CHANNELS, C),
    _P(0x65, "rec_cc", "transport", "Rec CC number", DATA, C),

    _P(0x57, "led_brightness", "lights", "LED brightness", DATA, C),
)

EDITABLE = tuple(p for p in PARAMS if p.confirmed)
BY_ID = {p.id: p for p in PARAMS}
BY_KEY = {p.key: p for p in PARAMS}
SECTIONS = ("midi", "keyboard", "pedals", "mod_pitch", "clock", "sequencer", "transpose", "cv",
            "transport", "lights")

# Values read on 2026-10-20 from a Swing (firmware 1.1.52) whose settings were never changed.
READ_DEFAULTS = {
    0x07: 0, 0x08: 0, 0x09: 0, 0x0A: 65, 0x0B: 0, 0x0C: 127, 0x0D: 64, 0x0E: 1, 0x0F: 1, 0x10: 2,
    0x13: 0, 0x14: 127, 0x15: 0, 0x16: 0, 0x19: 1, 0x1A: 0, 0x20: 2, 0x21: 65, 0x22: 2, 0x23: 0,
    0x24: 0, 0x25: 0, 0x26: 0, 0x27: 0, 0x28: 0, 0x29: 0, 0x2A: 127, 0x2B: 60, 0x2C: 1, 0x2D: 0,
    0x46: 0, 0x47: 1, 0x4A: 0, 0x4C: 0, 0x4D: 1, 0x4E: 0, 0x4F: 12, 0x50: 24, 0x57: 127, 0x60: 3,
    0x61: 0, 0x62: 0, 0x63: 0, 0x64: 51, 0x65: 50, 0x66: 54, 0x67: 0,
}


def param(id_or_key):
    p = BY_ID.get(id_or_key) if isinstance(id_or_key, int) else BY_KEY.get(id_or_key)
    if p is None:
        raise ProtocolError(f"unknown parameter {id_or_key!r}")
    return p


class SwingSettings:
    """The 47 global settings, keyed by parameter id, always complete and valid."""

    def __init__(self, values=None):
        values = dict(READ_DEFAULTS if values is None else values)
        missing = set(BY_ID) - set(values)
        extra = set(values) - set(BY_ID)
        if missing or extra:
            raise ProtocolError(f"settings must have exactly the {len(BY_ID)} known parameters"
                                f" (missing {sorted(missing)}, unknown {sorted(extra)})")
        for pid, value in values.items():
            BY_ID[pid].validate(value)
        self._values = values

    def __getitem__(self, id_or_key):
        return self._values[param(id_or_key).id]

    def set(self, id_or_key, value):
        """Return a copy with one value changed (validated)."""
        p = param(id_or_key)
        p.validate(value)
        values = dict(self._values)
        values[p.id] = value
        return SwingSettings(values)

    def items(self):
        """(Param, value) in table order."""
        return [(p, self._values[p.id]) for p in PARAMS]

    def as_dict(self):
        return dict(self._values)

    def differences(self, other):
        """Editable ids whose value differs from other, in table order."""
        return [p.id for p in EDITABLE if self._values[p.id] != other[p.id]]

    def with_editable_from(self, other):
        """A copy of self with the editable settings taken from other (unconfirmed ones stay)."""
        values = dict(self._values)
        values.update({p.id: other[p.id] for p in EDITABLE})
        return SwingSettings(values)

    def __eq__(self, other):
        return isinstance(other, SwingSettings) and self._values == other._values

    def __repr__(self):
        return f"SwingSettings({self._values!r})"


# --- messages the app sends

def build_product_info_request():
    return HEADER + bytes([CMD_PRODUCT_INFO, SYSEX_END])


def build_read(id_or_key):
    return HEADER + bytes([param(id_or_key).id, SYSEX_END])


def build_write(id_or_key, value):
    p = param(id_or_key)
    if not p.confirmed:
        raise ProtocolError(f"{p.key} is not confirmed on a real Swing: it is never written")
    p.validate(value)
    return HEADER + bytes([p.id, value, SYSEX_END])


def check_outgoing(message):
    """Last guard before anything reaches the Swing: only the three kinds of message above."""
    m = bytes(message)
    ok = (m[:len(HEADER)] == HEADER and m[-1:] == bytes([SYSEX_END]) and len(m) in (8, 9)
          and m[6] not in FORBIDDEN_COMMANDS)
    if ok and len(m) == 8:
        ok = m[6] == CMD_PRODUCT_INFO or m[6] in BY_ID
    elif ok:
        ok = m[6] in BY_ID and BY_ID[m[6]].confirmed and m[7] in BY_ID[m[6]].allowed
    if not ok:
        raise ProtocolError(f"refusing to send {m.hex(' ')}")
    return m


# --- messages the Swing sends

@dataclass(frozen=True)
class ProductInfo:
    versions: tuple   # ((a, b, c), (a, b, c)): firmware is most likely the second one


@dataclass(frozen=True)
class Value:
    id: int
    value: int


@dataclass(frozen=True)
class Ack:
    id: int


@dataclass(frozen=True)
class Status:
    data: bytes       # decoded from the 8-in-7 packing


def is_swing_message(message):
    m = bytes(message)
    return (len(m) >= 8 and m[0] == 0xF0 and m[-1] == SYSEX_END and m[1:4] == MANUFACTURER
            and m[5] == MODEL)


def unpack_7bit(data):
    """Undo the 8-in-7 packing: in every group of 8 bytes the first holds the high bits of the next 7."""
    out = bytearray()
    for start in range(0, len(data), 8):
        group = data[start:start + 8]
        high = group[0]
        for i, b in enumerate(group[1:]):
            out.append(b | (((high >> i) & 1) << 7))
    return bytes(out)


def parse(message):
    """Swing message -> ProductInfo, Value, Ack or Status; None for anything else."""
    if not is_swing_message(message):
        return None
    m = bytes(message)
    cmd, body = m[6], m[7:-1]
    if cmd == CMD_PRODUCT_INFO and len(body) == 6:
        return ProductInfo((tuple(body[:3]), tuple(body[3:])))
    if cmd == CMD_STATUS:
        return Status(unpack_7bit(body))
    if cmd in BY_ID and len(body) == 1:
        return Value(cmd, body[0])
    if cmd in BY_ID and len(body) == 0:
        return Ack(cmd)
    return None
