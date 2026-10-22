# ANT_task

Keyboard implementation based on **`old/ANT_task.py`**, not a recreation of the older
E-Prime experiment or the published protocol. Run from the repository root:

```powershell
pixi run ant-task
```

## Participant and responses

Uses the shared participant-number/monitor dialog, with optional webcam recording
(off by default). There is no eye-tracker option or gaze recording.

Identify the **middle bird's colour**, ignoring its neighbours and whether the
row is above or below the nest. Press **G for yellow** and **H for red**, as in
the old PsychoPy script. These are real keyboard responses, not just saved
labels. Mouse clicks and touchscreen taps are not responses; no touchscreen
houses are drawn. Other keys do not count as participant responses.

## Editable instructions

All instruction, reminder, break and closing messages are read from
**`instructions.txt`**, using the same `[section]` format as HideAndSeek.
Edit or translate the wording without changing the Python script; keep the
section headings and the G/yellow, H/red response mapping unchanged. The file
is checked for missing/empty required sections before participant setup.

Messages use **bold black text on an opaque ivory panel** over the original
artwork, rather than low-contrast text directly over the picture. The panel is
only present on message screens, never during fixation, cues, targets or
feedback. The exact loaded wording is also kept in the participant JSON.

## Protocol and intentional changes from the converted script

- Six fixed, untimed practice targets: YELLOW_CONG, YELLOW_INC, RED_CONG,
  RED_INC, ANT_6 and ANT_7, with one-second feedback and an operator-controlled
  reminder after each. The first four are birds-only strips; the last two use
  the full tree scene. Practice starts directly with the target, without cues.
- 48 test conditions from `Stimuli/trial_list.csv`, transcribed from
  `old/Trial_list_ANT.xlsx`. The workbook is also copied into Stimuli for reference;
  the runtime reads the CSV, so Excel libraries are not required.
- `Stimuli/sequences.csv` preassigns all 48 conditions to S001–S400: shuffle once
  per participant, then split into three blocks of 16. Each block need not be
  balanced. Playback reads the CSV in saved order, with no runtime shuffling.
  Missing participants and malformed schedules stop setup before presentation.
- Initial fixation: one shuffled value from 0.4–1.6 s in 0.1 s steps, reused for
  every trial, preserving the old script's `fix_times[1]` behaviour.
- Cue: 350 ms; warning sound starts with the cue when specified in the CSV.
- Post-cue fixation: 100 ms, followed by a 150 ms interstimulus interval (ISI).
  **Both show `ANT_1`: the same tree and unhighlighted eggs**, so the picture
  stays continuously visible for the combined 250 ms before the birds appear.
  This intentionally replaces the old script's 150 ms black screen, without
  removing the interval or changing its requested duration.
- Target: until the first G/H response, maximum **5 seconds**.
- Correct/incorrect/missing response: supplied feedback image and sound, 1 second.
  There is no added timed post-feedback interval. Saving introduces an untimed
  delay before feedback/next trial, as in the converted script.
- Progress pictures after test trials 16 and 32; Space continues.

Visual intervals are refresh-bound and may exceed requested durations. Warning
and feedback sounds use the converted script's files, without replacing them
with E-Prime/paper sounds or forcing a different duration.

## Pre-generated randomisation

`Stimuli/trial_list.csv` is the source condition table; the runtime schedule is
`Stimuli/sequences.csv` (one test trial per row). Columns include subject ID,
seed, fixation duration, trial/block, original condition, colour, warning, cue,
target and expected response. Practice order is fixed and is not randomised.

Generate or safely extend the schedule from the repository root:

```powershell
pixi run python -m ANT_task.Stimuli.generate_sequences
pixi run python -m ANT_task.Stimuli.generate_sequences --subjects 500
```

The fixed master seed is **20261022**; each participant's seed is the master
plus their number. The generator preserves existing assignments when extending,
does nothing if the requested schedule already exists unchanged, and refuses
to overwrite mismatched assignments or reduce the participant count. Keep the
generator, source conditions and assigned CSV unchanged during collection.
Reproduction assumes the same generator and Python randomisation behaviour.

Before presentation the participant's validated trial order, seed and fixation
are saved in `Data/Sxxx/Sxxx.json`. No participant CSV exports are written;
the master CSVs in `Stimuli/` remain inputs only. There is no automatic schedule
generation or fallback at study startup.

## Display and controls

Retains the converted script's **1920 × 1400** full-scene images and
**960 × 400** practice strips, including existing distortion/cropping and the
incomplete central bird in RED_INC.JPG. Original media are copied unchanged.
The task uses the selected monitor's entire native fullscreen window, with no
1080-high mask. On **1920 × 1200**, main images stay **1920 × 1400**, centred:
only **100 pixels at the top and bottom** are cropped, with **no black bars**
and no additional stretching. On 1920 × 1080, the crop remains 160 pixels per
edge. Birds and practice strips keep the same pixel sizes on both
monitors. Smaller displays scale drawing uniformly using
1920 × 1080 as the scaling reference, not a clipping boundary. Display metadata
records the actual visible scene size. Check cropping and instruction legibility
on the collection display.

Space advances operator instruction/progress screens; Esc there stops.
During a timed test trial, Esc requests a pause **after feedback**, so pausing
does not contaminate the response window. Space resumes; Esc again stops.
During untimed practice, Esc ends the current attempt and opens the pause after
feedback. There is no X-controlled video break in this study.
Closing waits for Space/Esc instead of the old script's automatic two-second exit.

## Saved data and timing

`Data/Sxxx/Sxxx.json` contains metadata, planned test order, completed response
rows and event markers. The `results` list contains practice/test results,
including original condition number, block, expected/actual g/h response,
response colour, correctness, RT in seconds and target onset. Unlike the old
script, practice responses are saved too. Metadata identifies the response mode
as `keyboard` and records the colour/key mapping. New keyboard results do not
have touch coordinates; existing touchscreen session files are not changed.
JSON is saved after the response and after feedback, and at session end.
An interrupted trial may have events but no result row; a result without
`trial_end` means feedback did not finish. Errors after study start attempt a
final save and release window/sound/recorder resources.

Events include study start/end/stop/error, trial start/end, fixation/cue/
postcue-fixation/ISI/target/feedback onsets, response/no_response and pause. Phase onsets are flip callbacks; no separate offset timestamps are
claimed. The visible-tree interval is marked `isi_onset`, replacing the former
`blank_onset`; existing session files are not changed. Response events include
the actual G/H `key`, its PsychoPy keyboard
`press_time` and RT. RT is the keypress timestamp minus target flip callback
time, not the later polling time. Pending keyboard events are cleared at target
onset; pre-onset and post-deadline keypresses are rejected. Keyboard/display/audio
latency must be validated on the real hardware. Optional webcam event labels
are not frame-exact onset measurements.

Read the tables with pandas:

```python
import json
import pandas as pd

with open("ANT_task/Data/S001/S001.json", encoding="utf-8") as file:
    session = json.load(file)

results = pd.DataFrame(session["results"])
events = pd.DataFrame(session["events"])
planned_trials = pd.DataFrame(session["planned_trials"])
```

Seed, fixation duration, display information and other session metadata remain
at the top level. Optional webcam files are still saved separately under `video/`.
Existing CSV outputs from earlier versions are not deleted or modified.

## Checks

```powershell
python -m unittest ANT_task.test_ant
```

These checks do not open PsychoPy or create participant data. A real keyboard,
display and audio pilot is required before data collection.
