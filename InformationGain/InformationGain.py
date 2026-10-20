from contextlib import ExitStack, nullcontext
from datetime import datetime
from pathlib import Path

# ------------------------------ Helper functions ------------------------------

# The session table: one row per action or event. Unused columns stay None.
COLUMNS = [
    "sequence", "trial", "phase", "action", "stimulus",
    "x", "y", "time_study", "time_trial",
]


def save_event(action, **fields):
    """Append one row of the session table.

    A session or trial marker passes just an action name. A cue or target
    marker also passes its phase, stimulus name and position. The sequence,
    trial and time_trial columns come from the current place in the study,
    unless the caller overrides them.
    """
    row = {name: None for name in COLUMNS}
    now = study_clock.getTime()

    trial = fields.pop("trial", current["trial"])

    row["action"] = action
    row["phase"] = fields.pop("phase", "event")
    row["sequence"] = fields.pop("sequence", current["sequence"])
    row["trial"] = trial
    row["time_study"] = round(now, 3)

    # time_trial runs from the start of the trial, and is null outside one, so
    # that it is null exactly when trial is null.
    time_trial = fields.pop("time_trial", None)
    if time_trial is None and trial is not None:
        time_trial = now - current["trial_start"]
    row["time_trial"] = None if time_trial is None else round(time_trial, 3)

    row.update(fields)
    rows.append(row)

    # Show the event on the video and send it to the eye tracker, so all the
    # records share one vocabulary and line up in time.
    if etracker is not None:
        etracker.record_event(action)
    if recorder is not None:
        recorder.send_text(action)


def save_data(subject_dir):
    """Rewrite the participant file, so a stop or crash loses nothing.

    The dump goes to a temporary file first: if anything fails part-way (a
    stray NaN, a full disk), the previous good file is left untouched.
    """
    data = {"metadata": session, "columns": COLUMNS, "rows": rows}

    write_json(subject_dir / f"{subject_id}.json", data)


def pause_study(win):
    """Space resumes; Esc stops. Return True when the operator chooses to stop."""
    print("Study paused. Space = continue; Esc = stop.", flush=True)
    save_event("pause", phase="pause")

    background.draw()
    visual.TextStim(
        win,
        text="Paused\n\nSpace = continue\nEsc = stop",
        color="black", height=40, units="pix",
    ).draw()
    win.flip()

    event.clearEvents(eventType="keyboard")
    keys = event.waitKeys(keyList=["space", "escape"])
    background.draw()
    win.flip()  # clear the message before returning to the task

    print("Stopping study..." if "escape" in keys else "Continuing study.", flush=True)
    return "escape" in keys


def ask_continue():
    """Show the pause screen, and quit the session if asked to stop."""
    if pause_study(win):
        finish_study(stopped=True)
        core.quit()


def show_end():
    """Show 'The End!' for ten seconds, then let the study close."""
    visual.TextStim(win, text="The End!", color="black", height=100,
                    units="pix").draw()
    win.flip()
    core.wait(10)


def check_keys():
    """Check the experimenter's keyboard input.

    Space records a look-away, x cancels it, and Esc asks whether to stop.
    """
    global track_time, cancel_time

    keys = event.getKeys(keyList=["space", "x", "escape"])

    # Record only the first space press for this look-away
    if "space" in keys and not track_time:
        track_time.append(core.getTime())
        save_event("lookaway", phase="lookaway")

    # Cancel a look-away that was recorded by mistake
    if "x" in keys:
        cancel_time = core.getTime()

        if track_time:
            save_event("lookaway_cancel", phase="lookaway")

    # Ask whether to keep going or stop
    if "escape" in keys:
        ask_continue()


