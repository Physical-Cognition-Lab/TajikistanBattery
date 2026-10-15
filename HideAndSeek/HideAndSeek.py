import json
from datetime import datetime
from pathlib import Path
import psychopy
from psychopy import visual, gui, core, event, sound
import pandas as pd



#----------------------------- Functions  ---------------------------------------------

def load_text(path):
    """Read a text file of [section] blocks into a dict of name -> text.

    Each block keeps its own line breaks, so the wording can be edited or
    translated without touching the code.
    """
    sections = {}
    current = None

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


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


# The session table: one row per action or event. Unused columns stay None.
COLUMNS = [
    "trial", "phase", "action", "puppet",
    "x", "y", "time_study", "time_trial",
    "target_x", "target_y", "target_angle", "prediction_x", "prediction_y",
]


def save_event(action, trial=None, **fields):
    """Append one row of the session table.

    A session marker passes just an action name. A participant action passes
    the phase, puppet and position. Both land in the same table.
    """
    row = {name: None for name in COLUMNS}
    row["action"] = action
    row["trial"] = trial
    row["phase"] = fields.pop("phase", "event")

    # A click carries the time of its own press; a marker is stamped here.
    press_time = fields.pop("time_study", None)
    row["time_study"] = study_clock.getTime() if press_time is None else press_time

    row.update(fields)

    # Round to the nearest millisecond. The touch pipeline is nowhere near
    # that precise, and it stops 42.05 - 41.2 becoming 0.8499999999999943.
    row["time_study"] = round(row["time_study"], 3)
    if row["time_trial"] is not None:
        row["time_trial"] = round(row["time_trial"], 3)

    rows.append(row)


def save_data(subject_dir):
    """Rewrite the participant file, so a stop or crash loses nothing.

    The reveal position and the prediction belong to the whole trial, so they
    are copied into every row of that trial here, once they are known.
    """
    for row in rows:
        info = trials.get(row["trial"])
        if info is not None:
            row.update(info)

    data = {"metadata": session, "columns": COLUMNS, "rows": rows}

    # Dump to a temporary file first: if anything fails part-way (a stray NaN,
    # a full disk), the previous good file is left untouched.
    path = subject_dir / f"{subject_id}.json"
    tmp = subject_dir / f"{subject_id}.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, allow_nan=False)
    tmp.replace(path)


def pause_study(win):
    """Show pause instructions: Space continues, Esc stops."""
    print("Paused: Space = continue, Esc = stop.", flush=True)
    save_event("pause")
    visual.TextStim(
        win,
        text="Press Space to continue\n\nPress Esc again to close",
        color="white", height=36, wrapWidth=900, units="pix",
    ).draw()
    win.flip()
    event.clearEvents(eventType="keyboard")
    keys = event.waitKeys(keyList=["space", "escape"])
    win.flip()  # Clear the message before returning to the task.
    print("Stop requested." if "escape" in keys else "Continuing.", flush=True)
    return "escape" in keys


def draw_scene(win, stimuli, centre=None, centre_in_front=False, overlays=None):
    """Draw one frame, in the same order as the original task.

    back -> front: sky, the centre image, the grass, the portraits, overlays.

    The grass is drawn over the centre image, unless `centre_in_front` is set.
    That matches the original, which used opposite orders in its two routines:
      - choosing a puppet: it stands in FRONT of the hill
      - the reveal: it rises from BEHIND the hill
    """
    stimuli["sky"].draw()

    if centre is not None and not centre_in_front:
        centre.draw()

    stimuli["foreground"].draw()

    if centre is not None and centre_in_front:
        centre.draw()

    for portrait in stimuli["portraits"].values():
        portrait.draw()

    for stim in overlays or []:
        stim.draw()


def show_message(win, stimuli, text):
    """Draw a message over the sky and wait for Space. Esc also closes."""
    stimuli["sky"].draw()
    visual.TextStim(
        win,
        text=text,
        color="black",
        height=0.035,
        wrapWidth=1.5,
    ).draw()
    win.flip()

    event.clearEvents(eventType="keyboard")
    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        win.close()
        core.quit()


