"""Record a short real-webcam demo: python -m utils.video_recording.demo_random_messages."""

import argparse
import json
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
    labels = []
    try:
        for number in range(1, 11):
            time.sleep(1)
            text = f"{random.choice(['Trial', 'Reveal', 'Pause', 'Choose', 'Predict'])} {number}"
            if not recorder.send_text(text):
                raise RuntimeError(recorder.last_error or "Message queue full")
            labels.append(text)
            print(f"Sent: {text}", flush=True)
        time.sleep(1)
    finally:
        stopped = recorder.stop()
    if not stopped:
        raise RuntimeError(recorder.last_error)

    with recorder.output.with_suffix(".json").open(encoding="utf-8") as file:
        events = json.load(file)["events"]
    recorded = [event["text"] for event in events]
    if recorded != labels:
        raise RuntimeError(f"Expected labels {labels}, metadata has {recorded}")

    # Decode the saved file and extract one marked frame for easy inspection.
    import cv2

    video = cv2.VideoCapture(str(recorder.output))
    frame_count = 0
    preview = recorder.output.with_suffix(".preview.png")
    first_label_frame = events[0]["frame_index"]
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
    if frame_count <= first_label_frame:
        raise RuntimeError(f"Video has {frame_count} frames, first label is on {first_label_frame}")
    print(f"Video: {recorder.output}")
    print(f"Preview: {preview}")
    print(f"Verified: {frame_count} decoded frames, {len(labels)} one-frame messages")
    print(f"Video size: {recorder.output.stat().st_size / (1024 * 1024):.2f} MiB")


if __name__ == "__main__":
    main()