def check_lookaway():
    """Check whether the infant has looked away for one second.

    If so, show the background and wait for the experimenter to press space.
    Return 1 to end the sequence, otherwise 0.
    """
    global track_time, cancel_time

    # No look-away has been recorded
    if not track_time:
        cancel_time = 0
        return 0

    # Cancel a look-away if x was pressed within one second
    if cancel_time > 0:
        if track_time[0] <= cancel_time <= track_time[0] + LOOKAWAY_SECS:
            track_time = []

        cancel_time = 0

    # Continue if cancelled or if the look-away has not lasted long enough
    if not track_time:
        return 0

    if core.getTime() - track_time[0] < LOOKAWAY_SECS:
        return 0

    # Tell the experimenter what happens next
    if sequence_number < sequence_count:
        print(f"Look-away criterion met. Space = start sequence {sequence_number + 1}; Esc = pause.", flush=True)
    else:
        print("Look-away criterion met. Space = finish; Esc = pause.", flush=True)

    # Clear the stimulus and reset the look-away times
    background.draw()
    win.flip()
    track_time = []
    cancel_time = 0

    # Wait for the experimenter to continue, or to stop the session
    if "escape" in event.waitKeys(keyList=["space", "escape"]):
        ask_continue()

    return 1


def show_background(duration, phase, action):
    """Show the background for the matching number of 60 Hz refreshes.

    The first flip ends the previous stimulus and starts the gap. The next
    stimulus flip ends the gap. Return 1 if a look-away ends the sequence.
    """
    global timing_issue

    save_in_gap = action == "target_end" and etracker is not None
    index = 0
    deadline = None
    while True:
        if save_in_gap:
            if deadline is not None and study_clock.getTime() >= deadline:
                break
        elif index >= round(duration * REFRESH_HZ):
            break
        background.draw()
        win.flip()

        if index == 0:
            if save_in_gap:
                deadline = study_clock.getTime() + duration
            if phase in ("cue", "target"):
                elapsed = study_clock.getTime() - current["stimulus_start"]
                expected = CUE_SECS if phase == "cue" else TARGET_SECS
                if abs(elapsed - expected) > TIMING_TOLERANCE:
                    timing_issue = True

            save_event(action, phase=phase)

        check_keys()
        if check_lookaway():
            return 1

        if index == 0 and save_in_gap:
            # Saving uses part of the ITI, rather than adding another wait.
            save_data(subject_dir)
            etracker.save_data()
            check_keys()
            if check_lookaway():
                return 1
        index += 1

    return 0


def show_stimulus(stimulus, name, location, phase):
    """Draw each animation image once, one image per monitor refresh.

    No extra wait: win.flip() paces the animation. The following background
    flip ends the last image. Return 1 if a look-away ends the sequence.
    """
    for index, image in enumerate(stimulus):
        image.pos = location
        background.draw()
        image.draw()
        win.flip()

        if index == 0:
            current["stimulus_start"] = study_clock.getTime()
            save_event(phase + "_start", phase=phase, stimulus=name,
                       x=float(location[0]), y=float(location[1]))

        check_keys()
        if check_lookaway():
            return 1

    return 0


def finish_study(stopped):
    """Mark the session finished and write the data file.

    Used both when the study ends on its own and when the experimenter stops
    it with Esc while it is running.
    """
    save_event("study_stopped" if stopped else "study_end", phase="session",
               sequence=None, trial=None)

    session["completed"] = not stopped
    session["ended"] = datetime.now().isoformat(timespec="seconds")
    session["timing_issue"] = bool(timing_issue)

    background_sound.stop()
    save_data(subject_dir)

    print(f"Study {'stopped early' if stopped else 'completed'}. Data saved to {subject_dir}.", flush=True)
    if timing_issue:
        print("WARNING: some cues or targets differed from their expected "
              f"duration by more than {TIMING_TOLERANCE} seconds.", flush=True)


# ------------------------------ Settings and paths ------------------------------

etracker = None

## Paths
study_dir = Path("InformationGain")

data_dir = study_dir / "Data"
stimuli_dir = study_dir / "Stimuli"

# Window size in pixels, matching the eye-tracking display

# Where the cue appears: the centre of the screen
cue_loc = [0, 0]

# One image per refresh: 60 cue images = 1 s; 90 target images = 1.5 s.
REFRESH_HZ = 60
CUE_SECS = 1.0
TARGET_SECS = 1.5
TIMING_TOLERANCE = 0.1

# How long the infant may look away before the sequence is abandoned
LOOKAWAY_SECS = 1

