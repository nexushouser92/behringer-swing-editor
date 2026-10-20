"""Phase 1, read only: ask the Swing for its product info and read all 47 known settings.

Sends only command 00 (product info) and reads of the known ids (no value byte), never a write.
Every message received is logged in hex. Usage: python research/tools/read_swing.py [log.txt]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from swing_editor.midi_win import open_swing  # noqa: E402

HEADER = bytes([0xF0, 0x00, 0x20, 0x32, 0x7F, 0x42])
PARAMS = {
    0x07: "MIDI In channel", 0x08: "MIDI Thru", 0x09: "Sustain pedal mode", 0x0A: "Sustain pedal user",
    0x0B: "Sustain CC low", 0x0C: "Sustain CC high", 0x0D: "Sustain CC number", 0x0E: "Hold switch mode",
    0x0F: "Hold switch function", 0x10: "Sustain pedal function", 0x13: "Mod MIDI channel",
    0x14: "Mod CC number", 0x15: "Pitch bend", 0x16: "Output channel", 0x19: "Velocity curve",
    0x1A: "Aftertouch curve", 0x20: "Clock mode", 0x21: "Transposition input channel",
    0x22: "Tap tempo count", 0x23: "Clock start", 0x24: "Next sequence", 0x25: "Arm to start",
    0x26: "Transposition latch", 0x27: "Transposition input port", 0x28: "Tempo knob (Rate)",
    0x29: "Velocity", 0x2A: "Fixed velocity", 0x2B: "Transposition center pitch",
    0x2C: "Sequencer random", 0x2D: "Arpeggiator random", 0x46: "Gate output", 0x47: "Pitch output",
    0x4A: "1 V MIDI note", 0x4C: "0 V MIDI note", 0x4D: "Note priority", 0x4E: "Mod CV source",
    0x4F: "Mod CV max voltage", 0x50: "Pitch CV range", 0x57: "LED brightness", 0x60: "Transport mode",
    0x61: "Stop MIDI channel", 0x62: "Rec MIDI channel", 0x63: "Play MIDI channel", 0x64: "Stop CC",
    0x65: "Rec CC", 0x66: "Play CC", 0x67: "Play/Pause",
}
REPLY_WAIT = 0.6

log_lines = []


def log(text):
    print(text)
    log_lines.append(text)


def is_swing(msg):
    return len(msg) >= 7 and msg[1:4] == b"\x00\x20\x32" and msg[5] == 0x42


def ask(port, command, label):
    """Send HEADER + command + F7 and return the first Swing reply with that command, logging everything."""
    out = HEADER + bytes([command, 0xF7])
    port.send(out)
    log(f"-> {label:<28} {out.hex(' ')}")
    deadline = time.monotonic() + REPLY_WAIT
    found = None
    while time.monotonic() < deadline:
        msg = port.receive(max(0.0, deadline - time.monotonic()))
        if msg is None:
            break
        log(f"<- {'':<28} {msg.hex(' ')}")
        if found is None and is_swing(msg) and msg[6] == command:
            found = msg
            break
    return found


def main():
    with open_swing() as port:
        port.drain()
        log("== Product info ==")
        reply = ask(port, 0x00, "product info")
        if reply is not None and len(reply) == 14:
            a, b = reply[7:10], reply[10:13]
            log(f"   groups: {a[0]}.{a[1]}.{a[2]}  and  {b[0]}.{b[1]}.{b[2]}")
        log("")
        log("== Settings ==")
        values = {}
        for pid, name in PARAMS.items():
            reply = ask(port, pid, f"{pid:02X} {name}")
            if reply is not None and len(reply) == 9:
                values[pid] = reply[7]
        log("")
        log("== Summary ==")
        for pid, name in PARAMS.items():
            v = values.get(pid)
            log(f"{pid:02X}  {name:<28} {'no reply' if v is None else v}")
        log(f"{len(values)} of {len(PARAMS)} parameters answered")
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
