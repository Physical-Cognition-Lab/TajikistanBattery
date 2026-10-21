from contextlib import ExitStack, contextmanager, nullcontext
import csv
from datetime import datetime
from pathlib import Path

# ------------------------------ Helper functions ------------------------------

def scene_scale(size):
    """Fit the original 16:9 scene inside the screen without stretching it."""
    width, height = size
    return min(1.0, width / (height * SCENE_ASPECT))


def scene_position(x, y, size, scale):
    """Convert bottom-left pyglet pixels back to original scene height units."""
    width, height = size
    return ((x - width / 2) / (height * scale),
            (y - height / 2) / (height * scale))


def set_view_scale(win, scale):
    """Apply the scale before drawing, not after the next flip."""
    win.viewScale = scale
    win.setDefaultView(clearDepth=False)


@contextmanager
def unscaled_view(win):
    """Pixel-sized operator messages and break videos need no scene scaling."""
    saved_scale = win.viewScale
    try:
        set_view_scale(win, (1, 1))
        yield
    finally:
        set_view_scale(win, saved_scale)


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


def get_assignment_row(subject_id):
    """Return this subject's row of the colour/pattern schedule."""
    if not assignments_file.exists():
        print(f"No participant assignments file: {assignments_file}")
        print("Create it with:")
        print("  pixi run python HideAndSeek/tools/make_participant_assignments.py")
        core.quit()

    with assignments_file.open(encoding="utf-8", newline="") as log:
        schedule = {row["subject"]: row for row in csv.DictReader(log)}

    if subject_id not in schedule:
        print(f"{subject_id} is not in {assignments_file}, "
              f"which holds {len(schedule)} subjects.")
        print("Extend it with:")
        print("  pixi run python HideAndSeek/tools/make_participant_assignments.py --subjects 500")
        core.quit()

    return schedule[subject_id]


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

    # Mirror the same event onto the recorded video, when recording is on.
    if recorder is not None:
        recorder.send_text(action)


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

    write_json(subject_dir / f"{subject_id}.json", data)


def pause_study(win):
    """Space resumes; Esc stops. Return True when the operator chooses to stop."""
    print("Study paused. Space = continue; Esc = stop.", flush=True)
    save_event("pause")
    with unscaled_view(win):
        visual.TextStim(
            win,
            text="Press Space to continue\n\nPress Esc again to close",
            color="white", height=36, wrapWidth=900, units="pix",
        ).draw()
        win.flip()
        event.clearEvents(eventType="keyboard")
        keys = event.waitKeys(keyList=["space", "escape"])
        win.flip()  # Clear the message before returning to the task.
    print("Stopping study..." if "escape" in keys else "Continuing study.", flush=True)
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
            # Undo the drawing scale before hit-testing or saving coordinates.
            # Use pyglet's own dimensions because its events use those pixels.
            pos = scene_position(x, y, win.winHandle.get_size(), win.viewScale[0])
            pending_presses.append((*pos, study_clock.getTime()))
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

            # Black bars are not part of the task, even above the centre.
            # Keep these touches as misses, but never let them advance a trial.
            if not (abs(mouse_x) <= SCENE_ASPECT / 2 and abs(mouse_y) <= 0.5):
                clicks.append({"time": press_time, "x": mouse_x, "y": mouse_y,
                               "phase": "predict" if hidden else "choice",
                               "action": "miss", "puppet": puppet})
                continue

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


# ------------------------------ Settings and paths ------------------------------

## Paths
# Works both as a script and when running cells in a notebook.
study_dir = Path("HideAndSeek")

data_dir = study_dir / "Data"
stimuli_dir = study_dir / "Stimuli"
assignments_file = stimuli_dir / "participant_assignments.csv"
WIN_SIZE = (1920, 1080)
SCENE_ASPECT = WIN_SIZE[0] / WIN_SIZE[1]

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
texts = load_text(study_dir / "instructions.txt")

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


# Set while a session records, so save_event can also write to the video.
recorder = None

# ------------------------------ Run ------------------------------

