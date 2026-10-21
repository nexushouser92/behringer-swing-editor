"""DAW mode: turns the Swing into a plain MIDI controller — one clean layer with nothing in the way.

It leaves only what a controller needs: the keys, OCT-/OCT+, Hold, pitch bend and modulation, all on
channel 1, over USB and the DIN MIDI out. Everything else the Swing can leak over USB is silenced:
Play/Stop/Rec send nothing (so the Arp + REC/STOP/PLAY clock-source combos leak nothing either),
nothing transposes the sequencer, and the mod strip uses the standard CC 1.

The arpeggiator, the sequencer and the Arp + clock-source combos are front-panel features with no
SysEx switch to disable them (see research/MESSAGE_FLOW.md, "Not possible from outside the Swing");
turning transport off is what makes them harmless to a DAW. The clock echo is a DAW-side sync setting.

Turning it on saves the values it replaces in a small JSON file, so they can be put back later even
after the editor was closed. Only confirmed settings are involved; nothing else is changed.
"""
import json
import os

from . import protocol
from .protocol import ProtocolError

DAW_SETTINGS = {
    "transport_mode": 0,      # Off: Play/Stop/Rec send nothing, so Arp + REC/STOP/PLAY leak nothing to the DAW
    "transpose_channel": 126, # None: nothing transposes the sequencer (no stray octave jumps from the DAW)
    "mod_cc": 1,              # the standard mod wheel CC, not the reserved CC 127
    "midi_thru": 0,           # off: nothing is echoed out of the MIDI jack
    "velocity_curve": 0,      # linear: the full velocity range
    "velocity_mode": 0,       # As played: not stuck on a fixed velocity
    "hold_function": 1,       # Hold keys: the Swing sends each note's own note off when Hold is released
    "output_channel": 0,      # channel 1: a single, predictable note channel
    "mod_channel": 0,         # mod strip on channel 1 too
    "pitch_bend_channel": 0,  # pitch bend on channel 1 too
}
# Hold mode (Gate/Toggle) is left alone on purpose: it only changes how Hold latches, not what leaks,
# and Toggle is what lets Hold keep a chord. See research/MESSAGE_FLOW.md for the reasons behind each value.

for _key, _value in DAW_SETTINGS.items():
    protocol.param(_key).validate(_value)
    assert protocol.param(_key).confirmed


def default_backup_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Swing Editor", "before_daw_mode.json")


def is_active(settings):
    return all(settings[key] == value for key, value in DAW_SETTINGS.items())


def turn_on(settings, backup_path):
    """Return settings in DAW mode, after saving the values it replaces (unless a backup exists)."""
    if not os.path.exists(backup_path):
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump({key: settings[key] for key in DAW_SETTINGS}, f, indent=1)
    result = settings
    for key, value in DAW_SETTINGS.items():
        result = result.set(key, value)
    return result


def has_backup(backup_path):
    return os.path.exists(backup_path)


def turn_off(settings, backup_path):
    """Return settings with the values saved before DAW mode, and delete the backup."""
    try:
        with open(backup_path, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ProtocolError(f"cannot read the saved settings: {e}") from None
    result = settings
    for key in DAW_SETTINGS:
        if key in saved:
            result = result.set(key, saved[key])   # validates every value
    os.remove(backup_path)
    return result
