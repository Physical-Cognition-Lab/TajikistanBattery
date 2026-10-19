# WhatBabiesKnow

The infant watches three blocks of short videos. Each block contains 18 video
presentations, with category order shuffled separately for each block. Videos
within a category stay together; some categories allow repeated selections.

Run from the repository root: `pixi run what-babies-know`.

## Flow

```text
Session
├── Participant/options + eye-tracker connection check
├── Load the subject's three-block CSV schedule and save a copy
├── Prepare block 1's 18 movie players on a black screen
├── Start screen → Space to begin
├── Start optional webcam recording
├── Blocks × 3
│   ├── Play shuffled category groups: 18 videos per block
│   │   ├── Gaze following .............. 3
│   │   ├── Object representation ....... 2
│   │   ├── Action prediction ........... 2
│   │   ├── Geometry .................... 2
│   │   ├── Numerosity: easy / hard ..... 2 / 2
│   │   ├── Three attention-getter groups 1 each
│   │   └── Relations: neutral/violation . 1 each, shuffled
│   ├── Save block data
│   └── Between blocks
│       ├── Black screen: unload previous players and prepare next block
│       └── Once ready: Space continues / Esc stops
└── Save final data, stop recording, unload remaining players and close
```

## Randomization and saved schedules

`Stimuli/sequences.csv` contains the assigned orders for S001–S400: one movie
per row, 54 movies per subject. The experiment reads the selected subject's
rows without further randomization and saves them as `Data/Sxxx/Sxxx_sequence.csv`.
The existing JSON sequence and event log are also retained. Missing subjects,
incorrect trial numbering, or missing movies stop setup before playback.
The CSV columns are `subject_id,seed,block,trial,category,video`. Block numbers
run from 1 to 3; trial numbers run from 1 to 18 within each block. Movie paths
are relative to `Stimuli/`. Subject number 1 uses S001's schedule, and so on;
there is no wraparound or automatic schedule generation for subjects above 400.

The standalone generator is `Stimuli/generate_sequences.py`. Run it from the
repository root with `python WhatBabiesKnow/Stimuli/generate_sequences.py`.
It uses only Python's standard library and a fixed master seed, `20261019`.
Each subject's seed is the master seed plus their subject number, and is saved
in the CSV and JSON. With the same generator, Python environment and movie pools,
the schedules can be reproduced. The generator refuses to
overwrite an existing CSV; keep the assigned schedules unchanged during collection.

There are **10 category groups**, shuffled separately for each block during
CSV generation. All movies from a group stay together; playback does not
shuffle the CSV again.

| Group | Movie pool | Movies per block | Selection |
| --- | --- | --- | --- |
| GazeFollowing | 64 | 3 | Without replacement |
| ObjectRepresentation | 4 | 2 | With replacement |
| ActionPrediction | 18 | 2 | Without replacement |
| Geometry | 26 | 2 | Without replacement |
| ANS_easy | 2 | 2 | With replacement |
| ANS_hard | 2 | 2 | With replacement |
| Attention | attention2, attention3 | 1 | Without replacement |
| Attention2 | attention4, attention6 | 1 | Without replacement |
| Attention3 | attention2, attention3, attention4, attention6 | 1 | Without replacement |
| Relations | 16 neutral + 16 violation | 1 neutral + 1 violation | Without replacement, separately per subgroup |

- **Without replacement:** shuffle a pool, take its movies in order, and
  reshuffle/refill only when empty. Unused movies carry over to the next block.
  Pools restart for each subject, not each block. For example, the nine
  GazeFollowing movies in a full session are all different.
- **With replacement:** each selection is independent, so the same movie can
  appear twice even within one block. Neither ANS variant is guaranteed to appear.
- **Attention pools are independent:** a movie can repeat across attention
  groups, even before either group's own pool is exhausted. Repeats are also
  allowed across a pool-refill boundary.
- **Relations:** choose independently from the neutral and violation pools,
  then shuffle the order of those two movies. There is no matching of filename
  conditions across the two selections.
