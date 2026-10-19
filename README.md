# TajikistanBattery

Infant studies prepared for data collection in Tajikistan. The aim is to make
existing studies easy to run and maintain, including at remote sites operated
by non-specialists.

The studies use readable PsychoPy scripts, preserving the established study
designs and behaviour.

## Studies

- [Features2Functions](Features2Functions/README.md) — still pictures of objects, with attention getters.
- [HideAndSeek](HideAndSeek/README.md) — a touchscreen puppet game.
- [InformationGain](InformationGain/README.md) — cue and target animations, with look-away marking.
- [WhatBabiesKnow](WhatBabiesKnow/README.md) — three video blocks using pre-generated subject schedules; see its README for sampling rules, movie timing and event markers.

## Repository structure

Each study has its own folder:

```text
StudyName/
    StudyName.py       study script
    Stimuli/           images, videos and sounds
    Data/              participant folders: S001, S002, ...
```

Shared code lives in `utils/`:

- `subject_selection.py` — participant dialog, options and folder creation.
- `eye_tracker_check.py` — Tobii connection check.
- `pause_video.py` — X-controlled video breaks using `pause.avi` (except InformationGain).
- `data_saving.py` — safe JSON writes shared by the studies.
- `video_recording/` — webcam recording in a separate process.

`pixi.toml` defines the environment and launch commands; `pixi.lock` pins package
versions. The project uses Python 3.10 and PsychoPy 2025.1.1.

## Script structure

Each study stays in one script:

1. **Standard-library imports and helper functions.**
2. **Settings and paths** — stimulus locations, timing and study constants.
3. **Main block** (`if __name__ == "__main__":`) — heavy imports, participant
   selection, session setup, study loop, data saving and cleanup.

Keep PsychoPy, NumPy, pandas and local GUI imports inside the main block.
The webcam worker re-runs the study module, so imports outside it slow down
recording startup. See [VIDEO_WORKER_STARTUP.md](utils/VIDEO_WORKER_STARTUP.md).

Keep changes simple and readable. Shared functionality belongs in `utils/`;
study-specific behaviour stays in the study script.

All studies use `study_dir` and `WIN_SIZE` for their main paths and window size,
`pause_study(win)` (True means stop), and `save_data(subject_dir)`. Each keeps
its own output format; the shared JSON writer protects the previous save if a
new write fails.

Each script uses the standard-library `ExitStack` to register window and sound
cleanup as resources are created. Cleanup also runs on early exits or exceptions;
the webcam recorder keeps its own context-managed shutdown.

## Running a study

Install [pixi](https://pixi.sh), then run from the repository root:

```powershell
pixi run features-to-functions
pixi run hide-and-seek
pixi run information-gain
pixi run what-babies-know
```

The desktop shortcuts in `Shorcuts/` launch the same tasks. The first run may
take longer while pixi installs the environment.

## Participant setup

The shared dialog asks for the participant number, webcam recording and,
where supported, eye tracking with a nested **Recalibrate** option.

- Video and eye tracker default to on in all studies except HideAndSeek.
- HideAndSeek defaults to video off and hides eye-tracker options.
- Recalibrate defaults to on and is enabled only when eye tracker is selected.
- A failed tracker check offers instructions, Retry, Uncheck or Cancel.

The dialog ensures `Data/` exists and creates a new participant folder only
after its checks pass and the operator confirms. Existing participant folders
cannot be reused.

Features2Functions, InformationGain and WhatBabiesKnow use DeToX for positioning,
optional recalibration, gaze recording and event markers. Recording continues
through pauses. See each study README for save timing; real tracking requires
fullscreen on the display configured for the tracker. HideAndSeek has no gaze recording.

## Output

Each participant's files are saved under the study's `Data/Sxxx/` folder:

- Behavioural data as JSON, saved as the study progresses.
- Optional webcam video under `video/`, with event labels and timing files.
- Optional `Sxxx_gaze.h5` containing DeToX gaze data and events (simplified pixels).

See each study's `DATA_FORMAT.md`, where provided, for file details.
