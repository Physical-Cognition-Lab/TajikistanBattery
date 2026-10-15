from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd
import psychopy
from psychopy import core, event, gui, sound, visual
from psychopy.hardware.speaker import SpeakerDevice

from video_recording.webcam_recorder import WebcamRecorder


#----------------------------- Functions  ---------------------------------------------

def get_participant(data_dir):
    # Create the data folder if it does not exist
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Find participant folders such as S001 and S002
    existing = [
        folder.name
        for folder in data_dir.iterdir()
        if folder.is_dir()
        and folder.name.startswith("S")
        and folder.name[1:].isdigit()
    ]

    # Remove the "S" and turn the remaining text into numbers
    numbers = [int(name[1:]) for name in existing]

    # Suggest the highest number + 1, or 1 if there are no participants
    next_number = max(numbers, default=0) + 1

    # Keep asking until a valid, unused number is entered
    while True:
        dlg = gui.Dlg(title="StatLearning", alwaysOnTop=True)
        dlg.addField("Participant number:", initial=str(next_number))
        # Remove the message about asterisks
        dlg.requiredMsg.setText("")
        selection = dlg.show()

        # End the script if the user clicks Cancel
        if not dlg.OK:
            core.quit()

        # Check that the answer is a positive whole number
        try:
            subjnum = int(selection[0])

            if subjnum < 1:
                raise ValueError

        except (ValueError, TypeError):
            message = "Please enter a positive whole number."

        else:
            # Format the number: 1 becomes S001, 12 becomes S012
            subject_id = f"S{subjnum:03d}"

            # Return both versions if this participant does not exist
            if subjnum not in numbers:
                return subject_id, subjnum

            message = f"{subject_id} already exists. Choose another number."

        # Explain the problem before showing the entry dialog again
        warning = gui.Dlg(title="Check participant number")
        warning.addText(message)
        warning.show()


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
    if recorder is not None:
        recorder.send_text(action)
    # etracker.record_event(action)   # added with DeToX


def save_data(subject_dir):
    """Rewrite the participant file, so a stop or crash loses nothing.

    The dump goes to a temporary file first: if anything fails part-way (a
    stray NaN, a full disk), the previous good file is left untouched.
    """
    data = {"metadata": session, "columns": COLUMNS, "rows": rows}

    path = subject_dir / f"{subject_id}.json"
    tmp = subject_dir / f"{subject_id}.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, allow_nan=False)
    tmp.replace(path)


def show_message(text):
    """Draw a message over the background and wait. Space continues, Esc quits."""
    background.draw()
    visual.TextStim(win, text=text, color="black", height=40, units="pix").draw()
    win.flip()

    event.clearEvents(eventType="keyboard")
    if "escape" in event.waitKeys(keyList=["space", "escape"]):
        win.close()
        core.quit()


def get_bar():
    """Check the experimenter's keyboard input.

    Space records a look-away, x cancels it, and q asks to quit.
    """
    global track_time, cancel_time

    keys = event.getKeys(keyList=["space", "x", "q"])

    # Record only the first space press for this look-away
    if "space" in keys and not track_time:
        track_time.append(core.getTime())
        save_event("lookaway", phase="lookaway")

    # Cancel a look-away that was recorded by mistake
    if "x" in keys:
        cancel_time = core.getTime()

        if track_time:
            save_event("lookaway_cancel", phase="lookaway")

    # Ask for confirmation before ending the session
    if "q" in keys:
        DlgQuit.show()

        if DlgQuit.OK:
            finish_study(stopped=True)
            win.close()
            print("Testing session ended")
            core.quit()


def goto_next():
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
        print("Look-away criterion met. Press space to start sequence "
              f"{sequence_number + 1}.")
    else:
        print("END OF THE STUDY! Press space to close.")

    # Clear the stimulus and reset the look-away times
    background.draw()
    win.flip()
    track_time = []
    cancel_time = 0

    # Wait for the experimenter to continue
    event.waitKeys(keyList=["space"])

    return 1


def show_background(duration, phase, action):
    """Show only the background for duration seconds, checking the keyboard.

    `action` names the moment this flip marks: the opening background, or the
    end of the cue or the target. The marker is recorded just after the flip,
    so it lines up with the moment the background appears. Return 1 if the
    sequence must end here, otherwise 0.
    """
    background.draw()
    win.flip()
    save_event(action, phase=phase)

    clock = core.Clock()

    while clock.getTime() < duration:
        get_bar()
        if goto_next():
            return 1

        # Brief pause to reduce CPU use
        core.wait(0.001)

    return 0