def select_and_predict(win, stimuli, current_puppet, first_trial):
    """Let the participant switch puppet, hide it, then click where it appears.

    Returns the chosen puppet, the prediction position, and every click made
    while choosing (or None as the puppet if the participant stopped).
    """
    global stop_requested

    mouse = event.Mouse(win=win)

    # Keep the press point: quick taps can be released before the next frame.
    # A long touch may arrive as a right-click, so accept any mouse button.
    pending_presses = []
    buttons = mouse.getPressed()
    held_buttons = {button for button, down in zip((1, 2, 4), buttons) if down}

    def remember_press(x, y, button, modifiers):
        if not held_buttons:
            # pyglet pixels start at bottom-left; height units at the centre.
            width, height = win.winHandle.get_size()
            pending_presses.append(((x - width / 2) / height,
                                    (y - height / 2) / height,
                                    study_clock.getTime()))
        held_buttons.add(button)

    def remember_release(x, y, button, modifiers):
        # Only a new contact after release can trigger another action.
        held_buttons.discard(button)

    hidden_patch = stimuli["hidden_patch"]
    portraits = stimuli["portraits"]
    hint = stimuli["instructions"]["hint"]
    footer = stimuli["instructions"]["footer"]

    puppet = current_puppet
    hidden = False
    clicks = []  # Every click made while choosing, with its position.

    # First trial: start with the "hide" hint. Later trials: drop the hint and
    # show the standing reminder instead.
    if first_trial:
        hint.setText(texts["hide"])
    else:
        hint.setText("")
        footer.setText(texts["change"])

    # Pushed handlers also let PsychoPy receive the normal mouse events.
    win.winHandle.push_handlers(on_mouse_press=remember_press,
                                on_mouse_release=remember_release)
    try:
        while True:

            # On the first trial the hint follows the stage: hide, then predict.
            if first_trial:
                wanted = texts["predict"] if hidden else texts["hide"]
                if hint.text != wanted:
                    hint.setText(wanted)

            # The puppet (or the hidden patch) sits in front of the grass.
            if hidden:
                centre = hidden_patch
            else:
                centre = stimuli["puppets"][puppet]["cue"]

            draw_scene(win, stimuli, centre=centre, centre_in_front=True,
                       overlays=[hint, footer])
            win.flip()

            if "escape" in event.getKeys(keyList=["escape"]):
                if pause_study(win):
                    stop_requested = True
                    return None, None, clicks
                # Back from a pause: ignore any click that happened meanwhile.
                mouse.getPressed()  # Dispatch any remaining mouse events.
                pending_presses.clear()
                continue

            # --- react only to a fresh contact, at its saved press point ---
            pressed_now = mouse.getPressed()  # Dispatch events between frames.

            # Safety net: if pyglet says nothing is held but we still believe a
            # button is down, a release event was lost. Without this, one lost
            # release would block every later touch for the rest of the trial.
            if not any(pressed_now):
                held_buttons.clear()

            if not pending_presses:
                continue
            mouse_x, mouse_y, press_time = pending_presses.pop(0)
            press_pos = (mouse_x, mouse_y)

            # 1. A portrait was clicked: switch puppet.
            clicked_portrait = None
            for colour, portrait in portraits.items():
                if portrait.contains(press_pos):
                    clicked_portrait = colour

            if clicked_portrait is not None:
                clicks.append({"time": press_time, "x": mouse_x, "y": mouse_y,
                               "phase": "choice", "action": "switch",
                               "puppet": clicked_portrait})
                puppet = clicked_portrait
                hidden = False

            # 2. The central puppet was clicked: hide it.
            elif not hidden:
                if stimuli["puppets"][puppet]["cue"].contains(press_pos):
                    clicks.append({"time": press_time, "x": mouse_x, "y": mouse_y,
                                   "phase": "choice", "action": "hide",
                                   "puppet": puppet})
                    hidden = True
                    stimuli["sounds"]["hiding"].play()
                else:
                    # Touch that hit nothing while choosing.
                    clicks.append({"time": press_time, "x": mouse_x, "y": mouse_y,
                                   "phase": "choice", "action": "miss",
                                   "puppet": puppet})

            # 3. Already hidden: click above the middle to predict.
            else:
                if mouse_y > 0:
                    clicks.append({"time": press_time, "x": mouse_x, "y": mouse_y,
                                   "phase": "predict", "action": "predict",
                                   "puppet": puppet})
                    return puppet, (mouse_x, mouse_y), clicks
                else:
                    # Touch below the middle: not a prediction.
                    clicks.append({"time": press_time, "x": mouse_x, "y": mouse_y,
                                   "phase": "predict", "action": "miss",
                                   "puppet": puppet})
    finally:
        # Do not leave handlers attached after this trial ends or stops.
        win.winHandle.remove_handlers(on_mouse_press=remember_press,
                                      on_mouse_release=remember_release)


