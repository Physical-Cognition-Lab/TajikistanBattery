"""Record a short real-webcam demo: python -m utils.video_recording.demo_random_messages."""

import argparse
import csv
import random
import time
from pathlib import Path

from .webcam_recorder import WebcamRecorder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("Data/webcam_demo"))
    args = parser.parse_args()

    recorder = WebcamRecorder.for_subject(args.output_dir, camera=args.camera)
    if not recorder.start():
        raise RuntimeError(recorder.last_error)
    try:
        for number in range(1, 11):
            time.sleep(1)
            text = f"{random.choice(['Trial', 'Reveal', 'Pause', 'Choose', 'Predict'])} {number}"
            if not recorder.send_text(text):
                raise RuntimeError(recorder.last_error or "Message queue full")
            print(f"Sent: {text}", flush=True)
        time.sleep(1)
    finally:
        stopped = recorder.stop()
    if not stopped:
        raise RuntimeError(recorder.last_error)

    with recorder.output.with_suffix(".csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    labelled = [row for row in rows if row["text"]]
    if len(labelled) != 10:
        raise RuntimeError(f"Expected 10 recorded labels, got {len(labelled)}")

    # Decode the saved file and extract a marked frame for easy inspection.
    import cv2

    video = cv2.VideoCapture(str(recorder.output))
    frame_count = 0
    preview = recorder.output.with_suffix(".preview.png")
    first_label_frame = int(labelled[0]["frame_index"])
    try:
        while True:
            ok, frame = video.read()
            if not ok:
                break
            if frame_count == first_label_frame:
                if not cv2.imwrite(str(preview), frame):
                    raise RuntimeError("Could not save preview")
            frame_count += 1
    finally:
        video.release()
    if frame_count != len(rows):
        raise RuntimeError(f"Video has {frame_count} frames, CSV has {len(rows)} rows")
    print(f"Video: {recorder.output}")
    print(f"Preview: {preview}")
    print(f"Verified: {frame_count} decoded frames, {len(labelled)} one-frame messages")
    print(f"Video size: {recorder.output.stat().st_size / (1024 * 1024):.2f} MiB")


if __name__ == "__main__":
    main()
