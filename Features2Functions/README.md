# Features2Functions

The infant watches **18 object pictures**: six familiar to infants and adults,
six familiar only to adults, and six unfamiliar. Each picture follows a short
attention-getter movie with sound; background music loops during the trials.

Run from the repository root: `pixi run features-to-functions`.

## Study structure and timing

**Participant setup → positioning/calibration if selected → Space → 18 trials → end screen.**

Each trial:

| Phase | Duration |
| --- | --- |
| Attention-getter movie | Up to 2 s; stops earlier if the movie ends |
| Object picture | 5 s |
| Save behavioural and optional gaze data | No fixed duration |

About **2 min 6 s** of presentations with full-length attention getters, plus
setup, loading, saves, pauses and the **10 s** completion screen. There is no
separate timed inter-trial gap. Music continues through pauses/video breaks.

## Assigned order and display

`Stimuli/participant_assignments.csv` fixes each participant's object set, picture
order and starting attention getter. The three attention getters then cycle;
there is no runtime shuffle. Keep assignments unchanged during collection.

Pictures and attention getters are **1350 × 1080 pixels**, centered on the
selected fullscreen monitor. Check the layout on the collection display.
The [AOI files](aois/README.md) use image-relative coordinates at this displayed size.

## Controls and recording

- **Space:** start or resume. **Esc on the start screen:** abort.
- **Esc during a trial:** finish the trial, then pause; Space resumes, Esc stops.
- **X during a trial:** finish the trial, then loop `utils/pause.avi`; X returns.
- Webcam defaults **off**; eye tracking and Recalibrate default **on**.
  Positioning and optional recalibration precede the start screen. Unchecking
  Recalibrate keeps the current tracker calibration.
- Selected recordings start after Space and continue through pauses/breaks.

## Events / triggers

Named software events go to JSON and the selected gaze/webcam recordings:

| Event | Meaning |
| --- | --- |
| `study_start` | Before the first trial |
| `trial_start` / `trial_end` | Before attention getter / after object picture |
| `attention_onset` / `attention_offset` | Attention getter starts / function finishes |
| `stimulus_onset` / `stimulus_offset` | Object picture starts / function finishes |
| `pause` / `attgrabber` | Esc pause / extra X-controlled video break opens |
| `study_end` / `study_stopped` | Normal completion / operator stops |

Onsets use flip callbacks. Offsets are **function-end markers**, not screen-clear
timestamps: a picture can remain visible while the next stimulus loads. No
`resume` event is emitted. Aborting the start screen emits no study start/stop.

## Saved data

Under `Data/Sxxx/`:

- **`Sxxx_sequence.json`:** source schedule, object set, full planned `stimuli`
  list (including attention getters), display metadata and actual `events`.
  The plan is saved before presentation; updates follow each trial and session end.
  Event times are seconds from just before `study_start`, including loading/pauses.
- **`Sxxx_gaze.h5`:** optional gaze/events, saved between trials and at shutdown.
- **`video/`:** optional webcam recording and timing files. No separate sequence CSV.
