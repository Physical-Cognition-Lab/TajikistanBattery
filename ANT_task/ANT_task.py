"""Keyboard ANT based on old/ANT_task.py (not the E-Prime protocol)."""

from contextlib import ExitStack, nullcontext
import csv
from datetime import datetime
from pathlib import Path
import random


# ------------------------------ Helper functions ------------------------------

def load_text(path):
    """Read editable [section] blocks, as in HideAndSeek's instructions.txt."""
    sections = {}
    current = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    texts = {name: "\n".join(lines).strip() for name, lines in sections.items()}
    missing = [name for name in TEXT_SECTIONS if not texts.get(name)]
    if missing:
        raise ValueError(f"Missing or empty instruction sections in {path}: {', '.join(missing)}")
    return texts


def load_trials(path):
    with Path(path).open(encoding="utf-8", newline="") as file:
        trials = list(csv.DictReader(file))
    if len(trials) != 48:
        raise ValueError(f"Expected 48 trials in {path}; found {len(trials)}")
    for row in trials:
        if (row["Colour"] not in RESPONSE_KEYS
                or row["Expected_response"] != RESPONSE_KEYS[row["Colour"]]
                or row["Sound"] not in ("", "warning_sound")
                or row["Cue"] not in ("ANT_1", "ANT_2", "ANT_3")
                or row["Target"] not in {f"ANT_{n}" for n in range(5, 13)}):
            raise ValueError(f"Invalid ANT condition: {row}")
    return trials