def show_stimulus(stimulus, name, location, duration, phase):
    """Show an animation over the background at the given location.

    Each image is flipped on for about `duration` seconds. Both cue and target
    are around one monitor refresh, so the refresh rate is what actually paces
    the animation. The start marker is recorded after the first flip, when the
    stimulus appears. Return 1 if the sequence must end here, otherwise 0.
    """
    for image in stimulus:
        image.pos = location

    for index, image in enumerate(stimulus):
        background.draw()
        image.draw()
        win.flip()

        if index == 0:
            save_event(phase + "_start", phase=phase, stimulus=name,
                       x=float(location[0]), y=float(location[1]))

        clock = core.Clock()

        while clock.getTime() < duration:
            get_bar()
            if goto_next():
                return 1

            core.wait(0.001)

    return 0


def finish_study(stopped):
    """Mark the session finished and write the data file.

    Used both when the study ends on its own and when the experimenter quits
    with q while it is running.
    """
    save_event("study_stopped" if stopped else "study_end", phase="session",
               sequence=None, trial=None)

    session["completed"] = not stopped
    session["ended"] = datetime.now().isoformat(timespec="seconds")
    session["timing_issue"] = bool(timing_issue)

    hothothot.stop()
    save_data(subject_dir)

    print(f"Saved {len(rows)} rows for {subject_id} to {subject_dir}", flush=True)
    if timing_issue:
        print("WARNING: some target presentations were outside "
              f"{TARGET_SECS - TARGET_TOLERANCE}-"
              f"{TARGET_SECS + TARGET_TOLERANCE} seconds.")


#----------------------------- Settings ---------------------------------------------

## Paths
StudyPath = Path("InformationGain")

data_dir = StudyPath / "Data"
stimuli_dir = StudyPath / "Stimuli"

# Window size in pixels, matching the eye-tracking display
winsize = 1280, 720

# Where the cue appears: the centre of the screen
cue_loc = [0, 0]

# Requested on-screen time for each animation image. Both are around one
# monitor refresh, so the refresh rate rounds them up and paces the animation:
# at 60 Hz the 45-frame cue and the 90-frame target each last about 1.5 s.
cue_time = 0.0188
targ_time = 0.0118

# What a target presentation should last at 60 Hz, and how far it may drift
# before it is flagged
TARGET_SECS = 1.5
TARGET_TOLERANCE = 0.1

# How long the infant may look away before the sequence is abandoned
LOOKAWAY_SECS = 1

## Background-only periods, in seconds
START_SECS = 1.5
ISI_SECS = 0.75
ITI_SECS = 0.75

# Set up in the run below; None until then, so save_event can always ask.
recorder = None


#----------------------------- Run ---------------------------------------------

