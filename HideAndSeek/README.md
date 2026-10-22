# HideAndSeek

A touchscreen prediction game: the participant chooses one of three puppets,
taps the central puppet to hide it, then taps **above screen centre** where they
expect it to reappear. Each puppet advances along its own assigned trajectory.

Run from the repository root: `pixi run hide-and-seek`.

## Study structure and timing

**Participant setup → welcome/Space → choose, hide, predict, reveal → closing screen.**

Up to **83 trials**, stopping sooner when any puppet uses all **35 positions**.
Choosing and predicting have no response timeout, so session length is variable.

| Phase | Timing |
| --- | --- |
| New trial or puppet switch | Appearance sound after 0.3 s; hint after 0.5 s; central puppet after 1 s |
| Hide tap | Hiding sound after 0.3 s; hidden patch after 1 s; prediction can be made sooner |
| Reveal after prediction | 10 images × approximately 0.1 s, with sound (~1 s) |
| Between continuing trials | Save data, then 1 s of the scene without a central puppet |

Portrait switches restart the appearance stage. Quick predictions cancel any
pending hiding sound. First-trial hide/predict hints follow the current stage.
Loading, saving, refresh timing and pauses add time; no gap follows the final trial.

## Assigned paths and display

`Stimuli/locations.csv` defines three ordered paths. Each participant's row in
`Stimuli/participant_assignments.csv` assigns those paths to blue/red/green.
The participant chooses the actual puppet order; it is **not** predetermined.
Keep both CSVs unchanged during collection. Operator text is in `instructions.txt`.

The **1920 × 1080** scene scales uniformly inside the selected fullscreen monitor.
At 1920 × 1200 it has 60-pixel black bars above/below. Touches are converted back
to scene coordinates; bar touches count as misses. Check touch alignment and
extreme reveal positions before collection; original scene clipping is retained.

## Controls and recording

- **Touch/click:** select a portrait, hide the visible central puppet, or predict.
- **Space:** advance welcome/closing screens or resume a pause.
- **Esc:** pause during choosing, reveal or the inter-trial gap; Esc again stops.
  Esc on welcome/closing exits directly.
- Webcam is optional, default **off**; it starts after welcome and includes
  pauses and the closing screen. **No gaze recording or X video break.**

## Events / triggers

Named software events are saved in JSON `rows` (`action`) and sent to the webcam:

| Event | Meaning |
| --- | --- |
| `study_start` | Before the first trial |
| `trial_start` / `trial_end` | Before choosing / after reveal (including an interrupted reveal) |
| `switch` / `hide` / `predict` / `miss` | Portrait choice / hide tap / valid prediction / other tap |
| `pause` | Pause screen opens |
| `study_end` / `study_stopped` | Normal completion / operator stops |

Click rows retain press times, but are added and sent to the webcam **after a
valid prediction**. Stopping during choosing discards that trial's buffered
clicks and leaves no `trial_end`. No reveal-onset/offset or `resume` events.

## Saved data

Under `Data/Sxxx/`:

- **`Sxxx.json`:** `metadata` contains source filenames, colour→pattern mapping,
  full `planned_trajectories` (with playback angles) and display information;
  `rows` contains actual clicks, predictions, targets and events.
  The plan is saved before trials; updates follow each trial and session end.
  `time_study` includes participant setup; `time_trial` is relative to trial start.
- **`video/`:** optional webcam recording and timing files. No separate sequence CSV.
