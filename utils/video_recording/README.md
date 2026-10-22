# Standalone webcam recorder

`utils/video_recording/webcam_recorder.py` captures and saves video in a separate Python process. It
does not import PsychoPy, show a preview window, record audio, or change any
experiment. Defaults: camera 0, **640 × 480, 15 fps, hardware H.264 in MP4**,
targeting **1 Mbps** (approximately 450 MB/hour, plus a small JSON event record
and a normally empty FFmpeg log).

OpenCV must be installed in the Python environment used to run it. Check with
`python -c "import cv2; print(cv2.__version__)"`; if missing, install
`opencv-python` in that environment. No project dependencies have been changed.
The existing `.pixi/envs/default` environment already has OpenCV installed.
FFmpeg must also be available on `PATH`, built with a supported hardware encoder,
and the machine must have the corresponding GPU/driver. Check with
`ffmpeg -version`. Alternatively pass `ffmpeg=r"C:\path\to\ffmpeg.exe"` to
`WebcamRecorder`. No Pixi configuration or study scripts have been changed.

## How it works

```text
Study process: send_text("Trial 1") → bounded, non-blocking message queue
                                           ↓
Recording process: webcam → resize/rate limit → text overlay → FFmpeg → MP4
                                                        ↘ event JSON
```

The study sends only short labels. Capture, text drawing, encoding, the event
JSON and error logging all happen in the recording process. No video frames are
transferred back to PsychoPy. Frames go from the recording process to an FFmpeg
subprocess, which performs hardware H.264 encoding at a constant playback rate
of 15 fps. OpenCV processing and FFmpeg filtering are limited to one thread;
FFmpeg runs below normal priority on Windows. Backend capture/driver threads are
outside this limit.

`encoder="auto"` probes NVIDIA NVENC (`h264_nvenc`), Intel Quick Sync
(`h264_qsv`), then AMD AMF (`h264_amf`) before recording. It actually encodes a
test frame, rather than trusting the list of compiled-in encoders. Only hardware
encoders are tried: there is **no silent software-encoding fallback**. If none
works, `start()` returns `False` and `last_error` explains why. To pin a known
device, use `encoder="h264_nvenc"`, for example. You can change the target bitrate
with `bitrate=1_000_000` (bits/second); actual file sizes vary slightly.

This machine's RTX 4060 has been tested successfully with NVENC. Intel/AMD
selection is implemented but has not been tested here on those GPUs. Hardware
encoding still shares system resources with PsychoPy; measure experiment timing
on the intended machine rather than assuming no interference.

Folder contents:

- `webcam_recorder.py`: recorder and standalone interactive demo.
- `h264_writer.py`: hardware encoder selection and FFmpeg pipe/shutdown handling.
- `demo_random_messages.py`: eleven-second live-webcam test with random labels.
- `test_webcam_recorder.py`: hardware-free unit and spawned-process tests.
- `test_h264_writer.py`: hardware-free tests for FFmpeg selection and failures.
- `__init__.py`: marks the folder as an importable Python package.
- `README.md`: this guide.

## Standalone test

```powershell
pixi run python -m utils.video_recording.webcam_recorder webcam-test.mp4
```

Enter short ASCII labels; each is drawn on **one frame only**. Enter `/quit` to
finish the file. Use a new output filename for every recording.
Run this command from the project root (the folder containing `pixi.toml`).
To use another webcam, add `--camera 1`. If not using Pixi, use the same command
without `pixi run`, in a Python environment with OpenCV installed.

For an automatic webcam test with ten random messages, about one second apart:

```powershell
pixi run python -m utils.video_recording.demo_random_messages
```

This records about eleven seconds under `Data/webcam_demo/video/`, verifies the
labels recorded in the JSON against the ones it sent, and extracts a
`.preview.png` showing the first labelled frame. Each message lasts only one
frame. It activates the real webcam; use `--camera 1` to select another device.
These local demo recordings are excluded from Git by the existing `Data/` ignore
rule.

## Text appearance

- **Top-left:** `Frame 0`, `Frame 1`, etc., burned into every saved frame. This
  zero-based number is the frame's index in the saved video.
- **Top-right:** the received message, shown on one frame only. No message means
  no rectangle is drawn.
- Both use the same style: black text on a solid white rectangle, OpenCV's
  `FONT_HERSHEY_SIMPLEX`, a 2-pixel stroke, 8 pixels of padding inside the box and
  a 10-pixel outer margin. The frame number uses scale `0.7` (roughly 16 pixels
  tall), the message scale `1.0` (roughly 22 pixels tall). Long messages are
  automatically scaled down to fit beside the frame number; keep labels short for
  readability. The full text is still stored in the JSON even when it is drawn
  smaller.

## Future Coder integration (example only)

The recorder is standalone and is not currently integrated into any study.

```python
from utils.video_recording.webcam_recorder import WebcamRecorder
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
from utils.video_recording.webcam_recorder import WebcamRecorder
```

