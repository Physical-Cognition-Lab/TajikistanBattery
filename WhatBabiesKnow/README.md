# WhatBabiesKnow

The infant watches short videos about gaze following, object representation,
relations, action prediction, geometry and numerosity, with scheduled attention
grabbers throughout.

Run from the repository root: `pixi run what-babies-know`.

## Study structure and timing

**Setup → positioning/calibration if selected → Space → Block 1 → Break →
Block 2 → Break → Block 3 → 10 s completion screen.**

**3 blocks × 18 presentations = 54 per session.** Each block contains:

| Task group | Presentations per block |
| --- | ---: |
| GazeFollowing | 3 |
| ObjectRepresentation | 2 |
| Relations | 2: one Neutral + one Violation |
| ActionPrediction | 2 |
| Numerosity—easy | 2 |
| Numerosity—hard | 2 |
| Geometry | 2 |
| Attention grabbers | 3 separate groups, one clip each |

Video time is approximately **3 min 13 s per block / 9 min 40 s overall**.
Every movie plays to its end; Relations movies last about **35 s**, despite
`_5s` in their filenames. Add **250 ms on black at each block start**, and
**250 ms of the outgoing video's background between videos** (51 gaps = 12.75 s).
These waits are additional to the Tobii design. Loading, saving, setup and
operator-controlled breaks add time; there is no gap after a block's final video.

## Assigned order and display

Orders for S001–S400 are pre-generated in `Stimuli/sequences.csv`; playback
follows them without further randomization. Keep schedules unchanged during
collection. The generator is `Stimuli/generate_sequences.py`.

- Group order is shuffled per block, but each group's videos stay together.
  Numerosity easy/hard and the three attention groups are separate groups.
- GazeFollowing, ActionPrediction, Geometry and each Relations subgroup draw
  without replacement; unused videos carry across blocks until the pool empties.
  The attention groups also use separate without-replacement pools.
- ObjectRepresentation and Numerosity sample with replacement, so repeats can
  occur within a block. Relations draws Neutral/Violation independently, then
  shuffles their order. Attention groups can be consecutive or select the same clip.

Videos are centered on the selected fullscreen monitor. Relations is enlarged
proportionally to **1920 × 1080**; other movies retain native size. Geometry and
Numerosity have white surrounds. GazeFollowing starts gray and switches to white
at the displayed **8 s** timestamp (the final 500 ms); other surrounds are black.
The inter-video gap retains the outgoing surround. Source media are unchanged;
exact equivalence to the original Tobii runtime has not been tested.

## Controls and recording

- **Space:** start or continue from a pause/between-block break.
- **Esc during playback:** finish the video, then pause; Space resumes, Esc stops.
  Esc on the opening screen aborts.
- **X during playback:** finish the video, then loop `utils/pause.avi`; X returns.
  This is extra, not one of the 54 scheduled presentations.
- Between blocks, loading happens on black, then Space continues; no fixed break length.
- Webcam defaults **off**; eye tracking and Recalibrate default **on**.
  Positioning/optional recalibration precede the start screen. Unchecking
  Recalibrate keeps the current calibration. Recordings start after Space and
  continue through pauses/breaks, stopping before the completion screen.

## Events / triggers

Named software events go to JSON `events` and selected gaze/webcam recordings:

| Event | Meaning |
| --- | --- |
| `study_start` | Before the block loop, after recording starts |
| `block_start` | Before the 250 ms block-start wait |
| `video_onset` / `video_offset` | First decoded-frame flip / flip clearing the ended video |
| `pause` / `attgrabber` | Esc or between-block pause / extra X video break |
| `block_end` / `block_stopped` | Block completed / stopped within a block |
| `study_end` / `study_stopped` | All blocks completed / operator stops |

Events contain `time`, `trigger`, `block`, `trial`, `video`. Times are seconds
from just before `study_start`, including loading and pauses. Scheduled attention
clips use ordinary video events; `attgrabber` means only the X break. There is
no `resume` event; aborting the opening screen emits no study start/stop.

## Saved data

Under `Data/Sxxx/`:

- **`Sxxx_sequence.json`:** full planned `blocks`, seed, source filename (`schedule`),
  original assigned CSV rows (`schedule_rows`), display metadata and actual events.
  The plan is saved before presentation; JSON updates follow each block and
  session end. Use events, not the plan, to identify movies actually played.
  Unsaved events since the last checkpoint can be lost on a crash.
- **`Sxxx_gaze.h5`:** optional gaze/events, saved after each movie and at shutdown.
- **`video/`:** optional webcam recording and timing files. No new sequence CSV;
  existing CSVs are left untouched.
