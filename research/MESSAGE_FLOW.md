# Swing ↔ DAW message flow: loops and bugs

Review of what the Swing sends and receives over USB, from the four recordings in this folder
(`key_test_1.log` … `key_test_4_clock.log`, firmware 1.1.52). For each crossing: what happens,
the risk, and what to do.

## What the Swing sends

| Source | Messages | Notes |
|---|---|---|
| Keys | Note on / note off, channel aftertouch | Always a proper note off, also after Hold (test 3) |
| Mod strip | CC (setting `14`) | Was CC 127, a reserved channel-mode message; now CC 1 |
| Play | CC 54 (127, 0) on the transport channel + MMC Play `F0 7F 7F 06 02 F7` | |
| Stop | CC 51 (127, 0) + MMC Stop `06 01` + **CC 123 All Notes Off on channel 1** | CC 123 stays on channel 1 even with the transport on 16 |
| Rec | CC 50 = 127 on release (no 0) + MMC Record Strobe `06 06` / Exit `06 07` | Each press toggles; maps to a DAW record button |
| Clock in → out | **Every clock / Start it receives is sent back out** | 1446 clocks came back in test 4 |
| Status (SysEx `F0 00 20 32 7F 42 70 …`) | `01 05` about every 0.5 s when idle; `04` + BPM every 0.5 s with external clock; `06 n` on every button press/release; `03 x` on mode changes | Ableton ignores SysEx |

## Crossings that can cause loops or stuck notes

| # | Crossing | What can go wrong | Risk | What to do |
|---|---|---|---|---|
| 1 | DAW sends clock to the Swing **and** syncs to the Swing's input | The Swing echoes the clock back: the DAW follows its own clock with a delay → tempo drift, jumps, start/stop loops | **High** | In the DAW, Sync **only on the Swing's output**. Never on its input at the same time |
| 2 | Transport mode "Both" (CC + MMC) in a DAW that answers MMC (Cubase, Reaper…) and also has the CC mapped | One button press acts twice: Play then Play again = pause, record toggled on and off | **High** for those DAWs | DAW mode uses **"MIDI CC" only**; map the CCs in the DAW |
| 3 | Mod strip on CC 127 ("Poly mode on") | Synths/plugins may stop all notes or change mode while the strip moves | High (fixed) | Mod strip on CC 1 |
| 4 | Transport CCs on the notes' channel | Play/Stop/Rec change parameters of the armed instrument | Medium (fixed) | Transport on channel 16 |
| 5 | Hold (Toggle, *Hold keys*) and the DAW stops | The Swing keeps the notes and sends their note off when Hold is released, so nothing stays stuck in the DAW. Stop also sends All Notes Off | Low | Keep *Hold keys*. With *Sustain message* instead, Hold becomes CC 64 and Ableton can keep it on after Stop (a known Ableton behaviour) |
| 6 | MIDI Thru on + the DAW sends notes back to the Swing | Notes leave through the MIDI jack too: doubled or stuck notes on hardware synths | Medium | MIDI Thru off (DAW mode) |
| 7 | **Shift active by mistake** | With Shift, keys choose the MIDI channel, swing, gate and random values instead of playing, and Stop becomes Append. The keyboard seems dead, or the notes move to another channel the DAW track is not listening to | **Probable cause of test 2** (no notes and no Stop for 55 s while the mod strip still worked). The Quick Start Guide confirms Shift + the last 16 keys sets the MIDI channel (`PANEL_CONTROLS.md`) | Press Shift once; check the output channel in the editor. Next time it happens, record it with `key_test.py`: the `06 n` button events will show which button is latched |
| 8 | External clock stops mid-arpeggio | The arp stops with a proper note off (test 4) | Low | — |
| 9 | Status SysEx every 0.5 s | A DAW that records SysEx would fill clips with them | Low (Ableton ignores them) | — |
| 11 | **Arp + Rec to choose the INT clock while a DAW is open** | Releasing Rec after Arp + Rec still sends **CC 50 = 127 and an MMC Record message**, so the DAW starts or stops recording when you only wanted to change the clock source (`sync_test.log`). Arp + Play also sends Play's release (CC 54 = 0); Arp + Stop sends nothing | **High** while recording | Choose the clock source before arming the DAW, or press Arp + Stop/Play instead of Arp + Rec while recording |
| 10 | Exclusive USB port on Windows | DAW, Control Tribe and the editor cannot share the Swing | Medium | Close the editor before opening the DAW; the editor says when the port is busy |

## Not possible from outside the Swing

- **Setting or locking the clock source (INT / MIDI / USB).** Checked in `sync_test.log`: choosing
  INT, MIDI and USB on the panel changed **none** of the 47 settings (snapshots 04 and 05); the Swing
  only reports the button combination as a status event (`06 1D` = Arp + Rec/INT, `06 1E` =
  Arp + Stop/MIDI, `06 1F` = Arp + Play/USB; `06 19`/`06 1A` = Arp pressed/released). The guide adds
  a fourth choice, Arp (held 3–4 s) + TAP = external trigger, not measured yet. No known message
  sets the source, and trying unknown commands is unsafe (`77` puts the Swing in bootloader mode).
- **Giving the tempo knob a CC**: it sends nothing over USB.

## The DAW bridge (`swing_editor/bridge.py`, `bridge_io.py`)

With the bridge on, the editor keeps the Swing's port and the DAW talks to two loopMIDI ports
instead: it listens to **Swing to DAW** and sends its clock to **DAW to Swing**. This also removes
crossing 10 (exclusive port): the editor and the DAW can be open together.

| Crossing | What the bridge does |
|---|---|
| 1 Clock echo | Real-time messages from the Swing never reach the DAW |
| 9 Status SysEx | Never forwarded; the bridge reads them to follow the buttons |
| 11 Arp + Rec / Play | After `06 1D/1E/1F` it swallows that button's transport CC and MMC until its release event (`06 12/14/10`) plus 150 ms (the CC and the event arrive in either order) |
| DAW notes → Swing | Not forwarded by default: with transposition from USB they would transpose the sequencer (a likely cause of the "random octave transpositions" users report) |
| Stuck notes | Tracks the notes it forwarded; **Panic** (and unplugging the Swing) sends their note offs, sustain off and All Notes Off on all 16 channels |

Not covered yet (needs the DAW to test): latency through loopMIDI, and DAWs that send Song Position
before Start.