def reveal(win, stimuli, puppet, target_pos, target_angle):
    """Play the 10-frame animation at the target location."""
    global stop_requested

    animation = stimuli["puppets"][puppet]["animation"]
    footer = stimuli["instructions"]["footer"]

    for image in animation:
        image.pos = target_pos
        image.ori = target_angle

    stimuli["sounds"]["reveal"].play()

    frame_clock = core.Clock()

    for image in animation:
        frame_clock.reset()

        while frame_clock.getTime() < 0.1:
            draw_scene(win, stimuli, centre=image, overlays=[footer])
            win.flip()

            if "escape" in event.getKeys(keyList=["escape"]):
                if pause_study(win):
                    stop_requested = True
                    return

    stimuli["sounds"]["reveal"].stop()


#----------------------------- Settings, Paths and stimuli  ---------------------------------------------

## Paths
# Works both as a script and when running cells in a notebook.
StudyPath = Path("HideAndSeek")

data_dir = StudyPath / "Data"
stimuli_dir = StudyPath / "Stimuli"

### Stimuli

scene_files = {
    "sky": stimuli_dir / "background_sky.png",
    "foreground": stimuli_dir / "background2.png",
    "hidden_patch": stimuli_dir / "green.png",
}

puppet_files = {}

for colour, number in {"blue": 1, "red": 2, "green": 3}.items():
    puppet_files[colour] = {
        "cue": stimuli_dir / f"whole{number}.png",
        "portrait": stimuli_dir / f"whole{number}framed.jpg",
        "empty": stimuli_dir / f"whole{number}empty.jpg",
        "animation": [
            stimuli_dir / f"targ{number}_{frame:02d}.png"
            for frame in range(10)
        ],
    }

sound_files = {
    "appearance": stimuli_dir / "pop.wav",
    "hiding": stimuli_dir / "hidesound.wav",
    "reveal": stimuli_dir / "targetsound.wav",
}

### Instructions
# Editable, translatable text: one [section] block per message.
texts = load_text(StudyPath / "instructions.txt")

### Locations
# Loaded from locations.csv: puppet, position, x, y, angle

locations = {
    colour: group[["x", "y", "angle"]].values.tolist()
    for colour, group in (
        pd.read_csv(StudyPath / "locations.csv")
        .sort_values(["puppet", "position"])
        .groupby("puppet")
    )
}

### Stop rule
# A puppet has 35 locations. The original also capped the session at 83
# trials, which is what its "sum of indices == 80" worked out to.
MAX_TRIALS = 83


# Positions of the three selectable portraits along the bottom.
portrait_positions = {
    "blue": (-0.16428, -0.37),
    "red": (0, -0.37),
    "green": (0.16428, -0.37),
}


#----------------------------- Run  ---------------------------------------------

# Session bookkeeping used by save_event and save_data.
rows = []      # the session table: one dict per action or event
trials = {}    # per-trial values, known only after the reveal
study_clock = core.Clock()
stop_requested = False

subject_id, subjnum = get_participant(data_dir)
subject_dir = data_dir / subject_id
subject_dir.mkdir(parents=True, exist_ok=True)

# Everything about the session that is not a row.
session = {
    "subject": subject_id,
    "study": "HideAndSeek",
    "psychopy": psychopy.__version__,
    "window_size": [1280, 720],
    "started": datetime.now().isoformat(timespec="seconds"),
    "ended": None,
    "completed": False,
}

# Create the experiment window.
win = visual.Window(
    size=(1280, 720),
    fullscr=False,
    units="height",
    color="black",
)

# Record the size actually used: it can differ from the requested one.
session["window_size"] = [int(win.size[0]), int(win.size[1])]

