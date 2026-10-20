# Swing panel controls (from the Quick Start Guide)

Summary in our own words of the "Step 2: Controls" pages of the official Behringer SWING Quick Start
Guide (English and Spanish editions), kept as a reference for the editor and the DAW bridge. The
right-hand column links each control to what we measured over USB (see `MESSAGE_FLOW.md` and
`KEYBOARD_AND_DAW.md`).

## Front panel

| # | Control | What it does | Seen over USB / relevance |
|---|---|---|---|
| 1 | **Keyboard** (32 keys) | Velocity and aftertouch. **With SHIFT held, keys get a second job:** the first 5 set the gate length (10–80 %, keys 1 + 2 together = random gate), the next 11 set the swing (off = 50 % up to 80 %), the last 16 set the **MIDI channel 1–16** | Notes + channel aftertouch (`D0`). Shift + a key **changes the output channel** without any message, so the DAW track stops hearing the keys (`MESSAGE_FLOW.md` #7) |
| 2 | **Pitch bend** strip | Bends up/down, springs back to the center | Pitch bend (`E0`) on setting `15`'s channel |
| 3 | **Modulation** strip | Mod amount; stays where it is left | CC from setting `14` (was CC 127, now CC 1) |
| 4 | **OCT +** | Up one octave per press (max +4); faster blinking = higher. OCT + and OCT − together = back to the center. SHIFT + OCT + while the sequencer plays, then a key = **transpose** the sequence | — |
| 5 | **OCT −** | Down one octave (max −4). SHIFT + OCT − = play the keyboard over a running sequence (KYBD PLAY) | — |
| 6 | **HOLD** | Keeps the arpeggio after the keys are released; more notes can be added while one is still held. SHIFT + HOLD = enter/leave **chord mode**. **Factory reset: hold HOLD and SHIFT while plugging in the USB cable** | Status `06 09/0A` around Hold presses ⏳; Hold mode/function are settings `0E`/`0F` |
| 7 | **SHIFT** | Second function of the controls (gate, MIDI channel, swing on the keys); also makes the rotary knobs jump over intermediate values | No message of its own seen yet ⏳ |
| 8 | **ARP / SEQ** | Chooses arpeggiator or sequencer mode | Status `06 19/1A` = Arp pressed/released |
| — | **Sync source** | Hold **ARP for 3–4 s**, then press **REC = internal**, **STOP = MIDI**, **PLAY = USB**, **TAP = external trigger** (sync input). Without any external source the Swing runs on its internal clock | `06 1D` = INT, `06 1E` = MIDI, `06 1F` = USB (TAP not measured yet ⏳). Not a stored setting; Arp + REC leaks a Rec CC to the DAW (bridge filters it) |
| — | **Ratchet** | While recording, hold **SEQ for 3–4 s** on a step, then REC = none, STOP = 2, PLAY = 3, TAP = 4 repeats | Sequencer data, phase 5 |
| 9 | **REC** (INT) | Starts recording while programming the sequencer; also enters a rest or a tie | CC 50 (setting `65`) = 127 on release + MMC Record Strobe/Exit |
| 10 | **STOP** (MIDI) | Stops the arpeggiator/sequencer. The sequence is stored in slot A–H chosen with STYLE/PATTERN. SHIFT + STOP = append notes to the sequence | CC 51 (setting `64`) + MMC Stop + **CC 123 All Notes Off on channel 1** |
| 11 | **PAUSE / PLAY** (USB) | Starts the arpeggiator (light on, TAP blinks at the tempo); press again to pause (blinking). SHIFT + PLAY while playing = back to the start | CC 54 (setting `66`) + MMC Play; setting `67` chooses Pause or Reset |
| 12 | **TAP** | Tap the tempo several times; turning TEMPO afterwards goes back to the knob's value. SHIFT + TAP = **erase the last step** (short press) or **erase everything** (hold 4 s) | Setting `22` = how many taps are averaged. Shift + Tap is destructive: keep it in mind for the bridge |
| 13 | **TEMPO** knob | Arpeggiator/sequencer tempo; SHIFT for fine steps; TAP blinks at the tempo | **Sends nothing over USB** (measured); disabled while following an external clock |
| 14 | **SCALE** knob | 8 note values: 1/4, 1/4T, 1/8, 1/8T, 1/16, 1/16T, 1/32, 1/32T | Not reported over USB ⏳ |
| 15 | **STYLE / PATTERN** knob | 8 stored programs (sequencer) or 8 playing orders (arpeggiator) | Not reported over USB ⏳ |

## Rear panel

| # | Connector | Notes |
|---|---|---|
| 16 | USB | MIDI with a DAW or Control Tribe; also powers the Swing |
| 17 | DC in | Optional power supply when no computer is used |
| 18 | CV outputs | Modulation, gate and pitch for modular gear (settings `46`–`4F`) |
| 19 | Footswitch | Hold, sustain or both (settings `09`–`10`) |
| 20 | Sync in/out | External sync devices (setting `20` = clock input type, `23` = start) |
| 21 | MIDI in/out | DIN connections (settings `07`, `08`) |
| 22 | Lock | Security cable |

## What this adds to our findings

- **Shift + keys silently changes the MIDI channel, gate and swing.** That fits the "dead keyboard"
  in test 2 better than a hardware fault: the keys may have been sending on another channel, or Shift
  was being held. The editor shows the output channel (setting `16`), so a quick look there tells.
- **Factory reset** (HOLD + SHIFT at power-up) explains the "frequent factory resets" users mention;
  after one, the editor's values change back to the defaults (our `READ_DEFAULTS` are a good guess).
- **Sync source** is chosen by holding ARP 3–4 s; the fourth choice, TAP = external trigger, is still
  to be measured (likely status `06 20`).
- **Destructive combinations to keep away from in a DAW session:** SHIFT + TAP (erase step / all),
  SHIFT + STOP (append), SHIFT + PLAY (jump to start). The bridge could warn about them later using the
  button status events.
