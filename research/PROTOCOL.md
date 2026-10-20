# Behringer Swing SysEx protocol: research notes

Unofficial project, not affiliated with Behringer or Music Tribe. These notes describe the message
format **in our own words**, worked out for interoperability. No code or assets from the original
editor are copied into this project.

## Sources

| Source | What it gave us |
|---|---|
| The official editor's installer `ControlTribeSetup-1.4.1.exe` (NSIS), unpacked **without running it** with 7-Zip | It contains `ControlTribe.exe` (64-bit, built with JUCE). The app supports only the Swing. |
| Static analysis of `ControlTribe.exe` (strings and Ghidra decompilation of the Swing classes `SwingDeviceImpV010100`, `SwingDeviceSettingsV010100` and `SwingSyncThreadV010100`) | Message layout, every settings parameter id with its label, the read/write pattern and the dangerous commands. |
| A real Swing (firmware 1.1.52) connected by USB | Points marked ✅ were checked on it (2026-10-20, read only: `tools/read_swing.py`, log in `read_all.log`). Points marked ⏳ are still to check. |

## MIDI port

✅ The port is called **`Behringer Swing`** (input and output). Automatic detection looks for "SWING".

## Common header

```
F0 00 20 32 <dev> 42 <command> [data...] F7
   └──────┘ └───┘ └┘
   Behringer device Swing (model id 0x42)
```

- `00 20 32` is Behringer's MIDI manufacturer id.
- `<dev>`: the editor always **sends** `7F` (all devices) and **accepts any** value in replies. ✅ The Swing also replies with `7F`.
- `42` identifies the Swing.

## Messages

### Product information

| Direction | Bytes | Meaning |
|---|---|---|
| PC → Swing | `F0 00 20 32 7F 42 00 F7` | Request product info ✅ |
| Swing → PC | `F0 00 20 32 <dev> 42 00 a1 a2 a3 b1 b2 b3 F7` (12 data bytes) | Two 3-byte versions ✅. Our Swing answers `01 00 00 01 01 34` = **1.0.0** and **1.1.52**; 1.1.52 is most likely the firmware and 1.0.0 the bootloader ⏳ |

### Settings (global parameters)

| Direction | Bytes | Meaning |
|---|---|---|
| PC → Swing | `F0 00 20 32 7F 42 <param> F7` | **Read** one parameter ✅ |
| Swing → PC | `F0 00 20 32 <dev> 42 <param> <value> F7` | Current value ✅ (all 47 answer, in well under 100 ms) |
| PC → Swing | `F0 00 20 32 7F 42 <param> <value> F7` | **Write** one parameter ✅ |
| Swing → PC | `F0 00 20 32 7F 42 <param> F7` | **Acknowledge** of the write (no value byte) ✅ |

- One message per parameter: there is no full dump. The editor reads all of them one by one when it
  connects ("Settings" step of its sync), waiting about 100 ms between messages.
- Replies to a read have the same shape as a write. The editor treats any 7-byte reply whose command
  is between `0x07` and `0x67` as a parameter value.
- ✅ A write is acknowledged right away with the header and the parameter id but **no value** (same
  bytes as a read request). The new value is applied at once: reading it back returns it
  (`write_test.log`: LED brightness 127 → 64 → read 64 → 127 → read 127).
- ✅ Written values are saved in the Swing's memory right away: they survive unplugging it
  (checked 2026-10-20 with five settings, see `KEYBOARD_AND_DAW.md`).

#### Parameter table

✅ = value meanings checked on a real Swing: options changed in Control Tribe, then read with
`tools/snapshot.py` (`snapshots/01–03`, with screenshots of Control Tribe), and the Swing restored to
snapshot 01 afterwards. Generated from `swing_editor/protocol.py`.

