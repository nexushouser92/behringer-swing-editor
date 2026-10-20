# Swing Editor: plan

A friendly, unofficial settings editor for the Behringer Swing, with the same look and approach as
[Orbit Editor](../../Numark%20Orbit): Python 3 for Windows, CustomTkinter window, MIDI through
`winmm.dll` (no MIDI library), one `.exe` built by GitHub Actions, English/Spanish, MIT license.
Written from scratch from the protocol notes in `PROTOCOL.md`.

## What it does (version 1)

- Finds the Swing automatically and reads all its settings when it is plugged in.
- Shows them grouped in clear sections instead of one long list:

  | Section | Parameters |
  |---|---|
  | MIDI | In channel, Thru, Output channel |
  | Keyboard | Velocity curve, Velocity (as recorded / fixed), Fixed velocity, Aftertouch curve |
  | Pedals | Sustain pedal: function, mode, CC number, low/high values · Hold switch: function, mode |
  | Mod & pitch | Mod MIDI channel and CC, Pitch bend |
  | Clock & tempo | Clock mode, Clock start, Tap tempo count, Tempo knob |
  | Sequencer & arp | Next sequence, Arm to start, Sequencer random, Arpeggiator random |
  | Transposition | Input port, Input channel, Latch, Center pitch |
  | CV / Gate | Gate output, Pitch output, 0 V / 1 V notes, Note priority, Pitch range, Mod source, Mod max voltage |
  | Transport | Mode, Play/Pause, Play/Rec/Stop channels and CCs |
  | Lights | LED brightness |

- Every change is sent right away (debounced 0.3 s) and **verified by reading it back**.
- Shows the sync source and BPM the Swing reports.
- Save / load presets (`.json`) and "restore what was on the Swing when I connected".
- Plain-language help text under each setting.

Version 2: the 8-sequence step editor (needs the step format decoded first).

## Reused from Orbit Editor

| Orbit module | Reuse |
|---|---|
| `midi_win.py` | Almost as is: port search by name ("SWING"), SysEx send/receive, quiet time |
| `link.py` | Same idea: automatic search, read on link, debounced writes |
| `i18n.py`, `render.py`, `gui.py` look | Same window style, colors and fonts |
| `presets.py`, tests with fakes, `build.yml` | Same structure |

New: `protocol.py` (parameter table, message encode/decode, value validation, 8-in-7 unpacking),
`device.py` (read all, write one with read-back), the sections of the window.

## Safety rules

- Allow-list only: product info `00`, reads and writes of the 47 known ids. Never `77`, `74`, `73`
  or firmware data (see PROTOCOL.md).
- Values are validated against each parameter's range before sending.
- A write is only "done" when reading it back returns the same value.

## Phases

| Phase | Content | Needs the Swing |
|---|---|---|
| 0 | Protocol research from the official installer (done: `PROTOCOL.md`) | No |
| 1 | Hardware checks with small scripts in `research/tools`: port name, product info, read all 47 values, one write + read-back + restore (done) · map the "?" options (to do) | **Yes** |
| 2 | `protocol.py`, `device.py`, presets and unit tests with a simulated Swing (done: 62 tests; `device.read_all` also checked on the real Swing) | No |
| 3 | Window with the sections above, automatic link, live writes (done: `gui.py`, `link.py`, `i18n.py`; 97 tests; tried read-only with the real Swing). The 3 unconfirmed settings are read but never shown or written | Yes, to try it |
| 4 | README with screenshot, MIT license, GitHub Actions, first release | No |
| 5 (later) | Sequencer step editor | Yes |
