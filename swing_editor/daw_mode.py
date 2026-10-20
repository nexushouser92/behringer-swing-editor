"""DAW mode: a set of ordinary settings that make the Swing easier to use with a DAW over USB.

Turning it on saves the values it replaces in a small JSON file, so they can be put back later even
after the editor was closed. Only confirmed settings are involved; nothing else is changed.
"""
import json
import os

from . import protocol
from .protocol import ProtocolError

DAW_SETTINGS = {
    "play_channel": 15,      # transport on channel 16, away from the notes on channel 1
    "stop_channel": 15,
    "rec_channel": 15,
    "mod_cc": 1,             # the standard mod wheel CC
    "midi_thru": 0,          # off: nothing is echoed out of the MIDI jack
    "transpose_port": 0,     # transposition from USB only
    "velocity_curve": 0,     # linear
    "transport_mode": 1,     # MIDI CC only: with MMC as well, some DAWs act twice on one press
    "hold_function": 1,      # Hold keys: the Swing sends each note's own note off when Hold is released
}
# Hold mode is left alone on purpose: in Toggle it latches the arpeggiator, which DAW users need.
# See research/MESSAGE_FLOW.md for the reasons behind each value.

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