if __name__ == "__main__":
    from utils.display_settings import enable_native_pixels

    enable_native_pixels()
    # Imports
    # The webcam worker re-runs this file; it does not need the study libraries.
    import psychopy
    from psychopy import visual, core, event, sound
    import pandas as pd

    from utils.subject_selection import get_participant
    from utils.data_saving import write_json
    from utils.pause_video import show_pause_video
    from utils.display_settings import DisplaySettings

    # Participant setup
    # Keep this clock running through the dialog, as in existing session logs.
    study_clock = core.Clock()
    display = DisplaySettings.detect()
    subject_id, subjnum, recording, _, _ = get_participant(data_dir, display=display)
    subject_dir = data_dir / subject_id
    print(f"Preparing HideAndSeek for participant {subject_id}.", flush=True)

    # Prepare study sequence
    # Loaded from locations.csv: pattern, position, x, y, angle.
    # Patterns are named A, B and C; the schedule decides which character
    # walks which one, so colour and trajectory are not confounded.
    patterns = {
        pattern: group[["x", "y", "angle"]].values.tolist()
        for pattern, group in (
            pd.read_csv(stimuli_dir / "locations.csv")
            .sort_values(["pattern", "position"])
            .groupby("pattern")
        )
    }

    # Session bookkeeping used by save_event and save_data.
    rows = []      # the session table: one dict per action or event
    trials = {}    # per-trial values, known only after the reveal
    stop_requested = False

    # Which trajectory each character walks, fixed for this subject by the
    # schedule. locations stays keyed by colour, so the task code is unchanged.
    schedule_row = get_assignment_row(subject_id)
    locations = {
        colour: patterns[schedule_row[colour]]
        for colour in ("blue", "red", "green")
    }

    # Everything about the session that is not a row.
    session = {
        "subject": subject_id,
        "study": "HideAndSeek",
        "schedule": assignments_file.name,
        "patterns": {
            colour: schedule_row[colour] for colour in ("blue", "red", "green")
        },
        "psychopy": psychopy.__version__,
        "window_size": list(WIN_SIZE),
        "started": datetime.now().isoformat(timespec="seconds"),
        "ended": None,
        "completed": False,
    }

    # Window and stimuli
    # Registered cleanup runs on normal exit, Esc, or an exception (last added first).
    with ExitStack() as cleanup:
        win = visual.Window(
            size=display.size, screen=display.screen, fullscr=True,
            units="height", color="black",
        )
        cleanup.callback(win.close)
        # Height units normally fill the whole screen. Shrink the entire scene
        # uniformly to preserve its original 16:9 layout on a taller display.
        # At 1920x1200 this is 0.9: 1920x1080 with 60px black bars top/bottom.
        scale = scene_scale(win.size)
        set_view_scale(win, (scale, scale))
        # Record the size actually used: it can differ from the requested one.
        session["window_size"] = [int(win.size[0]), int(win.size[1])]
        session["display"] = display.metadata(win)
        session["display"].update({
            "scene_aspect_ratio": SCENE_ASPECT,
            "scene_scale": scale,
            "scene_size": [float(win.size[1] * scale * SCENE_ASPECT),
                           float(win.size[1] * scale)],
        })
        save_data(subject_dir)

        # Load the fixed scene.
        stimuli = {
            "sky": visual.ImageStim(win, image=str(scene_files["sky"]), size=(SCENE_ASPECT, 1)),
            "foreground": visual.ImageStim(win, image=str(scene_files["foreground"]), size=(SCENE_ASPECT, 1)),
            "hidden_patch": visual.ImageStim(
                win, image=str(scene_files["hidden_patch"]),
                pos=(0, -0.1), size=(0.15, 0.2),
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
            cue = visual.ImageStim(win, image=str(files["cue"]),
                                   pos=(0, -0.1), size=(0.15, 0.2))
            portrait = visual.ImageStim(win, image=str(files["portrait"]),
                                         pos=portrait_positions[colour], size=(0.16428, 0.2))
            animation = [
                visual.ImageStim(win, image=str(path), size=(0.1, 0.1))
                for path in files["animation"]
            ]
            stimuli["puppets"][colour] = {"cue": cue, "animation": animation}
            stimuli["portraits"][colour] = portrait

        # Register each sound immediately, including when later loading fails.
        for name, path in sound_files.items():
            stimuli["sounds"][name] = sound.Sound(str(path))
            cleanup.callback(stimuli["sounds"][name].stop)

        # Start screen
        print(f"Ready: participant {subject_id}. Space = start; Esc = abort.", flush=True)
        show_message(win, stimuli, texts["welcome"])

        # Recording
        recorder_ctx = nullcontext()
        if recording:
            from utils.video_recording.webcam_recorder import WebcamRecorder
            recorder_ctx = WebcamRecorder.for_subject(subject_dir)

        with recorder_ctx as recorder:
            if recorder is not None and recorder.last_error:
                print(f"WARNING: no video this session: {recorder.last_error}", flush=True)

            # Study loop
            position_index = {"blue": 0, "red": 0, "green": 0}
            current_puppet = "blue"
            save_event("study_start")
            print("Study started. Esc = pause; X = video break after the current trial.", flush=True)

            while not stop_requested:
                trial_number = len(trials) + 1
                trial_start_time = study_clock.getTime()
                save_event("trial_start", trial=trial_number, time_study=trial_start_time,
                           time_trial=0.0)
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

                # Advance that puppet's own sequence and show the reveal.
                target_pos_x, target_pos_y, target_angle = locations[puppet][position_index[puppet]]
                target_pos = (target_pos_x, target_pos_y)
                position_index[puppet] += 1
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
                print(f"Trial {trial_number} completed.", flush=True)

                if not stop_requested and "x" in event.getKeys(keyList=["x"]):
                    with unscaled_view(win):
                        show_pause_video(win, save_event)

                # Stop when a puppet has used all 35 of its locations, or at the cap.
                if len(trials) >= MAX_TRIALS or any(
                    position_index[c] >= len(locations[c]) for c in locations
                ):
                    break

            # Final save and cleanup
            session["completed"] = not stop_requested
            session["ended"] = datetime.now().isoformat(timespec="seconds")
            save_event("study_stopped" if stop_requested else "study_end")
            save_data(subject_dir)
            print(f"Study {'stopped early' if stop_requested else 'completed'}. Data saved to {subject_dir}.", flush=True)

            # Closing message. The data is already saved, so waiting here is safe.
            print("Space = close; Esc = exit.", flush=True)
            show_message(win, stimuli, texts["end"])
