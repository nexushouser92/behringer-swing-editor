# Keyboard and DAW checks (2026-10-20, Swing firmware 1.1.52)

Read-only tests with `tools/key_test.py`, which records everything the Swing sends over USB while
someone plays. Logs: `key_test_1.log`, `key_test_2.log`, `key_test_3.log`.

## Results

| Test | What happened |
|---|---|
| 1 (90 s) | 40 keys received. G2 and D2 got a note on and no note off of their own. Mod strip sent **CC 127**. Play/Stop sent CC 54/51 on channel 1, **CC 123 (All Notes Off)** and MMC. |
| 2 (60 s) | Keys, Hold and Stop were played from the start, but **nothing arrived for 55 s** except the Swing's own status SysEx; only the mod strip worked at the end. |
| 3 (60 s, after unplugging and plugging the Swing back in) | Everything worked: every black key, soft and hard (velocities 40–127), no contact bounce, Hold released its note with a proper note off, Stop sent CC 51 + CC 123 each time. |

## Findings

1. **The Swing can get stuck in a state where the keys send nothing**, and a power cycle fixes it
   (test 2 → test 3). This matches user reports of needing restarts. It is firmware behaviour; the
   editor cannot fix it. Workaround: unplug and plug the Swing back in.
2. **Mod strip on CC 127.** The setting "Mod CC number" is 127 (as read from this Swing and shown by
   Control Tribe). CC 120–127 are reserved *channel mode* messages in MIDI; CC 127 means "Poly mode
   on", which a synth or plugin may treat as "stop all notes / change mode". Using CC 1 (the standard
   mod wheel) avoids it.
3. **Transport buttons send controllers on the notes' channel.** Play, Stop and Rec send CC 54, 51
   and 50 on channel 1, the same channel the keys play on, so a DAW passes them to the armed
   instrument as parameter changes unless they are MIDI-mapped. Each press also sends CC 123 (All
   Notes Off), which is good against stuck notes. MMC is sent only while the transport is running.
4. **Velocity curve "Logarithmic"** makes hard presses reach 127 almost every time (test 3), which
   can feel like inconsistent velocity. "Linear" gives more range.
5. **Exclusive MIDI port on Windows.** Only one program can open the Swing at a time: with a DAW open,
   Control Tribe and the editor cannot connect (and the other way round). The editor now says so.
6. No real-time messages (clock, active sensing) were sent by the Swing while stopped.

## Changes applied to this Swing (2026-10-20, at the owner's request)

Written with `device.write_settings` and verified by reading everything back; all other settings
unchanged.

| Setting | Before | After | Why |
|---|---|---|---|
| Mod CC number (`14`) | 127 | **1** | standard mod wheel instead of the reserved CC 127 |
| Play / Stop / Rec MIDI channel (`63`/`61`/`62`) | 1 | **16** | transport CCs no longer reach the instrument on channel 1 |
| Velocity curve (`19`) | Logarithmic | **Linear** | wider velocity range |

In Ableton: to use Play/Stop/Rec, MIDI-map them (MIDI Map Mode, then press the button) — they now
arrive as CC 54/51/50 on channel 16.

After unplugging and plugging the Swing back in, all five values were still there.

## Test 4: DAW clock (`key_test_4_clock.log`)

The tool acted as a DAW from second 30: MIDI Start plus clock at 120 BPM.

- The arpeggiator **follows the external clock**: 16th notes every 0.125 s at 120 BPM.
- Every Stop still sends **CC 123 (All Notes Off) on channel 1**, even with the transport moved to
  channel 16, so Stop keeps working as a panic button for the notes.
- The Swing **sends the clock it receives back out over USB** (1446 clock messages came back). If a
  DAW syncs to the Swing's input *and* sends clock to its output, the clock loops. In Ableton: Sync on
  the Swing's output only.
- The **tempo knob sent nothing over USB**, neither with the internal clock nor with the DAW clock.
  There is no setting to give it a CC.
- Rec sends CC 50 on the transport channel plus MMC Record Strobe/Exit (`F0 7F 7F 06 06/07 F7`).
- Hold in DAW mode behaved like Gate because the first version of DAW mode set Hold to Gate. That was
  removed from DAW mode and Hold was set back to Toggle on this Swing.

### Swing status messages (command 70, decoded)

| First byte | Seen | Likely meaning |
|---|---|---|
| `01` | `01 05` about every 0.5 s while not synced | idle / sync status ⏳ |
| `03` | `03 00`, `03 01` when buttons were pressed | a mode switched off / on ⏳ |
| `04` | `04` + 32-bit float, every 0.5 s with external clock | detected tempo: 120.024, 120.0, 119.976 BPM |
| `06` | `06 <n>`: odd n on press, even n on release | button events: `0F/10` Play, `13/14` Stop, `11/12` Rec, `09/0A` and `19`–`1C` other buttons ⏳ |