| Id | Setting | Raw values | |
|---|---|---|---|
| `07` | MIDI In channel | 0–15 = channels 1–16, 65 = User | ✅ |
| `08` | MIDI Thru | 0 = Off, 1 = On | ✅ |
| `09` | Sustain pedal mode | 0 = Gate, 1 = Toggle | ✅ |
| `0A` | Sustain message channel | 0–15 = channels 1–16, 65 = User | ✅ |
| `0B` | Sustain CC value (released) | 0–127 | ✅ |
| `0C` | Sustain CC value (pressed) | 0–127 | ✅ |
| `0D` | Sustain CC number | 0–127 | ✅ |
| `0E` | Hold switch mode | 0 = Gate, 1 = Toggle | ✅ |
| `0F` | Hold switch function | 1 = Hold keys, 2 = Sustain message, 3 = Both | ✅ |
| `10` | Sustain pedal function | 1 = Hold keys, 2 = Sustain message, 3 = Both | ✅ |
| `13` | Mod MIDI channel | 0–15 = channels 1–16, 65 = User | ✅ |
| `14` | Mod CC number | 0–127 | ✅ |
| `15` | Pitch bend MIDI channel | 0–15 = channels 1–16, 65 = User | ✅ |
| `16` | Output channel | 0–15 = channels 1–16 | ✅ |
| `19` | Velocity curve | 0 = Linear, 1 = Logarithmic, 2 = Anti-logarithmic | ✅ |
| `1A` | Aftertouch curve | 0 = Linear, 1 = Logarithmic, 2 = Anti-logarithmic | ⏳ |
| `20` | Clock input | 0 = 1 step (gate), 1 = 1 step (clock), 2 = 1 pulse (Korg), 3 = 24 ppq, 4 = 48 ppq | ✅ |
| `21` | Transposition channel | 0–15 = channels 1–16, 65 = All, 126 = None | ✅ |
| `22` | Tap tempo | 0 = 2 taps, 1 = 3 taps, 2 = 4 taps | ✅ |
| `23` | Clock start | 0 = On clock, 1 = On gate start | ✅ |
| `24` | Next sequence | 0 = At the end, 1 = Instant reset, 2 = Instant continue | ✅ |
| `25` | Arm to start | 0 = Off, 1 = On | ✅ |
| `26` | Transposition latch | 0 = On, 1 = Off | ✅ |
| `27` | Transposition input | 0 = USB, 1 = MIDI, 2 = USB and MIDI | ✅ |
| `28` | Tempo knob | 0 = Jump, 1 = Pickup | ⏳ |
| `29` | Velocity | 0 = As played, 1 = Fixed | ✅ |
| `2A` | Fixed velocity | 0–127 | ✅ |
| `2B` | Transposition center note | MIDI note 0–127 (60 = C3) | ✅ |
| `2C` | Tie mode | 0 = Tie to previous, 1 = Tie to next | ✅ |
| `2D` | Arpeggiator random mode | 0 = Total, 1 = Pattern, 2 = Brownian | ⏳ |
| `46` | Pitch CV mode | 0 = Volts per octave, 1 = Hertz per volt | ✅ |
| `47` | Gate output level | 0 = S-trig, 1 = V-trig 5 V, 2 = V-trig 12 V | ✅ |
| `4A` | Note at 1 V | MIDI note 0–127 (60 = C3) | ✅ |
| `4C` | Note at 0 V | MIDI note 0–127 (60 = C3) | ✅ |
| `4D` | Note priority | 0 = Low, 1 = High, 2 = Last | ✅ |
| `4E` | Mod output source | 0 = Mod strip, 1 = Velocity, 2 = Aftertouch | ✅ |
| `4F` | Mod output max voltage | 5 = 5 V, 6 = 6 V, 7 = 7 V, 8 = 8 V, 9 = 9 V, 10 = 10 V, 11 = 11 V, 12 = 12 V | ✅ |
| `50` | Pitch range | 0–127 | ✅ |
| `57` | LED brightness | 0–127 | ✅ |
| `60` | Transport messages | 0 = Off, 1 = MIDI CC, 2 = MMC, 3 = Both | ✅ |
| `61` | Stop MIDI channel | 0–15 = channels 1–16 | ✅ |
| `62` | Rec MIDI channel | 0–15 = channels 1–16 | ✅ |
| `63` | Play MIDI channel | 0–15 = channels 1–16 | ✅ |
| `64` | Stop CC number | 0–127 | ✅ |
| `65` | Rec CC number | 0–127 | ✅ |
| `66` | Play CC number | 0–127 | ✅ |
| `67` | Play/Pause button | 0 = Pause, 1 = Reset | ✅ |

Corrections found on the hardware compared with the first reading of the editor's code:

- `2C` is the **Tie mode** (the code labels it "Sequencer random mode").
- `46` is the **pitch CV mode** and `47` the **gate output level** (the code labels both "Gate Output").
- Sustain and hold-switch **functions start at 1** (1 = Hold keys, 2 = Sustain message, 3 = Both).
- **Latch: 0 = On**, 1 = Off.
- MIDI In channel offers 1–16 and **User** (65), no All/None.
- The velocity curve has 3 options (no Soft).
- ⏳ `28`: changing Control Tribe's *Tempo → Mode* to Pickup did **not** change `28`, so the tempo
  mode is somewhere else and `28` is still unknown.
- ⏳ `2D` (arpeggiator random mode) is not shown by Control Tribe.
- ⏳ `1A`: whether the aftertouch curve has a 4th option (Soft).

#### Values read from our Swing (2026-10-20)

Full log: `read_all.log`. Unchanged settings, so most likely the factory defaults ⏳.