# Load the fixed scene.
stimuli = {
    "sky": visual.ImageStim(win, image=str(scene_files["sky"]), size=(1.77778, 1)),
    "foreground": visual.ImageStim(win, image=str(scene_files["foreground"]), size=(1.77778, 1)),
    "hidden_patch": visual.ImageStim(
        win,
        image=str(scene_files["hidden_patch"]),
        pos=(0, -0.1),
        size=(0.15, 0.2),
    ),
    "puppets": {},
    "portraits": {},
    "sounds": {},
    "instructions": {
        # Both start empty; only one is filled at a time, in select_and_predict.
        "hint": visual.TextStim(win, text="", pos=(0, -0.23), height=0.022, color="black"),
        "footer": visual.TextStim(win, text="", pos=(0, -0.483), height=0.021, color="black"),
    },
}

# Load each puppet: its central image, its portrait, and its animation frames.
for colour, files in puppet_files.items():

    cue = visual.ImageStim(
        win,
        image=str(files["cue"]),
        pos=(0, -0.1),
        size=(0.15, 0.2),
    )

    portrait = visual.ImageStim(
        win,
        image=str(files["portrait"]),
        pos=portrait_positions[colour],
        size=(0.16428, 0.2),
    )

    animation = [
        visual.ImageStim(win, image=str(path), size=(0.1, 0.1))
        for path in files["animation"]
    ]

    stimuli["puppets"][colour] = {"cue": cue, "animation": animation}
    stimuli["portraits"][colour] = portrait

# Load the sounds.
for name, path in sound_files.items():
    stimuli["sounds"][name] = sound.Sound(str(path))

# Welcome screen: waits for Space; Esc quits before the task starts.
show_message(win, stimuli, texts["welcome"])


#----------------------------- Main loop  ---------------------------------------------

position_index = {"blue": 0, "red": 0, "green": 0}

current_puppet = "blue"

save_event("study_start")
print(f"Starting {subject_id}. Escape pauses; Space continues.", flush=True)

while not stop_requested:

    trial_number = len(trials) + 1
    trial_start_time = study_clock.getTime()
    save_event("trial_start", trial=trial_number, time_study=trial_start_time,
               time_trial=0.0)

    # Let the participant pick a puppet, hide it, and predict where it appears.
    puppet, prediction, clicks = select_and_predict(
        win, stimuli, current_puppet, first_trial=(trial_number == 1)
    )

    if stop_requested:
        break

    current_puppet = puppet

    # Every touch made while choosing becomes a row of the table.
    for click in clicks:
        save_event(click["action"], trial=trial_number, phase=click["phase"],
                   puppet=click["puppet"], x=click["x"], y=click["y"],
                   time_study=click["time"],
                   time_trial=click["time"] - trial_start_time)

    # Advance that puppet's own sequence.
    target_pos_x, target_pos_y, target_angle = locations[puppet][position_index[puppet]]
    target_pos = (target_pos_x, target_pos_y)
    position_index[puppet] += 1

    # Show the reveal animation.
    reveal(win, stimuli, puppet, target_pos, target_angle)

    # Values that only exist after the reveal; save_data copies them into
    # every row of this trial.
    trials[trial_number] = {
        "target_x": target_pos_x,
        "target_y": target_pos_y,
        "target_angle": target_angle,
        "prediction_x": prediction[0],
        "prediction_y": prediction[1],
    }

    trial_end_time = study_clock.getTime()
    save_event("trial_end", trial=trial_number, time_study=trial_end_time,
               time_trial=trial_end_time - trial_start_time)
    save_data(subject_dir)

    # Stop when a puppet has used all 35 of its locations, or at the cap.
    if len(trials) >= MAX_TRIALS or any(
        position_index[c] >= len(locations[c]) for c in locations
    ):
        break

session["completed"] = not stop_requested
session["ended"] = datetime.now().isoformat(timespec="seconds")
save_event("study_stopped" if stop_requested else "study_end")
print(f"Study {'stopped' if stop_requested else 'completed'}.", flush=True)

save_data(subject_dir)
print(f"Saved {len(trials)} trials for {subject_id} to {subject_dir}", flush=True)

# Closing message. The data is already saved, so waiting here is safe.
show_message(win, stimuli, texts["end"])

win.close()