Use the study's actual participant data path rather than relying on the current
working directory. For that same script layout, for example:
`subject_data = Path(__file__).resolve().parent / "data" / "S001"`.

## Output files

`WebcamRecorder.for_subject(subject_data_dir)` generates a unique filename and
creates missing directories when started. For example:

```text
InformationGain/data/S001/video/
    recording_20261014_153000_a1b2c3d4.mp4
    recording_20261014_153000_a1b2c3d4.json
    recording_20261014_153000_a1b2c3d4.ffmpeg.log  (encoder diagnostics; normally empty)
    recording_20261014_153000_a1b2c3d4.errors.txt  (only on a worker error)
```

Alternatively pass an exact filename: `WebcamRecorder(subject_data / "video" /
"session1.mp4")`. Existing video, JSON, log or error files are never
intentionally overwritten; use the unique helper for repeat recordings.

The JSON pairs labels with frames. It records the video name, codec, selected
encoder, playback fps, output size, camera index, the clock declaration and a
near-simultaneous monotonic/Unix anchor, plus one entry per recorded label:

```json
{
  "video": "recording_20261014_153000_a1b2c3d4.mp4",
  "codec": "H.264",
  "encoder": "h264_nvenc",
  "playback_fps": 15.0,
  "width": 640,
  "height": 480,
  "camera": 0,
  "clock": "time.perf_counter_ns",
  "clock_anchor_monotonic_ns": 8123456789012,
  "clock_anchor_unix_ns": 1760000000123456789,
  "events": [
    {"frame_index": 137, "text": "Trial 1", "sent_ns": 8120000000000, "received_ns": 8120050000000}
  ]
}
```

`frame_index` matches the `Frame N` burned into that video frame, and `text` is
the label the study passed to `send_text`. `sent_ns` is taken in the study
process, `received_ns` when the recorder dequeued it; both use the same
`time.perf_counter_ns` clock, so their difference estimates queue delay. Frames
without a label get no entry, so the file stays a few kilobytes per session.
Convert a stamp to Unix time with
`clock_anchor_unix_ns + (stamp_ns - clock_anchor_monotonic_ns)` to line it up
with the study's event table or eye-tracker log.

The JSON is written once, in the worker, when recording stops. A killed worker
or a crash produces no JSON at all, even if the MP4 is partly recoverable; it
never leaves a half-written file. Encoder errors are detected on writes and
shutdown, with FFmpeg details in the `.ffmpeg.log` file. The MP4 is fragmented
at keyframes (about every two seconds) so completed fragments can often be
recovered after interruption; the last fragment may be lost. This is not a
guarantee against file corruption, disk failure, or forced termination.
Messages not recorded (queue rejection, immediate stop before the next frame, or
a crash) never appear in the JSON: it describes what was encoded, not what the
study intended to send.

## Failure isolation

- `start`, `send_text`, and `stop` return booleans. Operational failures do not
  raise into the experiment; `last_error` holds the latest detected error.
- `start` and `stop` can wait, so keep them outside timing-critical trials.
  Startup has a 20-second default timeout, including hardware probing; an encoder
  probe has a four-second timeout. Encoding failures do not launch software H.264.
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
- MP4 uses the configured fixed playback frame rate. Actual capture cadence can
  differ; the JSON stores no per-frame timeline and does not compensate for
  dropped frames.
- Camera mode requests are best-effort (DirectShow on Windows), but **saved output
  is always the requested size**. Larger camera frames are resized before drawing
  overlays. Excess capture frames are discarded to target 15 saved frames/second;
  their messages are not consumed until a frame is selected for encoding. Timing
  jitter is tolerated; there is no catch-up burst after a delay.
- This webcam still delivered 1920 × 1080 despite requests for 640 × 480, even
  with DirectShow and MJPEG capture-mode requests. Output was verified at
  640 × 480/15 fps, but decoding and resizing a larger source still cost CPU.
  A webcam that supports native 640 × 480 capture would reduce that work.
- There is no frame duplication to fill gaps. If capture/encoding is slower than
  15 fps, playback will run faster than real time; use the JSON entry's
  `frame_index` and `*_ns` stamps, or the study's own logs, for actual timing.
  One-frame messages have approximately 67 ms granularity at 15 fps.
- CPU, USB and disk remain shared with PsychoPy. Compare PsychoPy dropped frames
  with recording on/off on the actual experiment machine; zero impact cannot be
  guaranteed. There is no preview, frame transport to the main process, or busy
  polling loop in the experiment. OpenCV's processing thread count is limited
  to one in the worker (the camera/codec backend may still use its own threads).
- Always stop explicitly. Forced termination or interpreter exit may leave the
  video incomplete. A timeout forces shutdown and returns `False`.

## Hardware-free tests

Includes an actual spawned process with synthetic capture/encoding backends;
no webcam, GPU or FFmpeg installation is required by these unit tests. Run the
random-message demo separately to validate the real camera and hardware encoder.
