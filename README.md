# TajikistanBattery

PsychoPy studies prepared for infant/child data collection in Tajikistan.
Each study's README explains its purpose, timing, controls, events and saved data:

| Study | Main task | Run from the repository root |
| --- | --- | --- |
| [ANT_task](ANT_task/README.md) | G/H keyboard response to the middle bird's colour | `pixi run ant-task` |
| [Features2Functions](Features2Functions/README.md) | 18 object pictures with attention getters | `pixi run features-to-functions` |
| [HideAndSeek](HideAndSeek/README.md) | Touchscreen puppet-position prediction | `pixi run hide-and-seek` |
| [InformationGain](InformationGain/README.md) | Cue/target animations with operator-marked look-aways | `pixi run information-gain` |
| [WhatBabiesKnow](WhatBabiesKnow/README.md) | Three blocks of cognitive-task videos | `pixi run what-babies-know` |

## Setup and running

Install [pixi](https://pixi.sh), then use the commands above or the desktop shortcuts
in `Shorcuts/`. First launch may take longer while the environment installs.
`pixi.toml` / `pixi.lock` pin Python 3.10, PsychoPy and DeToX; keep the tested
versions rather than updating packages during collection.

- Choose an unused participant number and the **participant monitor** in setup.
  A new `Data/Sxxx/` folder is created only after validation; existing folders cannot be reused.
- Webcam defaults **off**, except in InformationGain (**on**).
- Features2Functions, InformationGain and WhatBabiesKnow offer eye tracking
  and Recalibrate, both default **on**. A failed connection offers Retry,
  Uncheck or Cancel. Unchecking Recalibrate retains the current calibration;
  a cancelled/unaccepted calibration does not automatically abort setup.
- Use the fullscreen monitor configured for the Tobii tracker. Check layout,
  touch alignment, sound level and timing on the real collection hardware.
  Studies target 1920 × 1080 / 1920 × 1200 displays, but fitting differs by study.
- Playback volume is **1.0** (explicit in InformationGain, default elsewhere).
  This does not normalize recordings or set Windows/speaker volume.

## Events and saved data

Named triggers are **software events, not hardware TTL pulses**. They are saved
in the participant JSON and sent as event-name labels to optional recordings.
Gaze/webcam clocks are separate; labels are not physical-onset measurements.
Recordings continue through pauses. See each study for exact start/stop points,
event meanings, time origins and save checkpoints; no study emits `resume`.

Outputs live under each study's `Data/Sxxx/`:

- **Main JSON:** planned assignment and actual behavioural events/results.
  ANT_task uses `planned_trials`; Features2Functions uses `stimuli`;
  WhatBabiesKnow uses `blocks` plus original `schedule_rows`;
  HideAndSeek metadata includes `patterns` / `planned_trajectories`;
  InformationGain metadata includes `planned_trials` / `target_locations`.
  A planned trial is not proof it was presented. No separate participant
  sequence CSV is exported; existing CSV outputs are left untouched.
- **`Sxxx_gaze.h5`:** optional DeToX gaze/events in simplified pixel coordinates
  (Features2Functions, InformationGain, WhatBabiesKnow only).
- **`video/`:** optional webcam video and timing/event files; no webcam audio.

Keep the master schedule CSVs in `Stimuli/` unchanged during collection.
JSON writes protect the previous checkpoint if replacement fails; unsaved events
can still be lost on a crash.

## Code and validation

Each folder contains its study script, `Stimuli/` and participant `Data/`.
Shared participant/display checks, safe saving, video breaks and webcam recording
live in `utils/`. Keep heavy imports inside the script's main guard: Windows
webcam workers re-run the module; see [VIDEO_WORKER_STARTUP.md](utils/VIDEO_WORKER_STARTUP.md).

The pinned PsychoPy snapshot passed a 54-movie playback diagnostic with every
source frame submitted. Movie presentations were still about 42–63 ms longer
than encoded durations. This is not a substitute for physical audio/video,
keyboard/touch and eye-tracker validation on the collection setup.