## Background-only periods, in seconds
START_SECS = 1.5
ISI_SECS = 0.75
ITI_SECS = 0.75

# Set while a session records, so save_event can also write to the video.
recorder = None


# ------------------------------ Run ------------------------------

if __name__ == "__main__":
    from utils.display_settings import enable_native_pixels

    enable_native_pixels()
    # Imports
    # The webcam worker re-runs this file; it does not need the study libraries.
    import numpy as np
    import pandas as pd
    import psychopy
    from psychopy import core, event, sound, visual
    from psychopy.hardware.speaker import SpeakerDevice

    from utils.subject_selection import get_participant
    from utils.data_saving import write_json
    from utils.display_settings import DisplaySettings

    # Participant setup
    display = DisplaySettings.detect(preferred=1)
    subject_id, subjnum, recording, tracker_checked, recalibrate = get_participant(
        data_dir, recording=True, eye_tracker=True, display=display,
    )
    subject_dir = data_dir / subject_id

    print(f"Preparing InformationGain for participant {subject_id}.", flush=True)

    # Prepare study sequence
    # One row per trial, one column per sequence.
    sequences = pd.read_csv(stimuli_dir / "sequences_t.csv", header=None).transpose()
    sequence_count = len(sequences.columns)

    # Fixed pixel positions for the 1920 × 1080 layout, relative to screen center.
    targ_loc = np.array([
        [-576, 324],
        [576, 324],
        [-576, -324],
        [576, -324],
    ])

    # Rotate them with the participant number, so that over participants every
    # sequence is presented equally often in every position
    if subjnum in list(range(1, 1000, 4)):
        targ_loc = np.array([targ_loc[3], targ_loc[0], targ_loc[2], targ_loc[1]])
    elif subjnum in list(range(2, 1000, 4)):
        targ_loc = np.array([targ_loc[1], targ_loc[2], targ_loc[3], targ_loc[0]])
    elif subjnum in list(range(3, 1000, 4)):
        targ_loc = np.array([targ_loc[0], targ_loc[3], targ_loc[1], targ_loc[2]])
    elif subjnum in list(range(4, 1000, 4)):
        targ_loc = np.array([targ_loc[2], targ_loc[1], targ_loc[0], targ_loc[3]])

    # Window and stimuli
    # Registered cleanup runs on normal exit, Esc, or an exception (last added first).
    with ExitStack() as cleanup:
        win = visual.Window(
            size=display.size, screen=display.screen, fullscr=True,
            color="black", units="pix", waitBlanking=True,
        )
        cleanup.callback(win.close)

        ## Session bookkeeping
        # One row per action or event, rewritten to disk after every trial
        rows = []
        study_clock = core.Clock()
        # Where we are in the study, so save_event can stamp rows without being told
        current = {"sequence": None, "trial": None, "trial_start": 0.0,
                   "stimulus_start": None}
        # 0 until the first sequence starts, so that a look-away during the opening
        # background is reported as sequence 1
        sequence_number = 0
        # Look-away tracking, updated by check_keys and check_lookaway
        track_time = []
        cancel_time = 0
        timing_issue = False

        session = {
            "subject": subject_id,
            "study": "InformationGain",
            "psychopy": psychopy.__version__,
            "window_size": [int(win.size[0]), int(win.size[1])],
            "display": display.metadata(win),
            "started": datetime.now().isoformat(timespec="seconds"),
            "ended": None,
            "completed": False,
            "timing_issue": False,
        }
        save_data(subject_dir)

        ## Stimuli
        background = visual.ImageStim(win, units="pix", size=(1920, 1080),
                                      image=str(stimuli_dir / "background.jpg"))
        speaker = SpeakerDevice(index=13)  # lab machine only
        background_sound = sound.Sound(str(stimuli_dir / "hothothot_long.wav"),
                                       speaker=speaker, volume=1.0)
        cleanup.callback(background_sound.stop)

        # Images: the folders come in numbered cue/target pairs, 01_StarCue,
        # 01_StarTarget, 02_TrefoilCue, ...
        IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
        stimulus_dirs = sorted(d for d in stimuli_dir.iterdir() if d.is_dir())
        stimulus_names = [directory.name for directory in stimulus_dirs]
        assert len(stimulus_dirs) == 2 * sequence_count, \
            "expected one cue and one target folder per sequence"

        stimuli = [
            [
                visual.ImageStim(win, units="pix",
                                 size=(200, 200),
                                 image=str(image))
                for image in sorted(directory.iterdir())
                if image.suffix.lower() in IMAGE_SUFFIXES
            ]
            for directory in stimulus_dirs
        ]
        for index, animation in enumerate(stimuli):
            seconds = CUE_SECS if index % 2 == 0 else TARGET_SECS
            assert len(animation) == round(seconds * REFRESH_HZ), \
                f"unexpected image count in {stimulus_names[index]}"

        if tracker_checked:
            from DeToX import ETracker

            etracker = ETracker(win)
            etracker.show_status()
            if recalibrate:
                etracker.calibrate()

        # Start screen
        print(f"Ready: participant {subject_id}. Space = start.", flush=True)
        print("During trials: Space = mark look-away; X = cancel within 1 s; Esc = pause.", flush=True)
        event.clearEvents(eventType="keyboard")
        event.waitKeys(keyList=["space"])

        # Recording starts after the start screen and stops before the end screen.
        recorder_ctx = nullcontext()
        if recording:
            from utils.video_recording.webcam_recorder import WebcamRecorder
            recorder_ctx = WebcamRecorder.for_subject(subject_dir)

        with recorder_ctx as recorder, ExitStack() as gaze_cleanup:
            if etracker is not None:
                gaze_cleanup.callback(etracker.stop_recording)
                etracker.start_recording(str(subject_dir / f"{subject_id}_gaze.h5"))
            if recorder is not None and recorder.last_error:
                print(f"WARNING: no video this session: {recorder.last_error}", flush=True)

            print("Study started. Esc = pause.", flush=True)
            save_event("study_start", phase="session")
            background_sound.play()
            show_background(START_SECS, "background", "background_start")

            # Study loop
            for sequence_number, column in enumerate(sequences, start=1):
                cue_idx = 2 * (sequence_number - 1)
                trials_in_sequence = len(sequences[column])
                current["sequence"] = sequence_number
                current["trial"] = None
                save_event("sequence_start", phase="sequence")
                print(f"Sequence {sequence_number}/{sequence_count} started.", flush=True)

                for trial_number, location_index in enumerate(sequences[column], start=1):
                    current["trial"] = trial_number
                    current["trial_start"] = study_clock.getTime()
                    save_event("trial_start", phase="trial")

                    # Cue, its ISI, target, its ITI. The ISI flip is the moment the
                    # cue disappears, and the ITI flip the moment the target does,
                    # so those two flips mark the ends instead of separate events.
                    # A look-away in any of them ends the sequence.
                    looked_away = show_stimulus(stimuli[cue_idx],
                                                stimulus_names[cue_idx],
                                                cue_loc, "cue")
                    if not looked_away:
                        looked_away = show_background(ISI_SECS, "cue", "cue_end")
                    if not looked_away:
                        looked_away = show_stimulus(stimuli[cue_idx + 1],
                                                    stimulus_names[cue_idx + 1],
                                                    targ_loc[location_index - 1],
                                                    "target")
                    if not looked_away:
                        looked_away = show_background(ITI_SECS, "target", "target_end")

                    save_event("trial_aborted" if looked_away else "trial_end", phase="trial")
                    if etracker is None or looked_away:
                        save_data(subject_dir)
                        if etracker is not None:
                            etracker.save_data()
                    if looked_away:
                        break

                current["trial"] = None
                save_event("sequence_end", phase="sequence")
                if trial_number == trials_in_sequence:
                    if sequence_number < sequence_count:
                        print("Sequence ended. Space = start the next sequence; Esc = pause.", flush=True)
                    else:
                        print("Final sequence ended. Space = finish; Esc = pause.", flush=True)
                    if "escape" in event.waitKeys(keyList=["space", "escape"]):
                        ask_continue()

            # Final save and cleanup
            finish_study(stopped=False)

        # The video file is closed here.
        show_end()