if __name__ == "__main__":

    ## Subject
    subject_id, subjnum = get_participant(data_dir)
    subject_dir = data_dir / subject_id

    print(f"Testing is starting for participant {subject_id}")

    # Dialog shown when the experimenter presses q during the study
    DlgQuit = gui.Dlg(title="End testing session?")
    DlgQuit.addText("Press OK to quit, or Cancel to continue.")

    ## Target positions
    # Four positions, one per screen quadrant
    targ_loc = np.array([
        [-(winsize[0] * .8 - winsize[0] / 2), winsize[1] * .8 - winsize[1] / 2],
        [winsize[0] * .8 - winsize[0] / 2, winsize[1] * .8 - winsize[1] / 2],
        [-(winsize[0] * .8 - winsize[0] / 2), -(winsize[1] * .8 - winsize[1] / 2)],
        [winsize[0] * .8 - winsize[0] / 2, -(winsize[1] * .8 - winsize[1] / 2)],
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

    ## Window
    win = visual.Window(winsize, screen=1, fullscr=False, color=(1, 1, 1),
                        units="pix")

    ## Session bookkeeping
    # One row per action or event, rewritten to disk after every trial
    rows = []
    study_clock = core.Clock()

    # Where we are in the study, so save_event can stamp rows without being told
    current = {"sequence": None, "trial": None, "trial_start": 0.0}

    # 0 until the first sequence starts, so that a look-away during the opening
    # background is reported as sequence 1
    sequence_number = 0

    # Look-away tracking, updated by get_bar and goto_next
    track_time = []
    cancel_time = 0

    # A target presentation outside the expected duration sets this
    timing_issue = False

    # Everything about the session that is not a row
    session = {
        "subject": subject_id,
        "study": "InformationGain",
        "psychopy": psychopy.__version__,
        "window_size": [int(win.size[0]), int(win.size[1])],
        "started": datetime.now().isoformat(timespec="seconds"),
        "ended": None,
        "completed": False,
        "timing_issue": False,
    }

    ## Stimuli
    # One row per trial, one column per sequence
    sequences = pd.read_csv(stimuli_dir / "sequences_t.csv", header=None).transpose()
    sequence_count = len(sequences)

    # The background image
    background = visual.ImageStim(win, units="pix", size=winsize,
                                  image=str(stimuli_dir / "background.jpg"))

    # Sound
    speaker = SpeakerDevice(index=13)  # lab machine only

    hothothot = sound.Sound(str(stimuli_dir / "hothothot_long.wav"),
                            speaker=speaker, volume=1.0)

    # Images: the folders come in numbered cue/target pairs, 01_StarCue,
    # 01_StarTarget, 02_TrefoilCue, ...
    IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
    stimulus_dirs = sorted(d for d in stimuli_dir.iterdir() if d.is_dir())
    stimulus_names = [directory.name for directory in stimulus_dirs]

    # One cue and one target folder per sequence
    assert len(stimulus_dirs) == 2 * sequence_count, \
        "expected one cue and one target folder per sequence"

    stimuli = [
        [
            visual.ImageStim(win, units="pix",
                             size=(200 * winsize[0] / 1920,) * 2,
                             image=str(image))
            for image in sorted(directory.iterdir())
            if image.suffix.lower() in IMAGE_SUFFIXES
        ]
        for directory in stimulus_dirs
    ]

    ## START
    print("_____________________________________________________________")
    print("Ready. Make sure to record video.\nThen press SPACE to start.")
    print("Press SPACE when the infant looks away and x to cancel a mistake,")
    print("SPACE again to start the next sequence, and q to quit.")
    print("_____________________________________________________________")

    event.clearEvents(eventType="keyboard")
    event.waitKeys(keyList=["space"])

    # From here on a run always writes data, so the participant folder can exist
    subject_dir.mkdir(parents=True, exist_ok=True)

    # The recording lives exactly as long as the study: start() here, and stop()
    # is guaranteed on the way out, including when q quits the session.
    with WebcamRecorder.for_subject(subject_dir) as recorder:
        if recorder.last_error:
            print(f"WARNING: no video this session: {recorder.last_error}",
                  flush=True)

        save_event("study_start", phase="session")

        hothothot.play()
        # TODO start the DeToX recording here, before the study begins
        show_background(START_SECS, "background", "background_start")

        ## Experiment loop
        for sequence_number, column in enumerate(sequences, start=1):
            cue_idx = 2 * (sequence_number - 1)
            trials_in_sequence = len(sequences[column])

            current["sequence"] = sequence_number
            current["trial"] = None
            save_event("sequence_start", phase="sequence")
            print(f"Started sequence {sequence_number}!", flush=True)

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
                                            cue_loc, cue_time, "cue")
                if not looked_away:
                    looked_away = show_background(ISI_SECS, "cue", "cue_end")

                if not looked_away:
                    target_start = study_clock.getTime()
                    looked_away = show_stimulus(stimuli[cue_idx + 1],
                                                stimulus_names[cue_idx + 1],
                                                targ_loc[location_index - 1],
                                                targ_time, "target")
                    target_secs = study_clock.getTime() - target_start
                    if not (TARGET_SECS - TARGET_TOLERANCE
                            <= target_secs <= TARGET_SECS + TARGET_TOLERANCE):
                        timing_issue = True

                if not looked_away:
                    looked_away = show_background(ITI_SECS, "target", "target_end")

                save_event("trial_aborted" if looked_away else "trial_end",
                           phase="trial")
                save_data(subject_dir)

                if looked_away:
                    break

            current["trial"] = None
            save_event("sequence_end", phase="sequence")

            if trial_number == trials_in_sequence:
                if sequence_number < sequence_count:
                    print("Sequence has ended. Press the bar to start the next one.")
                else:
                    print("END OF THE STUDY! Press the bar to close.")
                event.waitKeys(keyList=["space"])

        ## STOP
        finish_study(stopped=False)

    # The video file is closed here.
    show_message("The End!\n\nPress SPACE to close.")
    win.close()
