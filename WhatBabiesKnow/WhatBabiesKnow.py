import json
import random
from pathlib import Path
from psychopy import visual, gui, core, event



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
        dlg = gui.Dlg(title="StatLearning",alwaysOnTop = True)
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

def save_event(trigger, block=None, trial=None, video=None):
    events.append({
        "time": study_clock.getTime(),
        "trigger": trigger,
        "block": block,
        "trial": trial,
        "video": video,
    })
    # Add eye-tracker trigger sending here later.


def pause_study(win):
    """Show pause instructions: Space continues, Esc stops."""
    print("Paused: Space = continue, Esc = stop.", flush=True)
    visual.TextStim(
        win,
        text="Paused\n\nPress Space to continue\nPress Esc to stop the study",
        color="white", height=36, wrapWidth=900,
    ).draw()
    win.flip()
    event.clearEvents(eventType="keyboard")
    keys = event.waitKeys(keyList=["space", "escape"])
    win.flip()  # Remove the instructions before loading the next video.
    print("Stop requested." if "escape" in keys else "Continuing.", flush=True)
    return "escape" in keys


def play_video(win, path, block_number, trial_number):
    """Load only this movie; play fully. Esc queues a pause at its end."""
    movie = visual.MovieStim(win, filename=str(path), units="pix", autoStart=False)
    pause_requested = False
    started = False
    event.clearEvents(eventType="keyboard")
    try:
        movie.play()
        while not movie.isFinished:
            movie.draw()
            # MovieStim returns True from draw(); check
            # decoded frame availability so a blank startup flip is not onset.
            first_frame = not started and movie._recentFrame is not None
            if first_frame:
                win.callOnFlip(save_event, "video_onset", block_number, trial_number, path.name)
                started = True
            win.flip()
            if first_frame:
                print(f"  Playing: {path.name} | onset {events[-1]['time']:.3f} s", flush=True)
            if event.getKeys(keyList=["escape"]):
                if not pause_requested:
                    print("  Pause requested; waiting for this video to finish.", flush=True)
                pause_requested = True

        win.callOnFlip(save_event, "video_offset", block_number, trial_number, path.name)
        win.flip()  # Clear the final image and timestamp that flip.
        print(f"  Finished: {path.name} | offset {events[-1]['time']:.3f} s", flush=True)
    finally:
        movie.unload()
    return pause_requested


#----------------------------- Settings, Paths and stimuli  ---------------------------------------------

## Paths
# Works both as a script and when running cells in a notebook.
StudyPath = Path("WhatBabiesKnow")

data_dir = StudyPath / "Data"
stimuli_dir = StudyPath / "Stimuli"

### Stimuli

# name: (files, how many to show per block, sample with replacement?)
CATEGORIES = {
    "GazeFollowing":        (sorted((stimuli_dir / "GazeFollowing").glob("GF_*.mp4")), 3, False),
    "ObjectRepresentation": (sorted((stimuli_dir / "ObjectRepresentations").glob("ObjectRep_*.mp4")), 2, True),
    "ActionPrediction":     (sorted((stimuli_dir / "ActionPrediction").glob("AP_*.mp4")), 2, False),
    "Geometry":             (sorted((stimuli_dir / "Geometry").glob("Geo_*.mp4")), 2, False),
    "ANS_easy":             ([stimuli_dir / "Numerosity/ANS_6_24.mp4", stimuli_dir / "Numerosity/ANS_24_6.mp4"], 2, True),
    "ANS_hard":             ([stimuli_dir / "Numerosity/ANS_6_12.mp4", stimuli_dir / "Numerosity/ANS_12_6.mp4"], 2, True),
    "Attention":            ([stimuli_dir / "AttentionGrabbers/attention2.mp4", stimuli_dir / "AttentionGrabbers/attention3.mp4"], 1, False),
    "Attention2":           ([stimuli_dir / "AttentionGrabbers/attention4.mp4", stimuli_dir / "AttentionGrabbers/attention6.mp4"], 1, False),
    "Attention3":           ([stimuli_dir / "AttentionGrabbers" / f"attention{i}.mp4" for i in (2, 3, 4, 6)], 1, False),
}

