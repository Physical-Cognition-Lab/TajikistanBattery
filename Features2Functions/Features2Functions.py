"""Features2Functions - still pictures of objects, 5 s each, attention getter in between.

A modern version of the old "Blob" study: infants look at 18 objects
(6 familiar, 6 familiar to adults only, 6 unfamiliar), all photographed on an
orange background, while we later want to know which parts they look at.

Run from the repository root:
    pixi run features-to-functions

The object set and the exact stimulus order for every subject come from
Stimuli/participant_assignments.csv, written before data collection;
see tools/make_participant_assignments.py.
"""

from contextlib import ExitStack, nullcontext
import csv
from pathlib import Path


# ------------------------------ Helper functions ------------------------------

def get_assignment_row(subject_id):
    """Return this subject's row of the randomisation schedule."""
    if not assignments_file.exists():
        print(f"No participant assignments file: {assignments_file}")
        print("Write one with:")
        print("  pixi run python Features2Functions/tools/make_participant_assignments.py")
        core.quit()

    with assignments_file.open(encoding="utf-8", newline="") as log:
        schedule = {row["subject"]: row for row in csv.DictReader(log)}

    if subject_id not in schedule:
        print(f"{subject_id} is not in {assignments_file}, which holds {len(schedule)} subjects.")
        print("Add more with:")
        print("  pixi run python Features2Functions/tools/make_participant_assignments.py --subjects 300")
        core.quit()

    return schedule[subject_id]


def attention_getter(ag_start_index, trial_number):
    """Attention getters cycle, starting from this subject's starting one."""
    return ATTENTION_GETTERS[(ag_start_index + trial_number - 1) % len(ATTENTION_GETTERS)]


def save_event(trigger, trial=None, stimulus=None):
    events.append({
        "time": study_clock.getTime(),
        "trigger": trigger,
        "trial": trial,
        "stimulus": stimulus,
    })
    # Add eye-tracker trigger sending here later.
    # Mirror the same event onto the recorded video, when recording is on.
    if etracker is not None:
        etracker.record_event(trigger)
    if recorder is not None:
        recorder.send_text(trigger)


def save_data(subject_dir):
    """Save the planned sequence and events without changing the file format."""
    write_json(subject_dir / f"{subject_id}_sequence.json", sequence)


def pause_study(win):
    """Space resumes; Esc stops. Return True when the operator chooses to stop."""
    print("Study paused. Space = continue; Esc = stop.", flush=True)
    save_event("pause")
    visual.TextStim(
        win,
        text="Paused\n\nPress Space to continue\nPress Esc to stop the study",
        color="white", height=36, wrapWidth=900,
    ).draw()
    win.flip()
    event.clearEvents(eventType="keyboard")
    keys = event.waitKeys(keyList=["space", "escape"])
    win.flip()  # Remove the instructions before the next stimulus.
    print("Stopping study..." if "escape" in keys else "Continuing study.", flush=True)
    return "escape" in keys


def present(win, image_path, seconds, trigger, trial_number, stimulus_name, sound_path=None):
    """Show one picture (optionally with a sound) and log onset and offset."""
    image = visual.ImageStim(
        win,
        image=str(image_path),
        size=(win.size[1] * 1.25, win.size[1]),  # the pictures are 4:3
        units="pix",
    )
    image.draw()

    if sound_path is None:
        stimulus_sound = None
    else:
        stimulus_sound = sound.Sound(str(sound_path))

    try:
        win.callOnFlip(save_event, trigger + "_onset", trial_number, stimulus_name)
        if stimulus_sound is not None:
            win.callOnFlip(stimulus_sound.play)
        win.flip()
        core.wait(seconds)
    finally:
        if stimulus_sound is not None:
            stimulus_sound.stop()
    save_event(trigger + "_offset", trial_number, stimulus_name)


def present_attention_getter(win, movie_path, seconds, trial_number, name, sound_path=None):
    """Play one attention getter for `seconds` and log its onset and offset."""
    size = (win.size[1] * 1.25, win.size[1])  # the getters are 4:3 like the pictures
    movie = visual.MovieStim(
        win,
        filename=str(movie_path),
        size=size,
        units="pix",
        autoStart=False,
    )

    with ExitStack() as cleanup:
        cleanup.callback(movie.unload)
        # PsychoPy's movie drawing leaves a dark hairline down the video's left
        # and right edges. An orange frame hides it against the background.
        edge_frame = visual.Rect(
            win, width=size[0], height=size[1],
            lineColor=ORANGE, lineColorSpace="rgb255",
            fillColor=None, lineWidth=6, units="pix",
        )
        getter_sound = None
        if sound_path is not None:
            getter_sound = sound.Sound(str(sound_path))
            cleanup.callback(getter_sound.stop)

        movie.play()
        win.callOnFlip(save_event, "attention_onset", trial_number, name)
        if getter_sound is not None:
            win.callOnFlip(getter_sound.play)

        # Play for the full attention getter time, or until the clip ends.
        timer = core.Clock()
        while timer.getTime() < seconds and not movie.isFinished:
            movie.draw()
            edge_frame.draw()
            win.flip()

        if getter_sound is not None:
            getter_sound.stop()
        save_event("attention_offset", trial_number, name)


