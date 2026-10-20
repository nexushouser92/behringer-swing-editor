"""Phase 1, first write: LED brightness (0x57). Reads it, writes 64, listens for an echo, reads it back,
then restores the original value and checks it. Sends nothing else.

Usage: python research/tools/write_test.py [log.txt]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from swing_editor.midi_win import open_swing  # noqa: E402

HEADER = bytes([0xF0, 0x00, 0x20, 0x32, 0x7F, 0x42])
PARAM = 0x57
TEST_VALUE = 64
LISTEN = 0.6

log_lines = []


def log(text):
    print(text)
    log_lines.append(text)


def listen(port, seconds):
    """Log and return every message received within seconds."""
    got = []
    deadline = time.monotonic() + seconds
    while True:
        msg = port.receive(max(0.0, deadline - time.monotonic()))
        if msg is None:
            return got
        log(f"<- {msg.hex(' ')}")
        got.append(msg)


def value_from(messages):
    for m in messages:
        if len(m) == 9 and m[1:4] == b"\x00\x20\x32" and m[5] == 0x42 and m[6] == PARAM:
            return m[7]
    return None


def send(port, data, label):
    port.send(data)
    log(f"-> {data.hex(' ')}   ({label})")


def read(port):
    send(port, HEADER + bytes([PARAM, 0xF7]), "read")
    return value_from(listen(port, LISTEN))


def write(port, value):
    send(port, HEADER + bytes([PARAM, value, 0xF7]), f"write {value}")
    echo = listen(port, LISTEN)
    log(f"   echo after write: {'yes, value ' + str(value_from(echo)) if value_from(echo) is not None else 'none'}")


def main():
    with open_swing() as port:
        port.drain()
        original = read(port)
        log(f"   original value: {original}")
        if original is None:
            log("ABORTED: no reply to the read, nothing was written")
            return
        write(port, TEST_VALUE)
        now = read(port)
        log(f"   read back: {now}  ({'OK' if now == TEST_VALUE else 'MISMATCH'})")
        time.sleep(2)  # leave time to see the LEDs dimmed
        write(port, original)
        restored = read(port)
        log(f"   restored: {restored}  ({'OK' if restored == original else 'MISMATCH'})")
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
