"""Read only: listen to everything the Swing plays for a while and report problems.

Finds stuck notes (note on without note off), notes pressed twice without release, the velocity
range of each key, sustain (CC 64) left on, other CCs (transport), MMC, clock and active sensing.
Sends nothing to the Swing, except with clock_from: from that second on it acts like a DAW in play,
sending MIDI Start and clock (24 pulses per beat) at BPM, and Stop at the end. No settings change.
Close any DAW and Control Tribe first: the MIDI port is exclusive.

Usage: python research/tools/key_test.py [seconds] [log.txt] [clock_from] [bpm]
"""
import collections
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from swing_editor import midi_win, protocol  # noqa: E402

REALTIME = {0xF8: "clock", 0xFA: "start", 0xFB: "continue", 0xFC: "stop", 0xFE: "active sensing"}


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    events = []
    lock = threading.Lock()

    def on_short(status, d1, d2):
        with lock:
            events.append((time.monotonic(), status, d1, d2))

    clock_from = float(sys.argv[3]) if len(sys.argv) > 3 else None
    bpm = float(sys.argv[4]) if len(sys.argv) > 4 else 120.0
    stop_clock = threading.Event()

    def run_clock(port, at):
        """Act like a DAW in play: Start, then 24 clock pulses per beat until stopped, then Stop."""
        while time.monotonic() < at:
            if stop_clock.wait(0.01):
                return
        port.send_short(0xFA)
        with lock:
            events.append((time.monotonic(), "sent", "MIDI Start + clock", None))
        tick, next_tick = 60.0 / bpm / 24, time.perf_counter()
        while not stop_clock.is_set():
            port.send_short(0xF8)
            next_tick += tick
            delay = next_tick - time.perf_counter()
            if delay > 0.002:
                time.sleep(delay - 0.002)
            while time.perf_counter() < next_tick:
                pass
        port.send_short(0xFC)

    with midi_win.open_swing() as port:
        port.on_short = on_short
        start = time.monotonic()
        clock = None
        if clock_from is not None:
            clock = threading.Thread(target=run_clock, args=(port, start + clock_from), daemon=True)
            clock.start()
        print(f"Listening for {seconds:.0f} s"
              + (f"; simulated DAW clock at {bpm:.0f} BPM from {clock_from:.0f} s" if clock else ""), flush=True)
        sysex = []
        while time.monotonic() - start < seconds:
            msg = port.receive(0.2)
            if msg is not None:
                sysex.append(msg)
                with lock:
                    events.append((time.monotonic(), "sysex", msg, None))
        stop_clock.set()
        if clock:
            clock.join(2)
        port.on_short = None

    with lock:
        events = list(events)
    lines = []
    out = lines.append
    held = {}                                   # (channel, note) -> time pressed
    released_by_all_off = set()                 # notes the Swing only released with CC 123 / 120
    stats = collections.defaultdict(list)       # note -> velocities
    doubles, quick = [], []
    ccs = collections.Counter()
    cc_last = {}
    realtime = collections.Counter()
    other = collections.Counter()
    timeline = sorted(events, key=lambda e: e[0])
    events = [e for e in timeline if not isinstance(e[1], str)]
    for t, status, d1, d2 in events:
        kind, ch = status & 0xF0, status & 0x0F
        if status in REALTIME:
            realtime[REALTIME[status]] += 1
        elif kind == 0x90 and d2 > 0:
            if (ch, d1) in held:
                doubles.append((ch, d1))
            held[(ch, d1)] = t
            stats[d1].append(d2)
        elif kind == 0x80 or (kind == 0x90 and d2 == 0):
            pressed = held.pop((ch, d1), None)
            if pressed is not None and t - pressed < 0.01:
                quick.append((ch, d1))
        elif kind == 0xB0:
            ccs[(ch, d1)] += 1
            cc_last[(ch, d1)] = d2
            if d1 in (120, 123):   # All Sound Off / All Notes Off: releases everything on the channel
                for key in [k for k in held if k[0] == ch]:
                    released_by_all_off.add(key[1])
                    del held[key]
        else:
            other[f"{status:02X}"] += 1

    out(f"{len(events)} short messages, {len(sysex)} SysEx in {seconds:.0f} s")
    out("")
    out(f"Keys played: {len(stats)}")
    if stats:
        notes = sorted(stats)
        out(f"  range {protocol.note_name(notes[0])} .. {protocol.note_name(notes[-1])}")
        span = range(notes[0], notes[-1] + 1)
        missing = [protocol.note_name(n) for n in span if n not in stats]
        out(f"  notes inside that range never received: {', '.join(missing) if missing else 'none'}")
        out("  key    times  velocity min/avg/max")
        for n in notes:
            v = stats[n]
            flag = "   <- always very soft" if max(v) < 40 else ""
            out(f"  {protocol.note_name(n):<5} {len(v):>5}   {min(v):>3} / {sum(v) // len(v):>3} / {max(v):>3}{flag}")
    out("")
    out(f"STUCK at the end (note on, never released): "
        f"{', '.join(f'{protocol.note_name(n)} (ch {c + 1})' for c, n in held) if held else 'none'}")
    out(f"Released only by an All Notes Off (CC 123), with no note off of their own: "
        f"{', '.join(protocol.note_name(n) for n in sorted(released_by_all_off)) if released_by_all_off else 'none'}")
    out(f"Pressed again without being released: "
        f"{', '.join(sorted({protocol.note_name(n) for _, n in doubles})) if doubles else 'none'}")
    out(f"Released less than 10 ms after pressing (contact bounce?): "
        f"{', '.join(sorted({protocol.note_name(n) for _, n in quick})) if quick else 'none'}")
    out("")
    out("Controllers:")
    for (ch, cc), count in sorted(ccs.items()):
        name = {64: "sustain", 1: "mod", 54: "transport play?", 51: "transport stop?", 50: "transport rec?"}.get(cc, "")
        warn = "   <- LEFT ON at the end" if cc == 64 and cc_last[(ch, cc)] >= 64 else ""
        out(f"  ch {ch + 1:>2} CC {cc:>3} {name:<16} {count:>4} messages, last value {cc_last[(ch, cc)]}{warn}")
    if not ccs:
        out("  none")
    out(f"Real-time: {dict(realtime) if realtime else 'none'}")
    out(f"Other channel messages (status byte): {dict(other) if other else 'none'}")
    mmc = [m for m in sysex if m[:4] == bytes([0xF0, 0x7F, 0x7F, 0x06]) or m[1:2] == b"\x7f"]
    out(f"MMC messages: {len(mmc)} {[m.hex(' ') for m in mmc[:4]]}")
    swing_status = [m for m in sysex if protocol.is_swing_message(m)]
    out(f"Swing status SysEx: {len(swing_status)}")

    out("")
    out("Timeline (seconds from start, channel aftertouch left out):")
    for t, status, d1, d2 in timeline:
        if status == "sent":
            out(f"  {t - start:7.3f}  >>> sent to the Swing: {d1}")
            continue
        if status == "sysex":
            reply = protocol.parse(d1)
            detail = f"Swing status {reply.data.hex(' ')}" if isinstance(reply, protocol.Status) else d1.hex(" ")
            out(f"  {t - start:7.3f}  SysEx  {detail}")
            continue
        kind, ch = status & 0xF0, status & 0x0F
        if status in REALTIME or kind == 0xD0:
            continue
        if kind == 0x90 and d2 > 0:
            what = f"note on  {protocol.note_name(d1)} vel {d2}"
        elif kind in (0x80, 0x90):
            what = f"note off {protocol.note_name(d1)}"
        elif kind == 0xB0:
            what = f"CC {d1} = {d2}"
        else:
            what = f"{status:02X} {d1} {d2}"
        out(f"  {t - start:7.3f}  ch {ch + 1:>2}  {what}")

    report = "\n".join(lines)
    print(report)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(report + "\n")


if __name__ == "__main__":
    main()