def missing_assets(object_set):
    """Return the files the study needs but cannot find."""
    missing = []

    for names in object_set.values():
        for name in names:
            if not (objects_dir / f"{name}.png").exists():
                missing.append(f"objects/{name}.png")

    for getter in ATTENTION_GETTERS:
        for extension in (".mp4", ".wav"):
            if not (attention_dir / f"{getter}{extension}").exists():
                missing.append(f"attention/{getter}{extension}")

    if not music_files:
        missing.append("music/background.<wav|mp3|ogg>")

    return missing


# ------------------------------ Settings and paths ------------------------------

etracker = None

## Paths
# Works both as a script and when running cells in a notebook.
study_dir = Path("Features2Functions")

data_dir = study_dir / "Data"

stimuli_dir = study_dir / "Stimuli"
objects_dir = stimuli_dir / "objects"
attention_dir = stimuli_dir / "attention"
music_dir = stimuli_dir / "music"

music_files = sorted(music_dir.glob("background.*"))

# The randomisation schedule: one row per subject, written before data collection.
assignments_file = stimuli_dir / "participant_assignments.csv"

### Number of stimuli in a session (from the schedule)
N_TRIALS = 18

### Timing
# Every object stays on the screen for 5 s, as in the old Blob study,
# with a 2 s attention getter before it.
STIMULUS_SECONDS = 5.0
ATTENTION_SECONDS = 2.0

### Stimuli
# The window background is the orange that the objects were photographed on.
# rgb255 passes these straight to the screen, so they match the pictures
# exactly; PsychoPy's default "rgb" space would gamma-correct them.
ORANGE = (248, 169, 122)

# The 18 objects, in three familiarity categories:
# 1 = familiar to infants and adults, 2 = familiar to adults only,
# 3 = unfamiliar to everyone. The two objects that only differ between
# study versions are Bottle1/2 (bottles) or Pacifier1/2 (pacifiers).
CATEGORY_2 = ["Drill", "Horn", "Microscope", "Trowel1", "Trowel2", "Trumpet"]
CATEGORY_3 = ["Object1", "Object3", "Object4", "Object6", "Object7", "Object8"]

OBJECT_SETS = {
    "bottles": {
        "category1": ["Bottle1", "Bottle2", "Cup1", "Cup2", "Keyring", "Spoon"],
        "category2": CATEGORY_2,
        "category3": CATEGORY_3,
    },
    "pacifiers": {
        "category1": ["Pacifier1", "Pacifier2", "Cup1", "Cup2", "Keyring", "Spoon"],
        "category2": CATEGORY_2,
        "category3": CATEGORY_3,
    },
}

# The three attention getters take turns, one before every stimulus. Each one
# is a two second video already drawn on the same orange as the pictures.
ATTENTION_GETTERS = ["spinning_wedge", "shattering_hexagon", "morphing_quarters"]

## General
WIN_SIZE = (1920, 1080)


# Set while a session records, so save_event can also write to the video.
recorder = None

# ------------------------------ Run ------------------------------

