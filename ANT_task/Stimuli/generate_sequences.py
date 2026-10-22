"""Generate/extend fixed ANT assignments before data collection (no PsychoPy)."""

import argparse
import csv
from pathlib import Path
import tempfile

from ANT_task.ANT_task import load_trials, prepare_sequence

STIMULI_DIR = Path(__file__).resolve().parent
MASTER_SEED = 20261022
FIELDS = ["subject_id", "seed", "fixation_seconds", "Trial", "Block",
          "Trial_orig", "Colour", "Sound", "Cue", "Target", "Expected_response"]


def generate_subject(trials, number):
    seed = MASTER_SEED + number
    sequence, fixation = prepare_sequence(trials, seed)
    return [{key: str(value) for key, value in {
        "subject_id": f"S{number:03d}", "seed": seed,
        "fixation_seconds": fixation, **trial}.items()} for trial in sequence]


def write_schedule(path, trials, subjects=400):
    """Never change existing assignments; fail if their contents differ."""
    if subjects < 1:
        raise ValueError("Subjects must be a positive integer")
    path = Path(path)
    rows = [row for number in range(1, subjects + 1) for row in generate_subject(trials, number)]
    if path.exists():
        with path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            existing = list(reader)
            if reader.fieldnames != FIELDS:
                raise ValueError(f"Unexpected schedule columns in {path}")
        if not existing or len(existing) % 48 or existing != rows[:len(existing)]:
            raise ValueError("Existing assignments differ, or the requested subject count is smaller. "
                             "Refusing to replace the schedule.")
        if existing == rows:
            return len(rows)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", delete=False,
                                         dir=path.parent, suffix=".tmp") as file:
            temporary = Path(file.name)
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subjects", type=int, default=400)
    args = parser.parse_args()
    count = write_schedule(STIMULI_DIR / "sequences.csv",
                           load_trials(STIMULI_DIR / "trial_list.csv"), args.subjects)
    print(f"Saved/verified {args.subjects} participants, {count} trials in {STIMULI_DIR / 'sequences.csv'}")


if __name__ == "__main__":
    main()
