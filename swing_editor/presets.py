"""Save and load Swing settings: our own readable JSON presets and .syx files.

Presets hold the editable (confirmed) settings only. JSON stores each one by its name with the raw
value the Swing uses (channels 0-15, 65 = User or All, 126 = None; see protocol.py) plus its label,
so a preset can be read by a person; only the values are used when loading. A .syx file is the list
of write messages, one per editable setting.
"""
import json
import os

from . import protocol
from .protocol import ProtocolError, SwingSettings

FORMAT_NAME = "swing-editor-preset"
FORMAT_VERSION = 1


def to_dict(settings):
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "settings": {p.key: {"value": settings[p.id], "label": p.label_of(settings[p.id])}
                     for p in protocol.EDITABLE},
    }


def from_dict(data):
    """Preset dict -> SwingSettings. Settings missing from the preset keep the read defaults, and
    unconfirmed ones in it are ignored (use with_editable_from() to apply a preset to a Swing)."""
    try:
        if data.get("format") != FORMAT_NAME:
            raise ProtocolError("not a Swing Editor preset")
        if data.get("version") != FORMAT_VERSION:
            raise ProtocolError(f"unsupported preset version {data.get('version')!r}")
        values = dict(protocol.READ_DEFAULTS)
        for key, entry in data["settings"].items():
            p = protocol.param(key)
            if not p.confirmed:
                continue
            value = entry["value"] if isinstance(entry, dict) else entry
            p.validate(value)
            values[p.id] = value
    except (KeyError, TypeError, AttributeError) as e:
        raise ProtocolError(f"malformed preset: {e!r}") from None
    return SwingSettings(values)


def to_syx(settings):
    return b"".join(protocol.build_write(p.id, settings[p.id]) for p in protocol.EDITABLE)


def from_syx(data):
    """Read a .syx made of write messages. Every editable setting must be present exactly once."""
    values = {}
    for message in _split_sysex(data):
        reply = protocol.parse(message)
        if not isinstance(reply, protocol.Value):
            raise ProtocolError(f"not a Swing setting: {message.hex(' ')}")
        if reply.id in values:
            raise ProtocolError(f"setting {protocol.param(reply.id).key} appears twice")
        p = protocol.param(reply.id)
        if not p.confirmed:
            raise ProtocolError(f"setting {p.key} is not editable")
        p.validate(reply.value)
        values[reply.id] = reply.value
    missing = [p.key for p in protocol.EDITABLE if p.id not in values]
    if missing:
        raise ProtocolError(f"the .syx file lacks {', '.join(missing)}")
    return SwingSettings({**protocol.READ_DEFAULTS, **values})


def _split_sysex(data):
    start = None
    for i, b in enumerate(data):
        if b == 0xF0:
            start = i
        elif b == 0xF7 and start is not None:
            yield bytes(data[start:i + 1])
            start = None
    if start is not None:
        raise ProtocolError("the .syx file ends in the middle of a message")


def save(path, settings):
    """Save as .syx or .json depending on the extension."""
    if os.path.splitext(path)[1].lower() == ".syx":
        content, mode = to_syx(settings), "wb"
    else:
        content, mode = json.dumps(to_dict(settings), indent=2, ensure_ascii=False) + "\n", "w"
    with open(path, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as f:
        f.write(content)


def load(path):
    if os.path.splitext(path)[1].lower() == ".syx":
        with open(path, "rb") as f:
            return from_syx(f.read())
    try:
        with open(path, encoding="utf-8") as f:
            return from_dict(json.load(f))
    except json.JSONDecodeError as e:
        raise ProtocolError(f"not a valid JSON file: {e}") from None