- There is no forced easy-before-hard order, fixed attention spacing,
  prevention of adjacent attention groups, or balancing of actors, directions,
  colours, or category positions across subjects. Randomization is not exact
  counterbalancing.

This follows the documented Tobii without-replacement pool interpretation;
exact equivalence to the original Tobii runtime has not been tested.

## Timing

Every video plays to its end; duration depends on the selected
clips. There is no fixed timed gap between videos. The session contains
54 video presentations in total, plus loading and operator-controlled pauses.
The groups above list the block's contents, not a fixed presentation order.

### Movie durations and embedded intervals

The following are video-track lengths measured from the supplied media, not
guaranteed wall-clock playback durations or Tobii's slightly longer media
descriptor durations. All movies are 30 fps.

| Movies | Video-track duration |
| --- | --- |
| GazeFollowing | 8.5 s |
| ObjectRepresentation | approximately 9.333 s |
| ActionPrediction | approximately 10.267–11.733 s |
| ANS_easy / ANS_hard | 9.6 s |
| Geometry | 5 s |
| Relations | approximately 35–35.2 s |
| attention2 / attention3 / attention4 / attention6 | 4 / 2.5 / 2.5 / approximately 2.033 s |

Some intervals are already part of the movies and must not be added again:

- GazeFollowing ends with 500 ms of white; ObjectRepresentation ends with
  approximately 300 ms of black; ActionPrediction ends with approximately
  500 ms of black.
- Each ANS movie contains 12 cycles of 500 ms dots followed by 300 ms white.
  These are movie contents, not 12 separately scheduled trials.
- Geometry is essentially a static display for its full 5 s.
- Relations movies include short gray holds near 0, 6.9 and 13.7 s, and a
  nearly static final 4.8–5 s. The complete 35–35.2 s movie plays: `_5s` in a
  filename is not a playback limit. Scientific phase labels for these intervals
  have not been confirmed.

### Playback and operator-controlled pauses

During movie playback, exposed screen areas match the original design:
GazeFollowing uses light gray (`#EDEDED`), Geometry uses white (`#FFFFFF`),
and all other categories use black. A full-window background is drawn behind
each movie frame without resizing the movie or changing its contents. Preparation
screens, inter-movie gaps, the opening screen and pause screens remain black.

`prepare_block()` loads the block's 18 movie players in saved CSV order, with
automatic playback disabled, and uploads their initial frames without showing
preview images. Each scheduled presentation has its own player, including
repeated selections of the same file. Block 1 is prepared after calibration
and before the opening start screen.

Between blocks, the screen stays black while the previous players are unloaded
and the next 18 players are prepared. Only then does the usual Space/Esc pause
screen appear. A real PsychoPy test of this implementation completed all 18
movies: initial preparation took about 1 s, and the between-block black screen
lasted about 4.7 s. The next block's first two movies and early-exit cleanup
also passed. These are development-computer measurements without eye tracking
or webcam recording, not fixed delays; other setups can differ.

Players are retained throughout the block, rather than loaded/unloaded between
individual movies. Each finished movie is explicitly paused: leaving a finished
player unpaused interfered with the next player's playback clock in testing.
Cleanup is registered as each player is created, so completed and unplayed
players are released on normal completion, early abort, or exceptions, before
the window closes. Keeping 18 players open uses substantial resources: about
2.4 GB of process RAM and roughly 1,000 threads with the tested default settings.

Onset is logged on the first flip with an available decoded video frame;
offset is logged on the flip that clears the final image. There is still an
untimed black gap while the finished player is paused, gaze data is saved when
enabled, and the next prepared player starts. Preloading removes per-movie
loading/unloading from that gap; it does not guarantee gap-free playback. These software
markers are not photodiode measurements of physical display onset/offset;
decoding, refresh timing and system load can affect actual presentation.
There is no gaze-contingent advancement, separate fixation interval, or extra
timed ISI/ITI. Do not interpret inter-movie gaps as controlled blank intervals.

