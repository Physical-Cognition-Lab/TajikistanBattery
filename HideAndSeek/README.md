# HideAndSeek

The participant can switch between three puppets, tap the central puppet to
hide it, then tap where they expect it to reappear. Each puppet follows an
ordered list of reveal positions from `Stimuli/locations.csv`; which of the
three lists it walks is counterbalanced across subjects by
`Stimuli/participant_assignments.csv`.

Run from the repository root: `pixi run hide-and-seek`.

`Stimuli/participant_assignments.csv` is written before data collection and
holds 400 subjects. Extend it with
`pixi run python HideAndSeek/tools/make_participant_assignments.py --subjects 500`;
existing rows never change, because a row depends only on the master seed and
the subject number.

## Flow

```text
Session
├── Participant number + optional webcam recording
├── Welcome/instructions → Space to begin
├── Start webcam recording if selected
├── Trials: up to 83, or until any puppet uses its 35 positions
│   ├── Choose/switch puppet ............ participant-paced
│   ├── Tap central puppet to hide ..... participant-paced
│   ├── Tap above screen centre
│   │   to predict its next position ... participant-paced
│   ├── Reveal animation + sound ....... ~1 s (10 images × 0.1 s)
│   └── Save data → next trial
├── Save final data
└── Closing message → Space to close; stop recording
```

## Timing

There is no fixed session duration: choosing, hiding and predicting have no
response timeout. After a prediction, the reveal uses 10 images, each shown
for about 0.1 s (about 1 s in total), with a reveal sound. Refresh timing and
pauses can extend this. There is no separately timed gap before the next
trial; data is saved first. The first trial includes extra hide/predict hints.

During choosing or the reveal, Esc pauses; Space resumes and Esc again stops.
Esc on the welcome or closing screen exits directly.

X waits until the current trial's reveal finishes, then loops `utils/pause.avi`
as a video break. Press X again to continue. It logs `attgrabber` (no `resume`
event), and optional webcam recording continues during the break.

## Triggers

These names are saved in the JSON session table (`action` column) and sent as
text to the optional webcam recorder. No eye-tracker triggers are sent yet.

- `study_start`: before the first trial.
- `trial_start` / `trial_end`: before choosing / after the reveal. Stopping
  during choosing leaves that trial without a `trial_end`.
- `switch`: a puppet portrait is selected.
- `hide`: the central puppet is tapped to hide it.
- `predict`: a valid prediction above screen centre is tapped.
- `miss`: a tap does not hide a puppet or make a valid prediction.
- `pause`: when the Esc pause screen opens.
- `attgrabber`: when the X-controlled video break opens.
- `study_end` / `study_stopped`: normal completion / operator stops early.

Click events keep their original press times, but are added to the table and
sent to the recorder after a valid prediction, not at the tap itself. Stopping
during choosing discards that trial's buffered clicks.
There are no separate reveal-onset/offset or `resume` triggers. Data is saved
after each trial and at session end; exiting the welcome screen logs no study events.
