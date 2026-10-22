# Features2Functions

The infant sees 18 object pictures: six familiar to infants, six familiar to
adults only, and six unfamiliar. An attention getter precedes each picture;
background music plays throughout the trials. `Stimuli/participant_assignments.csv` sets each
participant's object set, order and starting attention getter.

Run from the repository root: `pixi run features-to-functions`.

Object pictures are displayed at a fixed **1350 × 1080 pixels**. The
[AOI files](aois/README.md) use this displayed size, with image-relative
coordinates measured from the image's top-left corner.

## Flow

```text
Session
├── Participant/options + eye-tracker connection check
├── Load participant assignments, check assets and save planned order
├── Start screen → Space to begin
├── Start webcam recording if ticked (off by default) and background music
├── Object trials × 18
│   ├── Attention getter + sound ........ up to 2 s
│   ├── Object picture .................. 5 s
│   ├── Save data
│   └── If Esc requested: pause → Space resumes / Esc stops
└── Save final data, stop music/recording and close
```

## Timing

Each trial has an attention getter of up to 2 s (shorter if its movie ends)
followed by a 5 s picture. With full-length attention getters, the 18 trials
total about 2 min 6 s, excluding loading, saving, setup and pauses. There is
no separately timed gap between trials. The three attention getters cycle.

Onsets are logged on the first display flip. Offsets are logged when the
presentation function finishes; they are not display-clear timestamps, so
an image may remain visible briefly while the next stimulus loads.

Esc on the start screen aborts before playback. During trials, pause requests
are handled after the object picture finishes.

X also waits until the trial ends, then loops `utils/pause.avi` as a video
break. Press X again to continue. It logs `attgrabber` (no `resume` event), and
webcam/eye-tracker recording continues during the break.

## Triggers

These names are saved in the JSON `events` list (`trigger` field) and sent as
text to the optional webcam recorder and, when enabled, DeToX eye tracking.

- `study_start`: before the first trial.
- `trial_start` / `trial_end`: before the attention getter / after the picture.
- `attention_onset` / `attention_offset`: attention getter starts / finishes.
- `stimulus_onset` / `stimulus_offset`: object picture starts / finishes.
- `pause`: when the Esc pause screen opens, not at the initial keypress.
- `attgrabber`: when the X-controlled video break opens.
- `study_end` / `study_stopped`: normal completion / operator stops early.

There is no `resume` trigger. Data is saved after each trial and at session end;
aborting on the start screen does not log a study start or stop.

## Eye tracking

With Eye tracker selected, DeToX shows positioning before the start screen.
Recalibrate runs its infant-friendly five-point calibration; an unchecked box
keeps the tracker's current calibration. A cancelled/unaccepted calibration
does not automatically abort setup. Recording starts before `study_start`,
continues through pauses, and stops after the final event (also on errors).
Gaze and events are appended to `Data/Sxxx/Sxxx_gaze.h5`, using simplified
pixel coordinates. Gaze is saved between trials; this can add loading time.
Use the fullscreen display configured for the Tobii tracker.
