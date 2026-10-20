"""Read-only: save the Swing's 47 settings as a numbered snapshot and show what changed since the
previous one. Used to map each option of the official editor to its raw value.

Usage: python research/tools/snapshot.py [note]
Snapshots go to research/snapshots/NN.json. Close Control Tribe first: the MIDI port is exclusive.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from swing_editor import device, midi_win, protocol  # noqa: E402

FOLDER = os.path.join(ROOT, "research", "snapshots")


def read_raw(port):
    """Like device.read_all, but keeps values this app does not know yet."""
    port.drain()
    return {p.id: device.read_param(port, p.id) for p in protocol.PARAMS}


def main():
    os.makedirs(FOLDER, exist_ok=True)
    previous = sorted(glob.glob(os.path.join(FOLDER, "*.json")))
    with midi_win.open_swing() as port:
        values = read_raw(port)
    number = len(previous) + 1
    path = os.path.join(FOLDER, f"{number:02d}.json")
    note = " ".join(sys.argv[1:])
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"note": note, "values": {f"{k:02X}": v for k, v in values.items()}}, f, indent=1)
    print(f"snapshot {number:02d} saved ({note or 'no note'})")
    if not previous:
        return
    with open(previous[-1], encoding="utf-8") as f:
        before = {int(k, 16): v for k, v in json.load(f)["values"].items()}
    changed = [p for p in protocol.PARAMS if before[p.id] != values[p.id]]
    print(f"{len(changed)} changed since snapshot {len(previous):02d}:")
    for p in changed:
        print(f"  {p.id:02X} {p.label:<30} {before[p.id]:>3} -> {values[p.id]:>3}"
              f"   (current table: {p.label_of(before[p.id])} -> {p.label_of(values[p.id])})")


if __name__ == "__main__":
    main()
