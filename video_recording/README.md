# Standalone webcam recorder

`video_recording/webcam_recorder.py` captures and saves video in a separate Python process. It
does not import PsychoPy, show a preview window, record audio, or change any
experiment. Defaults: camera 0, 640 × 480, 30 fps, MJPEG in an AVI file.

OpenCV must be installed in the Python environment used to run it. Check with
`python -c "import cv2; print(cv2.__version__)"`; if missing, install
`opencv-python` in that environment. No project dependencies have been changed.
The existing `.pixi/envs/default` environment already has OpenCV installed.

## How it works

```text
Study process: send_text("Trial 1") → bounded, non-blocking message queue
                                           ↓
Recording process: webcam → one-frame text overlay → AVI + timing CSV
```

The study sends only short labels and their timestamps. Capture, text drawing,
encoding, timing-file writes and error logging happen in the recording process.
No video frames are transferred back to PsychoPy. The recorder uses MJPEG
(`MJPG`) in an AVI container, at a constant playback rate of 30 fps by default.
This keeps the encoding simple, but produces larger files than H.264/MP4.

Folder contents:

- `webcam_recorder.py`: recorder and standalone interactive demo.
- `test_webcam_recorder.py`: hardware-free unit and spawned-process tests.
- `__init__.py`: marks the folder as an importable Python package.
- `README.md`: this guide.

## Standalone test

```powershell
pixi run python -m video_recording.webcam_recorder webcam-test.avi
```

Enter short ASCII labels; each is drawn on **one frame only**. Enter `/quit` to
finish the file. Use a new output filename for every recording.
Run this command from the project root (the folder containing `pixi.toml`).
To use another webcam, add `--camera 1`. If not using Pixi, use the same command
without `pixi run`, in a Python environment with OpenCV installed.

## Text appearance

- **Top-left:** `Frame 0`, `Frame 1`, etc., burned into every saved frame. This
  zero-based number matches the CSV's `frame_index` exactly.
- **Top-right:** the received message, shown on one frame only, in black text
  on a solid white rectangle. It uses scale `1.0` (roughly 22 pixels tall), a
  2-pixel stroke, and 8 pixels of padding inside the rectangle. No message means
  no rectangle is drawn.
- The frame number stays at scale `0.7` (roughly 16 pixels tall), white with a
  black outline. Both use OpenCV's `FONT_HERSHEY_SIMPLEX` and a 10-pixel outer
  margin. Long messages are automatically scaled down to fit beside the frame
  number; keep labels short for readability. The full text stays in the CSV
  even when drawn smaller.

## Future Coder integration (example only)

The recorder is standalone and is not currently integrated into any study.

```python
from video_recording.webcam_recorder import WebcamRecorder
from pathlib import Path

def main():
    # Pass the study's existing participant data directory, preferably absolute.
    subject_data = Path("InformationGain/data/S001").resolve()
    recorder = WebcamRecorder.for_subject(subject_data)
    recording_started = recorder.start()  # Before timing-critical work.
    try:
        # Existing experiment runs here.
        accepted = recorder.send_text("Trial 1")
        # False means unavailable/full/invalid; continue the experiment normally.
    finally:
        recorder.stop()  # After timing-critical work; closes the video file.
    # Optional: inspect recorder.last_error after the experiment, not each frame.

if __name__ == "__main__":
    main()
```

On Windows, the **experiment's executable code must be inside a main guard**:
the spawned process imports the script. Without that guard, an existing Coder
script can accidentally launch the experiment again. The module must also be
on that script's Python import path. These integration changes have not been
applied to any study.

If you launch a study directly from a subfolder and the import is not found,
add the project root to the study's import path before importing the recorder.
For a script located one folder below the project root (e.g.
`InformationGain/InformationGain.py`), that would be:

```python
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
from video_recording.webcam_recorder import WebcamRecorder
```

Use the study's actual participant data path rather than relying on the current
working directory. For that same script layout, for example:
`subject_data = Path(__file__).resolve().parent / "data" / "S001"`.

## Output location and timing files

