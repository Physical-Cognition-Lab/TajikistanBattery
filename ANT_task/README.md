# ANT_task

A keyboard attention task: identify the **middle bird's colour**, ignoring its
neighbours and position above/below the nest. **G = yellow; H = red.** This follows
the converted `old/ANT_task.py`, not a recreation of the published/E-Prime protocol.
Touchscreen/mouse input is not a response.

Run from the repository root: `pixi run ant-task`.

## Study structure and timing

**Setup → welcome/Space → 6 practice trials → 3 × 16 test trials → closing screen.**

Practice uses six fixed targets, with no cue or response deadline, followed by
**1 s feedback** and a Space-controlled reminder after each. The first four
targets are birds-only strips; the last two use the full scene.

Each test trial:

| Phase | Requested duration |
| --- | --- |
| Initial fixation | Participant's assigned 0.4–1.6 s value, reused every trial |
| Cue + warning sound when specified | 350 ms |
| Post-cue fixation | 100 ms |
| ISI | 150 ms; same tree/unhighlighted eggs stay visible, not a black screen |
| Target | Until first G/H response, maximum 5 s |
| Correct/incorrect/no-response feedback + sound | 1 s |

Space-controlled progress screens follow test trials **16 and 32**. Session
length depends on responses and operator waits. Intervals are refresh-bound;
saving after responses/feedback adds untimed delays, with no extra timed ITI.

## Assigned order and display

`Stimuli/trial_list.csv` defines the 48 test conditions; `Stimuli/sequences.csv`
preassigns their order, seed and fixation duration for S001–S400. The shuffled
order is split into blocks of 16 (not necessarily balanced within blocks).
Playback does not shuffle or generate missing assignments. Keep inputs unchanged.
To safely extend the schedule: `pixi run python -m ANT_task.Stimuli.generate_sequences --subjects 500`.

The selected monitor is fullscreen. Main images retain their **1920 × 1400**
size on 1920-wide collection displays: 160 pixels per edge are cropped at
1920 × 1080, or 100 at 1920 × 1200, with no added black bars. Practice strips
are **960 × 400**. Smaller screens scale uniformly; check cropping/legibility.
Original image distortion/cropping is retained. Operator wording comes from
`instructions.txt`; keep section names and the G/H mapping when translating.

## Controls and recording

- **G/H:** participant responses. RT uses the keypress timestamp relative to
  the target flip; pre-onset and post-deadline presses are rejected.
- **Space:** advance instruction/progress/closing screens; **Esc** there stops.
- **Esc in a test trial:** queue a pause after feedback. Space resumes, Esc stops.
  In untimed practice it ends the attempt, then pauses after feedback.
- Optional webcam defaults **off**, starts after welcome and includes practice,
  pauses and closing. **No gaze recording or X video break.**

## Events / triggers

Named software events are saved in `events` and sent to the optional webcam:

| Event | Meaning |
| --- | --- |
| `study_start` | Before practice |
| `trial_start` / `trial_end` | Before trial phases / after feedback |
| `fixation_onset`, `cue_onset`, `postcue_fixation_onset`, `isi_onset` | First flips of test phases |
| `target_onset` / `feedback_onset` | First target / feedback flip |
| `response` / `no_response` | Valid G/H press / deadline reached |
| `pause` | Pause screen opens |
| `study_end` / `study_stopped` / `study_error` | Completion / stop / exception |

No separate phase-offset or `resume` events. An unfinished trial can have events
without a result; a result without `trial_end` means feedback did not finish.
Software flip/keypress timestamps still require real display/audio/keyboard validation.

## Saved data

**`Data/Sxxx/Sxxx.json`** contains `planned_trials`, seed, fixation duration,
display metadata, exact instructions, `events` and practice/test `results`
(condition, block, expected/actual key, correctness, RT and target onset).
The plan is saved before presentation; responses, feedback and session end each
checkpoint JSON. Event times include setup after assignment loading and all pauses.
Optional webcam/timing files are in **`video/`**. No participant CSV is exported;
old CSV outputs are left untouched.
