# InformationGain

The infant sees a central cue followed by a target in one of four screen
quadrants. There are 16 sequences of up to 15 trials, using the positions in
`Stimuli/sequences_t.csv`. The experimenter marks look-aways; a sustained
look-away ends the current sequence early.

Run from the repository root: `pixi run information-gain`.

## Flow

```text
Session
├── Participant/options + eye-tracker connection check
├── Load stimuli and wait for Space
├── Start optional webcam recording and background audio
├── Opening background .................. 1.5 s (once per session)
├── Sequences × 16
│   ├── Trials × up to 15
│   │   ├── Central cue animation ....... 1.0 s (60 images)
│   │   ├── Background-only gap (ISI) ... 0.75 s
│   │   ├── Target animation ............ 1.5 s (90 images)
│   │   ├── Background-only gap (ITI) ... 0.75 s
│   │   └── Save data
│   ├── Look-away lasting ≥1 s can interrupt any trial phase
│   │   └── End sequence early; skip its remaining trials
│   └── Wait for Space before continuing
├── Save final data and stop audio/recording
└── “The End!” screen ................... 10 s
```

## Timing

One image per refresh, with no extra per-image waits. The study assumes
a 60 Hz display; it does not measure or check the refresh rate. Background gaps
use 45 refreshes each; the opening background uses 90. At exactly 60 Hz, the
scheduled phases total 4 s per trial, 60 s per full sequence, or 16 min for all
240 trials. Setup, loading, saving data, pauses, waits and the end screen add time;
in particular, slow saving can extend the background before the next cue.

Cue/target durations are checked from the first image flip to the first following
background flip, rather than from function entry to return. Completed presentations
more than 0.1 s from the expected duration set the timing warning. This is not a
guarantee against individual dropped refreshes; verify timing on the lab display.

The cue reaches full size at frame 32 and holds through frame 60. Its first
image is blank: the 1 s cue phase includes one blank refresh and about 983 ms
of visible shape at 60 Hz. See `Cues_60fps/README.md` for image-generation details.

During trials, Space marks a look-away; X cancels it if pressed within 1 s.
Esc opens a pause screen: Space resumes, Esc stops.

## Triggers

These names are saved in the JSON session table (`action` column) and sent as
text to the optional webcam recorder and, when enabled, DeToX eye tracking.

- `study_start`: before the opening background; `background_start`: its first flip.
- `sequence_start` / `sequence_end`: before / after a sequence's trials.
- `trial_start`: before the cue; `trial_end`: after the final gap.
- `cue_start` / `target_start`: just after the first animation flip.
- `cue_end` / `target_end`: just after the first following background flip,
  starting the ISI / ITI respectively.
- `lookaway`: Space marks a look-away; `lookaway_cancel`: X is pressed while
  a look-away is pending (cancellation only succeeds within 1 s).
- `trial_aborted`: a sustained look-away ends the trial and sequence early,
  instead of `trial_end`. An interrupted phase may have no end marker.
- `pause`: when the pause screen opens.
- `study_end` / `study_stopped`: normal completion / operator stops early,
  before the final end screen.

There is no `resume` trigger. Without eye tracking, JSON is saved after each
trial and at session end.

## Eye tracking and ITI saves

With Eye tracker selected, the window is fullscreen on screen 1; use the
display configured for the Tobii tracker. DeToX shows positioning before the
start screen. Recalibrate runs its infant-friendly five-point calibration;
unchecked keeps the tracker's current calibration. A cancelled/unaccepted
calibration does not automatically abort setup.

Recording starts before `study_start`, continues through pauses, and stops
after the final event, before the end screen (also on errors). Gaze and events
are appended to `Data/Sxxx/Sxxx_gaze.h5`, using simplified pixel coordinates.

With tracking enabled, JSON and gaze saves use the existing 750 ms ITI:
the first background flip starts a deadline, saving consumes part of that
time, and background refreshes fill the remainder. The ISI is unchanged.
A save longer than 750 ms extends the ITI; keyboard checks briefly wait
during the synchronous write. `trial_end`, logged after the ITI, reaches disk
at the next checkpoint/final save. Look-away-aborted trials save immediately
after returning from the interrupted phase; final data is always saved.