Space starts playback from the opening screen. Between blocks, the operator
decides when to continue; there is no mandatory continue screen after block 3.

Esc during a video requests a pause after that clip finishes. At the pause,
Space resumes and Esc stops. Esc on the start screen aborts before playback.

X waits until the current video ends, then loops `utils/pause.avi` as a video
break. Press X again to continue. It logs `attgrabber` (no `resume` event), and
webcam/eye-tracker recording continues during the break.

## Triggers

Triggers are **named software events**, not numeric TTL pulses. Each call to
`save_event()` appends an event to the JSON and forwards only the trigger name
to `etracker.record_event()` and `recorder.send_text()` when those devices are
enabled. This script does not send hardware TTL/sync-out markers.

| Trigger name | When it is emitted |
| --- | --- |
| `study_start` | After optional recording starts, immediately before the block loop. |
| `block_start` | After block preparation and any between-block pause, just before starting its first prepared movie. |
| `video_onset` | Via `win.callOnFlip`, on the first flip with an available decoded movie frame. |
| `video_offset` | Via `win.callOnFlip`, on the flip clearing the movie after playback ends. |
| `pause` | On entry to the Space/Esc pause function, before drawing the pause screen; used for Esc pauses and between-block waits. |
| `attgrabber` | After loading the X-controlled break movie, before starting it; not flip-aligned. |
| `block_end` | After completing the block's movie loop and any requested final-movie pause/break. |
| `block_stopped` | When the operator stops from an Esc pause within a block. |
| `study_end` | After the block loop completes normally. |
| `study_stopped` | After an operator-requested stop, including stopping at a between-block pause. |

### Event contents and clocks

- JSON `events` contain `time`, `trigger`, `block`, `trial`, and `video`.
  `time` is seconds on a PsychoPy clock created just before `study_start`;
  it includes subsequent pauses and loading, but excludes setup/calibration.
- Movie events include the block number, within-block trial number and movie
  basename. Block events include the block number. Other events leave these
  context fields null. The CSV/JSON planned sequence supplies category and
  relative-path information.
- Eye tracking and webcam receive **only the event name**, not those JSON
  context fields or the JSON timestamp. Their timestamps belong to their
  respective recording systems; do not treat them as the JSON elapsed seconds.
- Webcam messages are queued asynchronously, overlaid on a saved camera frame,
  and logged in its timing CSV with frame index and monotonic send/receive/capture
  timestamps. The overlay is not a frame-exact measurement of stimulus onset.

There are no separate category, trial-start/end, ANS-cycle, within-movie phase,
calibration, preparation-start/end, or `resume` triggers. The scheduled attention movies use ordinary
`video_onset` / `video_offset` events; `attgrabber` is only the extra X break.
Stopping between blocks does not create a `block_stopped` for the next block,
because that block has not started. Aborting on the opening screen emits no
study start/stop event. Exceptions run cleanup but do not guarantee a stopped
event or a final JSON save.

### Saved data

The assigned CSV copy and initial JSON plan are saved before the opening screen.
JSON is then saved after each block (including a stopped block) and at session
end, not after every movie. The JSON retains the full planned schedule even
when playback stops early; use events to identify what was actually presented.
Gaze data is saved after each movie. Optional webcam video and its timing files
are saved under `Data/Sxxx/video/`.

## Eye tracking

With Eye tracker selected, DeToX shows positioning before the start screen.
Recalibrate runs its infant-friendly five-point calibration; an unchecked box
keeps the tracker's current calibration. A cancelled/unaccepted calibration
does not automatically abort setup. Recording starts before `study_start`,
continues through pauses, and stops after the final event (also on errors).
Both webcam and gaze recording also continue through the between-block black
preparation screens; initial block preparation occurs before recording starts.
Gaze and events are appended to `Data/Sxxx/Sxxx_gaze.h5`, using simplified
pixel coordinates. Gaze is saved after each video, before any pause or next
video loading; JSON saves remain per block. Use the fullscreen display
configured for the Tobii tracker.
