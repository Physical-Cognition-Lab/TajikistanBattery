# InformationGain

The infant sees a central cue followed by a target in one of four quadrants.
There are **16 sequences of up to 15 trials**. The experimenter marks look-aways;
a look-away lasting at least one second ends that sequence and skips its remaining trials.

Run from the repository root: `pixi run information-gain`.

## Study structure and timing

**Setup → positioning/calibration if selected → Space → opening background →
16 sequences → 10 s end screen.** Space advances between sequences.

| Phase | Scheduled duration at 60 Hz |
| --- | --- |
| Opening background (once) | 1.5 s |
| Central cue | 1 s / 60 frames |
| Background-only ISI | 0.75 s / 45 refreshes |
| Target | 1.5 s / 90 frames |
| Background-only ITI | 0.75 s |

**4 s per complete trial, 60 s per full sequence, 16 min for all 240 trials**,
plus opening/end screens, setup, loading, saving and operator waits. Look-aways
shorten sequences. Animation timing assumes **60 Hz**, one image per refresh.
The cue's first frame is blank; it reaches full size at frame 32.

With tracking enabled, JSON/gaze saving consumes part of the existing **750 ms
ITI**; background refreshes fill the remainder. Longer saves extend it. Without
tracking, saving follows each trial. Completed cue/target durations differing by
more than 0.1 s set a timing warning; this does not detect every dropped refresh.

## Assigned order and display

`Stimuli/sequences_t.csv` fixes target-location indices; the participant number
determines their quadrant mapping. Each sequence uses its numbered cue/target
pair, with no runtime shuffle. Keep the source CSV and images unchanged.

Animations are **200 × 200 pixels**, with targets at (±576, ±324) relative to
screen centre; the background is **1920 × 1080**. Select the fullscreen monitor
configured for the tracker and verify the layout and 60 Hz timing there.

## Controls and recording

- **Space:** start/advance; during trials, mark a look-away.
- **X:** cancel a pending look-away within 1 s; it is **not** a video-break key.
- **Esc:** open the pause screen; Space resumes, Esc stops.
- Webcam, eye tracking and Recalibrate default **on**. Positioning and optional
  recalibration happen before the opening Space wait; unchecking Recalibrate
  keeps the current calibration. Recordings start after Space and include pauses.
- Background music plays during the study; recordings stop before the end screen.

## Events / triggers

Named software events go to JSON `rows` (`action`) and selected gaze/webcam recordings:

| Event | Meaning |
| --- | --- |
| `study_start` / `background_start` | Before opening background / its first flip |
| `sequence_start` / `sequence_end` | Before / after the sequence's trials |
| `trial_start` / `trial_end` | Before cue / after ITI |
| `cue_start` / `target_start` | Just after the first animation flip |
| `cue_end` / `target_end` | First following background flip, starting ISI / ITI |
| `lookaway` / `lookaway_cancel` | Look-away marked / X pressed while one is pending |
| `trial_aborted` | Sustained look-away ends trial/sequence instead of `trial_end` |
| `pause` | Pause screen opens |
| `study_end` / `study_stopped` | Normal completion / operator stops |

Interrupted phases may lack an end marker. No `resume` event. Event timestamps
are software times, not measurements of physical display/audio onset.

## Saved data

Under `Data/Sxxx/`:

- **`Sxxx.json`:** `metadata` includes the source schedule, full `planned_trials`,
  participant-specific `target_locations`, display information and timing warning;
  `rows` holds actual events/positions. The plan is saved before calibration/trials.
  Session times start after window creation, **including loading/calibration**;
  trial times start before the cue.
- With tracking, JSON/gaze checkpoints occur during ITIs; `trial_end` reaches
  disk at the next checkpoint. Aborted trials save on return; final JSON always saves.
- **`Sxxx_gaze.h5`** and **`video/`:** optional gaze/events and webcam/timing files.
  No separate sequence CSV.
