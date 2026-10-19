"""Create the 400 subject schedules. Run this file once, before data collection."""

import csv
import random
from pathlib import Path

STIMULI_DIR = Path(__file__).resolve().parent
N_SUBJECTS = 400
N_BLOCKS = 3
MASTER_SEED = 20261019
FIELDS = ["subject_id", "seed", "block", "trial", "category", "video"]

# Category: (movies, presentations per block, sample with replacement).
CATEGORIES = {
    "GazeFollowing": (sorted(STIMULI_DIR.glob("GazeFollowing/GF_*.mp4")), 3, False),
    "ObjectRepresentation": (sorted(STIMULI_DIR.glob("ObjectRepresentations/ObjectRep_*.mp4")), 2, True),
    "ActionPrediction": (sorted(STIMULI_DIR.glob("ActionPrediction/AP_*.mp4")), 2, False),
    "Geometry": (sorted(STIMULI_DIR.glob("Geometry/Geo_*.mp4")), 2, False),
    "ANS_easy": ([STIMULI_DIR / f"Numerosity/{name}.mp4" for name in ("ANS_6_24", "ANS_24_6")], 2, True),
    "ANS_hard": ([STIMULI_DIR / f"Numerosity/{name}.mp4" for name in ("ANS_6_12", "ANS_12_6")], 2, True),
    "Attention": ([STIMULI_DIR / f"AttentionGrabbers/attention{i}.mp4" for i in (2, 3)], 1, False),
    "Attention2": ([STIMULI_DIR / f"AttentionGrabbers/attention{i}.mp4" for i in (4, 6)], 1, False),
    "Attention3": ([STIMULI_DIR / f"AttentionGrabbers/attention{i}.mp4" for i in (2, 3, 4, 6)], 1, False),
}
RELATION_NEUTRAL = sorted(STIMULI_DIR.glob("Relations/01 NATURAL/*.mp4"))
RELATION_VIOLATION = sorted(STIMULI_DIR.glob("Relations/02 VIOLATION/*.mp4"))


def shuffled_pool(files, rng):
    """Keep unused movies across blocks; refill only after the pool is empty."""
    if not files:
        raise ValueError("Cannot sample from an empty movie pool")
    while True:
        remaining = list(files)
        rng.shuffle(remaining)
        yield from remaining


def generate_subject(subject_id, seed):
    rng = random.Random(seed)
    pools = {
        name: shuffled_pool(files, rng)
        for name, (files, count, replace) in CATEGORIES.items()
        if not replace
    }
    neutral_pool = shuffled_pool(RELATION_NEUTRAL, rng)
    violation_pool = shuffled_pool(RELATION_VIOLATION, rng)
    rows = []

    for block in range(1, N_BLOCKS + 1):
        category_order = list(CATEGORIES) + ["Relations"]
        rng.shuffle(category_order)
        trial = 0
        for category in category_order:
            if category == "Relations":
                videos = [next(neutral_pool), next(violation_pool)]
                rng.shuffle(videos)
            else:
                files, count, replace = CATEGORIES[category]
                if replace:
                    videos = rng.choices(files, k=count)
                else:
                    videos = [next(pools[category]) for _ in range(count)]
            for video in videos:
                trial += 1
                rows.append({
                    "subject_id": subject_id,
                    "seed": seed,
                    "block": block,
                    "trial": trial,
                    "category": category,
                    "video": video.relative_to(STIMULI_DIR).as_posix(),
                })
    return rows


def main():
    # Check all source pools before creating the output file.
    all_pools = [files for files, count, replace in CATEGORIES.values()]
    all_pools += [RELATION_NEUTRAL, RELATION_VIOLATION]
    for files in all_pools:
        if not files:
            raise ValueError("A stimulus pool is empty; check the movie folders")
        for movie in files:
            if not movie.is_file():
                raise FileNotFoundError(movie)

    rows = []
    for number in range(1, N_SUBJECTS + 1):
        seed = MASTER_SEED + number
        rows.extend(generate_subject(f"S{number:03d}", seed))

    output = STIMULI_DIR / "sequences.csv"
    # Exclusive creation protects schedules already assigned to participants.
    with output.open("x", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {N_SUBJECTS} subjects, {len(rows)} movie rows to {output}")


if __name__ == "__main__":
    main()