# Relations is special: 1 Neutral + 1 Violation per block, order shuffled
RELATION_NEUTRAL = sorted((stimuli_dir / "Relations/01 NATURAL").glob("*.mp4"))
RELATION_VIOLATION = sorted((stimuli_dir / "Relations/02 VIOLATION").glob("*.mp4"))

ALL_CATEGORIES = list(CATEGORIES) + ["Relations"]

## General
N_BLOCKS = 3
WIN_SIZE = (1920, 1080)


# ------------------------------ Subject related settings ---------------------------------------

## Subjects
subject_id, subjnum = get_participant(data_dir)

# Create this participant's folder
subject_dir = data_dir / subject_id
subject_dir.mkdir()

print(f"Testing is starting for participant {subject_id}")


# ------------------------------ Generate and save the sequence ---------------------------------------
# Store participant and seed
random_seed = random.randrange(2**32)
random.seed(random_seed)

events = []
sequence = {
    "subject_id": subject_id,
    "random_seed": random_seed,
    "blocks": [],
    "events": events,
}

for block in range(1, N_BLOCKS + 1):
    category_order = ALL_CATEGORIES.copy()
    random.shuffle(category_order)
    categories = []

    for category in category_order:
        if category == "Relations":
            videos = [
                random.choice(RELATION_NEUTRAL),
                random.choice(RELATION_VIOLATION),
            ]
            random.shuffle(videos)
        else:
            files, count, replace = CATEGORIES[category]
            if replace:
                videos = random.choices(files, k=count)
            else:
                videos = random.sample(files, count)

        categories.append({
            "name": category,
            "videos": [
                video.relative_to(stimuli_dir).as_posix()
                for video in videos
            ],
        })

    sequence["blocks"].append({
        "block": block,
        "categories": categories,
    })

# Save the planned order before opening the window.
sequence_path = subject_dir / f"{subject_id}_sequence.json"
with sequence_path.open("x", encoding="utf-8") as log:
    json.dump(sequence, log, indent=2)

print(f"Saved sequence to {sequence_path}")


# ------------------------------ window and stimuli ---------------------------------------

win = visual.Window(WIN_SIZE, fullscr=True, color="black", units="pix")

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
    win.close()
    core.quit()
win.flip()  # Clear the start instructions.


# ------------------------------ START ---------------------------------------

study_clock = core.Clock()
sequence["time_reference"] = "Seconds since first block started, including pauses and video loading"
stop_requested = False
print(f"Starting {subject_id}: {len(sequence['blocks'])} blocks. Esc during a video requests a pause.", flush=True)

for block in sequence["blocks"]:
    # No message screen: wait on black for Space between blocks.
    if block["block"] > 1:
        print(f"Waiting to start block {block['block']}/{N_BLOCKS}.", flush=True)
        stop_requested = pause_study(win)
        if stop_requested:
            break

    save_event("block_start", block["block"])
    print(f"Block {block['block']}/{N_BLOCKS} started.", flush=True)

    # Put this block's trials in one list, preserving the saved category order.
    trials = []
    for category in block["categories"]:
        trials.extend((category["name"], filename) for filename in category["videos"])

    for trial_number, (category_name, filename) in enumerate(trials, start=1):
        print(f"Block {block['block']}/{N_BLOCKS} | Trial {trial_number}/{len(trials)} | {category_name} | Loading {filename}", flush=True)
        pause_requested = play_video(win, stimuli_dir / filename, block["block"], trial_number)
        if pause_requested:
            stop_requested = pause_study(win)
        if stop_requested:
            break
    save_event("block_stopped" if stop_requested else "block_end", block["block"])
    print(f"Block {block['block']} {'stopped early' if stop_requested else 'completed'}.", flush=True)
    with sequence_path.open("w", encoding="utf-8") as log:
        json.dump(sequence, log, indent=2)
    print(f"Saved {len(events)} events to {sequence_path}", flush=True)
    if stop_requested:
        break

save_event("study_stopped" if stop_requested else "study_end")
with sequence_path.open("w", encoding="utf-8") as log:
    json.dump(sequence, log, indent=2)
print(f"Study {'stopped' if stop_requested else 'completed'}. Saved {len(events)} events to {sequence_path}", flush=True)

win.close()
core.quit()