| Id | Value | | Id | Value | | Id | Value |
|---|---|---|---|---|---|---|---|
| `07` | 0 | | `16` | 0 | | `2C` | 1 |
| `08` | 0 | | `19` | 1 | | `2D` | 0 |
| `09` | 0 | | `1A` | 0 | | `46` | 0 |
| `0A` | 65 | | `20` | 2 | | `47` | 1 |
| `0B` | 0 | | `21` | 65 | | `4A` | 0 |
| `0C` | 127 | | `22` | 2 | | `4C` | 0 |
| `0D` | 64 | | `23` | 0 | | `4D` | 1 |
| `0E` | 1 | | `24` | 0 | | `4E` | 0 |
| `0F` | 1 | | `25` | 0 | | `4F` | 12 |
| `10` | 2 | | `26` | 0 | | `50` | 24 |
| `13` | 0 | | `27` | 0 | | `57` | 127 |
| `14` | 127 | | `28` | 0 | | `60` | 3 |
| `15` | 0 | | `29` | 0 | | `61`/`62`/`63` | 0 / 0 / 0 |
|  |  | | `2A` | 127 | | `64`/`65`/`66` | 51 / 50 / 54 |
|  |  | | `2B` | 60 | | `67` | 0 |

What the values tell us:

- **Channels** are sent as 0–15 for channels 1–16, plus special values. The editor contains the value
  lists `0…15,65` (shown as `1…16,User`) and `0…15,65,126` (shown as `1…16,All,None`), so
  **65 = User / All** and **126 = None**. That matches `0A` = 65 and `21` = 65 (transposition from
  all channels).
- **Notes** are MIDI note numbers: `2B` = 60 is C3 in the editor's naming (C-2 = 0).
- **Mod CV max voltage** `4F` = 12 is the voltage itself (list `5…12`).
- `10` = 2 is "Sustain message" (functions start at 1), `60` = 3 is "Both" (MIDI CC + MMC), `4D` = 1
  is "High" (low, high, last), `19` = 1 is "Logarithmic": all confirmed in the parameter table above.
- Transport CCs 51/50/54 (stop/rec/play) and sustain CC 64 are the usual defaults.

### Status (sent by the Swing)

`F0 00 20 32 <dev> 42 70 <packed data> F7`: the data after `70` is packed 8-in-7 (every 8th byte
carries the high bits of the next 7). First decoded byte:

- `00`: sync source, second byte 1 = Internal, 2 and 3 = (two more sources), 4 = Sync in.
- `04`: tempo, followed by a 32-bit float BPM.
- ✅ The Swing sends these by itself: during the read it sent `F0 00 20 32 7F 42 70 00 01 05 F7`
  (decoded `01 05`, a status type the editor ignores). A reader must skip unsolicited `70` messages
  while waiting for a reply.

### Sequencer (8 sequences) — phase 2

| Command | Direction | Data | Meaning |
|---|---|---|---|
| `6F` | PC → Swing | `<seq>` | Request sequence info |
| `6F` | Swing → PC | `<seq> <length> <x> <y>` | Sequence info (length plus two of gate/swing ⏳) |
| `6F` | PC → Swing | `<seq> <length> <x> <y>` | Write sequence info |
| `6B` / `6C` / `6D` | Swing → PC | `<seq> <value>` | One sequence field changed on the Swing |
| `71` | PC → Swing | `<seq> <step>` | Request one step |
| `71` | PC → Swing | `<seq> <step>` + 24 bytes | Write one step |
| `71` | Swing → PC | `<seq> <step> ...` | Step data |
| `68`, `6A` | Swing → PC | | Live note/step updates |
| `73` | PC → Swing | `<seq> 00` | **Clear a sequence** (destructive) |

The step format (24 bytes: notes, velocity, tie mode Legato/Standard/Tie start/Tie continue/Tie end…)
still has to be decoded.

## Commands the app must never send

| Command | Why |
|---|---|
| `77` | **Puts the Swing in bootloader mode** (firmware update). |
| `74` | Bootloader status query, part of the firmware update flow. The editor also sends it at the start of a sync, but we do not need it. |
| Firmware data | The editor can download and flash firmware. Out of scope. |
| `73` | Clears a sequence. Only allowed later, behind an explicit confirmation. |

Rule for the app: an **allow-list**. It only sends `00` (product info), reads of the 47 known ids,
and writes of those ids with a value inside the known range.

## To confirm on a real Swing (phase 1)

1. ✅ Port name.
2. ✅ Product info reply.
3. ✅ Read all 47 parameters (compare with the Swing's own menus: still to do).
4. ✅ Write one harmless parameter (LED brightness `57`), read it back, restore it.
5. ✅ Does a write produce an echo? An acknowledge without value.
5b. ✅ Does a written value survive unplugging the Swing? Yes.
6. For each "?" in the table: change it on the Swing (or in Control Tribe) and read it back to map
   values to options.