`WebcamRecorder.for_subject(subject_data_dir)` generates a unique filename and
creates missing directories when started. For example:

```text
InformationGain/data/S001/video/
    recording_20261014_153000_a1b2c3d4.avi
    recording_20261014_153000_a1b2c3d4.csv
    recording_20261014_153000_a1b2c3d4.json
    recording_20261014_153000_a1b2c3d4.errors.txt  (only on a worker error)
```

Alternatively pass an exact filename: `WebcamRecorder(subject_data / "video" /
"session1.avi")`. Existing video or sidecar files are never intentionally
overwritten; use the unique helper for repeat recordings.

The CSV has one row per frame written, with zero-based `frame_index`, fixed-rate
`video_time_s`, `capture_received_ns`, `message_sent_ns`, `message_received_ns`,
and `text`. Message fields are empty for unlabelled frames. All `*_ns` fields use
Python's shared monotonic `time.perf_counter_ns()` clock, not the PsychoPy clock.
Subtract send from receive to estimate message transport/queue delay. A frame's
capture time can precede the message send time because messages are checked after
capture. Capture time is **not** the camera exposure time. The JSON describes the
clock and stores a near-simultaneous monotonic/Unix-time anchor and video settings.

CSV writes are buffered and flushed about once per second and on clean shutdown.
A crash may lose the tail of the CSV/video. Rows describe submitted video frames;
OpenCV does not acknowledge durable disk writes or report every encoder failure.
Messages not recorded (queue rejection, immediate stop or crash) have no CSV row.

## Failure isolation

- `start`, `send_text`, and `stop` return booleans. Operational failures do not
  raise into the experiment; `last_error` holds the latest detected error.
- `start` and `stop` can wait, so keep them outside timing-critical trials.
  Shutdown waits up to the requested timeout plus a bounded termination wait.
- Worker crashes, closed queues/pipes, permission errors and shutdown failures
  are handled. A hung worker is terminated during shutdown; the experiment does
  not wait indefinitely. An OS-level termination failure cannot be guaranteed away.
- Error files are best-effort and written only by the worker; no filesystem
  logging happens in `send_text`. Native crashes/forced termination may produce
  no error file. Parent startup failures are available through `last_error`.
- Constructor configuration errors still raise `ValueError`: they are coding
  errors to fix before running the study. Invalid message text returns `False`.
- A recorder context manager will not mask an exception from your experiment
  while closing the recorder.

## Timing and load

- `send_text` only queues a short string. It never waits for capture/encoding or
  for queue space; the bounded queue holds at most 32 pending labels.
- The worker checks for one message per frame, after capture and before writing.
  That message is drawn on that frame, not subsequent frames. Multiple queued
  messages appear on successive frames, in order. Frames without messages still
  show their frame number.
- Receipt means **dequeued by the recorder**, not when the main process called
  `send_text`. Queue transport, camera buffering and scheduling introduce delay.
  This is a visual marker, not precise stimulus/video synchronization.
- Accepted messages are not delivery acknowledgments. Stopping immediately can
  discard pending labels. A dead worker causes `send_text` to return `False`.
  Worker errors are collected on the next send or stop, not continuously polled.
- AVI uses the configured fixed playback frame rate. Actual capture cadence can
  differ; the CSV records receive timing but does not compensate for dropped frames.
- The requested camera resolution/rate is best-effort. Actual frame dimensions
  are used for encoding. Long labels are reduced in size to fit the top row.
- CPU, USB and disk remain shared with PsychoPy. Compare PsychoPy dropped frames
  with recording on/off on the actual experiment machine; zero impact cannot be
  guaranteed. There is no preview, frame transport to the main process, or busy
  polling loop in the experiment. OpenCV's processing thread count is limited
  to one in the worker (the camera/codec backend may still use its own threads).
- Always stop explicitly. Forced termination or interpreter exit may leave the
  video incomplete. A timeout forces shutdown and returns `False`.

## Hardware-free tests

```powershell
pixi run python -m unittest video_recording.test_webcam_recorder -v
```

Includes an actual spawned process with a synthetic camera backend; no webcam
is activated by these tests.
