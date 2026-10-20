from contextlib import ExitStack, nullcontext
import csv
from itertools import groupby
from pathlib import Path

# ------------------------------ Helper functions ------------------------------

def load_sequence(csv_path, subject_id):
    """Read this subject's saved order, without sorting or randomizing it."""
    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = [row for row in csv.DictReader(file) if row["subject_id"] == subject_id]
    if len(rows) != N_BLOCKS * 18:
        raise ValueError(f"{subject_id} needs 54 movie rows in {csv_path}; found {len(rows)}")
    seed = int(rows[0]["seed"])
    for index, row in enumerate(rows):
        if (int(row["block"]), int(row["trial"])) != (index // 18 + 1, index % 18 + 1):
            raise ValueError(f"Invalid block/trial order for {subject_id} in {csv_path}")
        if int(row["seed"]) != seed:
            raise ValueError(f"Inconsistent seed for {subject_id} in {csv_path}")
        video = Path(row["video"])
        if video.is_absolute() or ".." in video.parts:
            raise ValueError(f"Expected a relative stimulus path: {video}")
        if not (stimuli_dir / video).is_file():
            raise FileNotFoundError(stimuli_dir / video)

    blocks = []
    for block_number, block_rows in groupby(rows, key=lambda row: int(row["block"])):
        categories = []
        for name, category_rows in groupby(block_rows, key=lambda row: row["category"]):
            categories.append({"name": name, "videos": [row["video"] for row in category_rows]})
        blocks.append({"block": block_number, "categories": categories})
    return {"subject_id": subject_id, "random_seed": seed, "blocks": blocks, "events": []}, rows


def save_event(trigger, block=None, trial=None, video=None):
    events.append({
        "time": study_clock.getTime(),
        "trigger": trigger,
        "block": block,
        "trial": trial,
        "video": video,
    })
    # Add eye-tracker trigger sending here later.
    # Mirror the same event onto the recorded video, when recording is on.
    if etracker is not None:
        etracker.record_event(trigger)
    if recorder is not None:
        recorder.send_text(trigger)


def save_data(subject_dir):
    """Save the planned blocks and events, retaining this study's JSON settings."""
    write_json(subject_dir / f"{subject_id}_sequence.json", sequence, allow_nan=True)


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
    win.flip()  # Remove the instructions before loading the next video.
    print("Stopping study..." if "escape" in keys else "Continuing study.", flush=True)
    return "escape" in keys


def prepare_block(win, block, movie_cleanup):
    """On a black screen, unload the old block and prepare the next one."""
    win.clearBuffer()
    win.flip()
    movie_cleanup.close()
    trials = []
    for category in block["categories"]:
        for filename in category["videos"]:
            background = visual.Rect(
                win, width=win.size[0], height=win.size[1], units="pix",
                fillColor=MOVIE_BACKGROUNDS.get(category["name"], "black"), lineColor=None,
            )
            movie = visual.MovieStim(
                win, filename=str(stimuli_dir / filename), units="pix", autoStart=False,
            )
            movie_cleanup.callback(movie.unload)
            # PsychoPy 2025.1.1 defaults to a square, not the movie's dimensions.
            # Relations fitted the original 1920 x 1080 screen; keep that size.
            movie.size = (1920, 1080) if category["name"] == "Relations" else movie.frameSize
            trials.append((category["name"], filename, movie, background))

    # Upload the initial frames while paused, without showing these previews.
    for category_name, filename, movie, background in trials:
        background.draw()
        movie.draw()
    win.clearBuffer()
    win.flip()
    return trials


def play_video(win, movie, background, block_number, trial_number):
    """Play a prepared movie fully. Esc queues a pause at its end."""
    video_name = Path(movie.filename).name
    pause_requested = False
    started = False
    event.clearEvents(eventType="keyboard")
    try:
        movie.play()
        while not movie.isFinished:
            background.draw()
            movie.draw()
            # MovieStim returns True from draw(); check
            # decoded frame availability so a blank startup flip is not onset.
            first_frame = not started and movie._recentFrame is not None
            if first_frame:
                win.callOnFlip(save_event, "video_onset", block_number, trial_number, video_name)
                started = True
            win.flip()
            if event.getKeys(keyList=["escape"]):
                pause_requested = True

        win.callOnFlip(save_event, "video_offset", block_number, trial_number, video_name)
        win.flip()  # Clear the final image and timestamp that flip.
    finally:
        # A finished but unpaused player can interfere with the next movie's clock.
        # Keep it allocated until the next block, but stop its playback now.
        movie.pause()
    return pause_requested


# ------------------------------ Settings and paths ------------------------------

etracker = None

## Paths
# Works both as a script and when running cells in a notebook.
study_dir = Path("WhatBabiesKnow")

data_dir = study_dir / "Data"
stimuli_dir = study_dir / "Stimuli"

## General
N_BLOCKS = 3
MOVIE_BACKGROUNDS = {"GazeFollowing": "#EDEDED", "Geometry": "#FFFFFF"}


# Set while a session records, so save_event can also write to the video.
recorder = None

# ------------------------------ Run ------------------------------

if __name__ == "__main__":
    from utils.display_settings import enable_native_pixels

    enable_native_pixels()
    # Imports
    # The webcam worker re-runs this file; it does not need the study libraries.
    from psychopy import visual, core, event

    from utils.subject_selection import get_participant
    from utils.data_saving import write_json
    from utils.pause_video import show_pause_video
    from utils.display_settings import DisplaySettings

    # Participant setup
    display = DisplaySettings.detect()
    subject_id, subjnum, recording, tracker_checked, recalibrate = get_participant(
        data_dir, recording=True, eye_tracker=True, display=display,
    )

    # The participant dialog has already created this folder after its checks.
    subject_dir = data_dir / subject_id

    print(f"Preparing WhatBabiesKnow for participant {subject_id}.", flush=True)


    # Load the assigned schedule and preserve the exact CSV rows with the data.
    sequence, rows = load_sequence(stimuli_dir / "sequences.csv", subject_id)
    events = sequence["events"]
    with (subject_dir / f"{subject_id}_sequence.csv").open("x", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    # Save the planned order before opening the window.
    sequence_path = subject_dir / f"{subject_id}_sequence.json"
    save_data(subject_dir)

    print(f"Saved sequence to {sequence_path}", flush=True)


    # Window and stimuli

    # Registered cleanup runs on normal exit, Esc, or an exception (last added first).
    with ExitStack() as cleanup:
        win = visual.Window(
            size=display.size, screen=display.screen, fullscr=True,
            color="black", units="pix",
        )
        cleanup.callback(win.close)
        sequence["display"] = display.metadata(win)
        save_data(subject_dir)
        movie_cleanup = ExitStack()
        cleanup.callback(movie_cleanup.close)

        if tracker_checked:
            from DeToX import ETracker

            etracker = ETracker(win)
            etracker.show_status()
            if recalibrate:
                etracker.calibrate()

        # Prepare block 1 before offering to start the study.
        trials = prepare_block(win, sequence["blocks"][0], movie_cleanup)

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
            study_clock = core.Clock()
            sequence["time_reference"] = "Seconds since first block started, including pauses and video loading"
            stop_requested = False
            print("Study started. After the current video: Esc = pause; X = video break.", flush=True)
            save_event("study_start")

            for block in sequence["blocks"]:
                if block["block"] > 1:
                    print(f"Preparing block {block['block']}/{N_BLOCKS}...", flush=True)
                    trials.clear()
                    trials = prepare_block(win, block, movie_cleanup)
                    print(f"Waiting to start block {block['block']}/{N_BLOCKS}.", flush=True)
                    stop_requested = pause_study(win)
                    if stop_requested:
                        break

                save_event("block_start", block["block"])
                print(f"Block {block['block']}/{N_BLOCKS} started.", flush=True)
                for trial_number, (category_name, filename, movie, background) in enumerate(trials, start=1):
                    print(f"Block {block['block']}/{N_BLOCKS} | Video {trial_number}/{len(trials)} | {category_name}", flush=True)
                    pause_requested = play_video(win, movie, background, block["block"], trial_number)
                    video_pause_requested = "x" in event.getKeys(keyList=["x"])
                    if etracker is not None:
                        etracker.save_data()
                    if pause_requested:
                        stop_requested = pause_study(win)
                    elif video_pause_requested:
                        show_pause_video(win, save_event)
                    if stop_requested:
                        break
                save_event("block_stopped" if stop_requested else "block_end", block["block"])
                print(f"Block {block['block']} {'stopped early' if stop_requested else 'completed'}.", flush=True)
                save_data(subject_dir)
                if stop_requested:
                    break

            # Final save and cleanup
            save_event("study_stopped" if stop_requested else "study_end")
            save_data(subject_dir)
            print(f"Study {'stopped early' if stop_requested else 'completed'}. Data saved to {sequence_path}.", flush=True)

    core.quit()