def prepare_sequence(trials, seed):
    """Used by the offline generator only; playback reads its saved CSV."""
    rng = random.Random(seed)
    fix_times = [n / 10 for n in range(4, 17)]
    rng.shuffle(fix_times)
    sequence = [dict(row) for row in trials]
    rng.shuffle(sequence)
    for index, row in enumerate(sequence):
        row.update(Trial=index + 1, Block=index // 16 + 1)
    # Preserve the converted script: fix_times[1] is reused, not drawn per trial.
    return sequence, fix_times[1]


def load_sequence(path, subject_id, trials):
    """Read and validate the assigned order without shuffling or sorting it."""
    with Path(path).open(encoding="utf-8", newline="") as file:
        rows = [row for row in csv.DictReader(file) if row["subject_id"] == subject_id]
    if len(rows) != 48:
        raise ValueError(f"{subject_id} needs 48 rows in {path}; found {len(rows)}. "
                         "Extend the offline schedule before running this participant.")
    templates = {row["Trial_orig"]: row for row in trials}
    seed, fixation = int(rows[0]["seed"]), float(rows[0]["fixation_seconds"])
    if fixation not in [n / 10 for n in range(4, 17)]:
        raise ValueError(f"Invalid fixation duration for {subject_id}: {fixation}")
    sequence, seen = [], set()
    for index, row in enumerate(rows, 1):
        if (int(row["Trial"]), int(row["Block"])) != (index, (index - 1) // 16 + 1):
            raise ValueError(f"Invalid trial/block order for {subject_id}, row {index}")
        if int(row["seed"]) != seed or float(row["fixation_seconds"]) != fixation:
            raise ValueError(f"Inconsistent seed/fixation for {subject_id}")
        original = row["Trial_orig"]
        if original in seen or original not in templates:
            raise ValueError(f"Duplicate or unknown condition for {subject_id}: {original}")
        template = templates[original]
        if any(row[key] != value for key, value in template.items()):
            raise ValueError(f"Schedule condition differs from trial_list.csv: {original}")
        seen.add(original)
        sequence.append({**template, "Trial": index, "Block": int(row["Block"])})
    return sequence, fixation, seed, rows


def scene_scale(size):
    """Keep legacy sizes on both 1920-wide monitors; use the full window."""
    return min(size[0] / 1920, size[1] / 1080)


def set_view_scale(win, scale):
    win.viewScale = scale
    if hasattr(win, "setDefaultView"):
        win.setDefaultView(clearDepth=False)
    else:
        # PsychoPy 2025 applies viewScale when preparing the next back buffer.
        win.flip()


def save_event(trigger, **fields):
    events.append({"time": study_clock.getTime(), "trigger": trigger,
                   "phase": context.get("phase"), "trial": context.get("trial"), **fields})
    if recorder is not None:
        recorder.send_text(trigger)


def save_data(subject_dir):
    """Keep the complete participant session in one safely replaced JSON file."""
    write_json(subject_dir / f"{subject_id}.json", session)


def check_controls():
    global pause_requested
    pause_requested |= "escape" in event.getKeys(keyList=["escape"])


def draw_image(name):
    if name is not None:
        images[name].draw()


def present(name, seconds, marker, sound_name=None):
    draw_image(name)
    timer = core.Clock()
    win.callOnFlip(timer.reset)
    win.callOnFlip(save_event, marker + "_onset")
    if sound_name:
        win.callOnFlip(sounds[sound_name].play)
    win.flip()
    while timer.getTime() < seconds:
        check_controls()
        draw_image(name)
        win.flip()
    # Offset is marked by the next phase's onset, not by a fictitious blank flip.


def show_message(text, background="ANT_15", sound_name=None):
    draw_image(background)
    message = visual.TextStim(win, text=text, color="black", bold=True,
                              font="Arial", height=42, wrapWidth=1480,
                              pos=(0, 0), units="pix")
    # PsychoPy 2027 lays out its Rect bounds lazily when vertices are accessed.
    # Older TextStim versions return an already measured pixel pair instead.
    bounds = message.boundingBox
    if hasattr(bounds, "height"):
        ys = [point[1] for point in message.verticesPix]
        text_height = max(ys) - min(ys)
    else:
        text_height = bounds[1]
    # A solid panel keeps the busy artwork from reducing instruction contrast.
    visual.Rect(win, width=1640, height=max(220, text_height + 96),
                fillColor="ivory", lineColor=None, units="pix").draw()
    message.draw()
    win.flip()
    if sound_name:
        sounds[sound_name].play()
    event.clearEvents(eventType="keyboard")
    try:
        return "space" in event.waitKeys(keyList=["space", "escape"])
    finally:
        if sound_name:
            sounds[sound_name].stop()


def pause_study():
    save_event("pause")
    return not show_message(texts["pause"])


def handle_pause():
    global pause_requested
    check_controls()
    if pause_requested:
        pause_requested = False
        if pause_study():
            return True
    return False


def collect_response(target, limit):
    onset = None

    def begin_response():
        nonlocal onset
        event.clearEvents(eventType="keyboard")
        onset = study_clock.getTime()
        save_event("target_onset", stimulus=target)

    draw_image(target)
    win.callOnFlip(begin_response)
    win.flip()
    while True:
        check_controls()
        for key, timestamp in event.getKeys(keyList=list(RESPONSE_COLOURS), timeStamped=study_clock):
            rt = timestamp - onset
            if rt < 0 or (limit is not None and rt > limit):
                continue
            save_event("response", key=key, press_time=timestamp, rt=rt,
                       colour=RESPONSE_COLOURS[key])
            return key, rt, onset
        if limit is not None and study_clock.getTime() - onset >= limit:
            save_event("no_response")
            return None, None, onset
        # Practice is untimed; allow a queued operator pause to be handled safely.
        if limit is None and pause_requested:
            return None, None, onset
        draw_image(target)
        win.flip()


def run_trial(row, practice=False):
    context.update(phase="practice" if practice else "test", trial=row["Trial"])
    started = study_clock.getTime()
    save_event("trial_start", block=row["Block"])
    if not practice:
        present("ANT_1", session["fixation_seconds"], "fixation")
        present(row["Cue"], 0.35, "cue", "warning" if row["Sound"] else None)
        present("ANT_1", 0.1, "postcue_fixation")
        # Keep the normal tree visible during the old script's 150 ms interval.
        present("ANT_1", 0.15, "isi")
    key, rt, onset = collect_response(row["Target"], None if practice else 5.0)
    colour = RESPONSE_COLOURS.get(key)
    correct = key == row["Expected_response"]
    results.append({**row, "Phase": context["phase"], "Subject": subject_id,
                     "Trial_start_time": started, "Target_onset": onset,
                     "Response": key, "Response_colour": colour, "RTs": rt,
                     "Correct": correct})
    save_data(subject_dir)
    present("ANT_13" if correct else "ANT_14", 1.0, "feedback",
            "correct" if correct else "wrong")
    save_event("trial_end", correct=correct)
    save_data(subject_dir)
    print(f"{context['phase']} trial {row['Trial']}: {colour or 'no response'}, RT={rt}", flush=True)


# ------------------------------ Settings and paths ------------------------------

study_dir = Path("ANT_task")
stimuli_dir = study_dir / "Stimuli"
data_dir = study_dir / "Data"
RESPONSE_KEYS = {"yellow": "g", "red": "h"}
RESPONSE_COLOURS = {key: colour for colour, key in RESPONSE_KEYS.items()}
PRACTICE = [("YELLOW_CONG", "g"), ("YELLOW_INC", "g"),
            ("RED_CONG", "h"), ("RED_INC", "h"), ("ANT_6", "h"), ("ANT_7", "g")]
TEXT_SECTIONS = ("welcome", "practice_reminder", "test_start", "block_break", "pause", "stopped", "end")
recorder = None


# ------------------------------ Run ------------------------------

if __name__ == "__main__":
    from utils.display_settings import enable_native_pixels
    enable_native_pixels()
    import psychopy
    from psychopy import prefs
    prefs.hardware["audioLib"] = ["ptb"]
    from psychopy import visual, core, event, sound
    from utils.subject_selection import get_participant
    from utils.display_settings import DisplaySettings
    from utils.data_saving import write_json

    image_files = {f"ANT_{n}": f"ANT_{n}.jpg" for n in (1, 2, 3, *range(5, 16))}
    image_files.update({name: name + ".JPG" for name, _ in PRACTICE if not name.startswith("ANT_")})
    image_files.update({"start_end": "START_END.jpeg", **{f"bird{n}": f"bird{n}.png" for n in (1, 2, 3)}})
    sound_files = {"warning": "WARNINGTONE.mp3", "correct": "CORRECT.mp3",
                   "wrong": "hz41_INCORRECT_NORESP.mp3", "start": "START.mp3"}
    texts = load_text(study_dir / "instructions.txt")
    trials = load_trials(stimuli_dir / "trial_list.csv")
    for filename in [*image_files.values(), *sound_files.values()]:
        if not (stimuli_dir / filename).is_file():
            raise FileNotFoundError(stimuli_dir / filename)

    display = DisplaySettings.detect()
    subject_id, subjnum, recording, _, _ = get_participant(
        data_dir, recording=False, display=display,
    )
    subject_dir = data_dir / subject_id
    assignments_file = stimuli_dir / "sequences.csv"
    sequence, fixation, seed, _ = load_sequence(assignments_file, subject_id, trials)
    study_clock = core.Clock()
    events, results, context = [], [], {}
    pause_requested = False
    session = {"subject": subject_id, "study": "ANT_task", "source": "old/ANT_task.py",
               "psychopy": psychopy.__version__, "seed": seed, "fixation_seconds": fixation,
               "schedule": assignments_file.name, "response_mode": "keyboard",
               "response_keys": RESPONSE_KEYS, "instructions": texts,
               "started": datetime.now().isoformat(timespec="seconds"), "ended": None,
               "completed": False, "planned_trials": sequence, "events": events, "results": results}
    save_data(subject_dir)

    with ExitStack() as cleanup:
        win = visual.Window(size=display.size, screen=display.screen, fullscr=True,
                            units="pix", color="black")
        cleanup.callback(win.close)
        win.mouseVisible = False
        scale = scene_scale(win.size)
        set_view_scale(win, (scale, scale))
        session["display"] = {**display.metadata(win), "scene_scale": float(scale),
                              "scaling_reference_size": [1920, 1080],
                              "visible_scene_size": [float(value / scale) for value in win.size],
                              "legacy_image_size": [1920, 1400]}
        # No 1080-high mask: a 1920x1200 screen exposes 120 more image rows,
        # cropping only 100 pixels at each end of the centred 1400-high picture.
        images = {}
        for name, filename in image_files.items():
            size = (960, 400) if name in {p[0] for p in PRACTICE[:4]} else (1920, 1400)
            images[name] = visual.ImageStim(win, image=str(stimuli_dir / filename), size=size)
        sounds = {}
        for name, filename in sound_files.items():
            sounds[name] = sound.Sound(str(stimuli_dir / filename))
            cleanup.callback(sounds[name].stop)
        if not show_message(texts["welcome"], "start_end", "start"):
            session["ended"] = datetime.now().isoformat(timespec="seconds")
            save_event("study_stopped")
            save_data(subject_dir)
            core.quit()
        recorder_ctx = nullcontext()
        if recording:
            from utils.video_recording.webcam_recorder import WebcamRecorder
            recorder_ctx = WebcamRecorder.for_subject(subject_dir)
        with recorder_ctx as recorder:
            if recorder is not None and recorder.last_error:
                print(f"WARNING: no video this session: {recorder.last_error}", flush=True)
            stopped = False
            save_event("study_start")
            try:
                for number, (target, answer) in enumerate(PRACTICE, 1):
                    row = dict(Trial_orig="", Trial=number, Block=0,
                               Colour=RESPONSE_COLOURS[answer], Sound="",
                               Cue="", Target=target, Expected_response=answer)
                    run_trial(row, practice=True)
                    if handle_pause() or not show_message(texts["practice_reminder"]):
                        stopped = True
                        break
                if not stopped:
                    context.clear()
                    stopped = not show_message(texts["test_start"], "start_end", "start")
                for row in sequence if not stopped else []:
                    if row["Trial"] in (17, 33):
                        context.clear()
                        if not show_message(texts["block_break"], f"bird{row['Block']-1}", "start"):
                            stopped = True
                            break
                    run_trial(row)
                    if handle_pause():
                        stopped = True
                        break
                session["completed"] = not stopped
                context.clear()
                save_event("study_stopped" if stopped else "study_end")
            except BaseException as exc:
                session["error"] = f"{type(exc).__name__}: {exc}"
                save_event("study_error")
                raise
            finally:
                session["ended"] = datetime.now().isoformat(timespec="seconds")
                save_data(subject_dir)
            show_message(texts["stopped" if stopped else "end"], "bird3")