if __name__ == "__main__":
    # Imports
    # The webcam worker re-runs this file; it does not need the study libraries.
    from psychopy import visual, core, event, sound

    from utils.subject_selection import get_participant
    from utils.data_saving import write_json
    from utils.pause_video import show_pause_video

    # Participant setup
    subject_id, _, recording, tracker_checked, recalibrate = get_participant(
        data_dir, recording=True, eye_tracker=True,
    )

    # The participant's assignment fixes the object set and
    # the whole order.
    schedule_row = get_assignment_row(subject_id)
    version = schedule_row["object_set"]
    object_set = OBJECT_SETS[version]

    # The participant dialog has already created this folder after its checks.
    subject_dir = data_dir / subject_id

    print(f"Preparing Features2Functions for participant {subject_id} ({version}).", flush=True)

    ## Check the stimulus files
    missing = missing_assets(object_set)
    if missing:
        print("Missing stimulus files:")
        for name in missing:
            print(f"  {name}")
        print("Add these files (see Stimuli/README.md) and run again.", flush=True)
        core.quit()


    # Prepare study sequence

    # The schedule row lists this subject's stimuli by name, in order.
    stimuli = [schedule_row[f"trial_{trial}"] for trial in range(1, N_TRIALS + 1)]

    # Every name has to be an object of this set; the same lookup gives us the
    # familiarity category of each trial.
    category_of = {name: category for category, names in object_set.items() for name in names}
    unknown = [name for name in stimuli if name not in category_of]
    if unknown:
        print(f"{subject_id}'s schedule names objects that are not in the {version} set:")
        for name in unknown:
            print(f"  {name}")
        core.quit()

    order = [(category_of[name], name) for name in stimuli]
    ag_start = ATTENTION_GETTERS.index(schedule_row["ag_start"])

    events = []

    # Register this subject's plan: which stimulus in which order, and which
    # attention getter comes before each one.
    sequence = {
        "subject_id": subject_id,
        "schedule": assignments_file.name,
        "object_set": version,
        "ag_start": schedule_row["ag_start"],
        "stimuli": [
            {
                "trial": trial_number,
                "category": category,
                "stimulus": name,
                "attention_getter": attention_getter(ag_start, trial_number),
            }
            for trial_number, (category, name) in enumerate(order, start=1)
        ],
        "events": events,
    }

    # Save the planned order before opening the window.
    sequence_path = subject_dir / f"{subject_id}_sequence.json"
    save_data(subject_dir)

    print(f"Saved sequence to {sequence_path}", flush=True)


    # Window and stimuli

    # Registered cleanup runs on normal exit, Esc, or an exception (last added first).
    with ExitStack() as cleanup:
        win = visual.Window(WIN_SIZE, fullscr=True, color=ORANGE, colorSpace="rgb255", units="pix")
        cleanup.callback(win.close)

        if tracker_checked:
            from DeToX import ETracker

            etracker = ETracker(win)
            etracker.show_status()
            if recalibrate:
                etracker.calibrate()

        # Start screen
        print(f"Ready: participant {subject_id}. Space = start; Esc = abort.", flush=True)
        visual.TextStim(
            win,
            text=f"Subject ID: {subject_id}\n\nPress Space to start\nPress Esc to abort",
            color="white", height=36, wrapWidth=900,
        ).draw()
        win.flip()
        event.clearEvents(eventType="keyboard")
        keys = event.waitKeys(keyList=["space", "escape"])
        if "escape" in keys:
            print("Study aborted before playback.", flush=True)
            core.quit()
        win.flip()  # Clear the start instructions.

        # Recording
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

            # Study loop
            background_sound = None
            if music_files:
                background_sound = sound.Sound(str(music_files[0]), loops=-1)
                cleanup.callback(background_sound.stop)
                background_sound.play()

            study_clock = core.Clock()
            sequence["time_reference"] = "Seconds since the first event, including pauses and loading"
            stop_requested = False
            print("Study started. After the current trial: Esc = pause; X = video break.", flush=True)
            save_event("study_start")

            for trial_number, (category, name) in enumerate(order, start=1):
                getter = attention_getter(ag_start, trial_number)
                print(f"Trial {trial_number}/{len(order)} | {category} | {name} | {getter}", flush=True)
                save_event("trial_start", trial_number, name)

                # Attention getter, then the object itself.
                present_attention_getter(
                    win, attention_dir / f"{getter}.mp4", ATTENTION_SECONDS, trial_number, getter,
                    sound_path=attention_dir / f"{getter}.wav",
                )
                present(win, objects_dir / f"{name}.png", STIMULUS_SECONDS, "stimulus", trial_number, name)
                save_event("trial_end", trial_number, name)
                if etracker is not None:
                    etracker.save_data()

                # Rewrite the whole file after every trial, so a crash costs one trial.
                save_data(subject_dir)
                # Esc after a trial pauses; a second Esc stops the study.
                keys = event.getKeys(keyList=["escape", "x"])
                if "escape" in keys:
                    stop_requested = pause_study(win)
                    if stop_requested:
                        break
                elif "x" in keys:
                    show_pause_video(win, save_event)

            # Final save and cleanup
            save_event("study_stopped" if stop_requested else "study_end")
            if background_sound is not None:
                background_sound.stop()
            save_data(subject_dir)
            print(f"Study {'stopped early' if stop_requested else 'completed'}. Data saved to {sequence_path}.", flush=True)

    core.quit()
