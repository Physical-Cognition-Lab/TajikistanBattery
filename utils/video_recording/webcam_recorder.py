"""Independent webcam recording with one-frame text markers (no PsychoPy imports)."""

import json
import math
import multiprocessing as mp
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Full
from uuid import uuid4

from .h264_writer import ENCODERS, H264Writer


def _draw_overlays(cv2, frame, frame_index, text):
    """Black text on solid white boxes, top-left and top-right."""
    margin = 10
    padding = 8
    number_scale = 0.7
    message_scale = 1.0
    font = cv2.FONT_HERSHEY_SIMPLEX

    def text_size(label, scale):
        (width, height), baseline = cv2.getTextSize(label, font, scale, 2)
        return width, height, baseline

    def boxed(label, scale, left):
        # The white box keeps the label readable against any camera image.
        width, height, baseline = text_size(label, scale)
        cv2.rectangle(frame, (left, margin),
                      (left + width + 2 * padding, margin + height + baseline + 2 * padding),
                      (255, 255, 255), -1)
        cv2.putText(frame, label, (left + padding, margin + padding + height),
                    font, scale, (0, 0, 0), 2, cv2.LINE_AA)
        return width

    number_width = boxed(f"Frame {frame_index}", number_scale, margin)
    if text is not None:
        message_width, _, _ = text_size(text, message_scale)
        available_width = max(1, frame.shape[1] - number_width - 4 * margin - 4 * padding)
        if message_width > available_width:
            message_scale *= available_width / message_width
            message_width, _, _ = text_size(text, message_scale)
        right = frame.shape[1] - margin
        boxed(text, message_scale, right - message_width - 2 * padding)


def _record(output, camera, width, height, fps, encoder, messages, stop, status,
            bitrate=1_000_000, ffmpeg="ffmpeg"):
    output = Path(output)
    capture = writer = metadata = None
    error = None
    try:
        import cv2

        cv2.setNumThreads(1)
        # DirectShow applies camera mode requests more reliably on Windows.
        capture = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open webcam {camera}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, fps)
        ok, frame = capture.read()
        captured_ns = time.perf_counter_ns()
        if not ok:
            raise RuntimeError("Webcam did not return an initial frame")

        # Cameras can ignore mode requests. Always enforce the saved dimensions.
        writer = H264Writer(output, width, height, fps, encoder, bitrate, ffmpeg)
        metadata = {
            "video": output.name, "codec": "H.264", "encoder": writer.encoder,
            "playback_fps": fps, "width": width, "height": height, "camera": camera,
            "clock": "time.perf_counter_ns",
            "clock_anchor_monotonic_ns": time.perf_counter_ns(),
            "clock_anchor_unix_ns": time.time_ns(),
            "events": [],
        }
        status.send(("ready", None))
        frame_index = 0
        interval_ns = round(1_000_000_000 / fps)
        next_frame_ns = captured_ns

        while not stop.is_set():
            # Read/discard excess camera frames, but only encode at the target rate.
            # Do not consume a message until there is a frame to save it on.
            if captured_ns + interval_ns // 2 < next_frame_ns:
                ok, frame = capture.read()
                captured_ns = time.perf_counter_ns()
                if not ok:
                    raise RuntimeError("Webcam stopped returning frames")
                continue
            next_frame_ns += interval_ns
            if next_frame_ns + interval_ns // 2 < captured_ns:
                next_frame_ns = captured_ns + interval_ns
            if frame.shape[:2] != (height, width):
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            try:
                text, sent_ns = messages.get_nowait()
                received_ns = time.perf_counter_ns()
            except Empty:
                text = sent_ns = received_ns = None
            _draw_overlays(cv2, frame, frame_index, text)
            writer.write(frame)
            if text is not None:
                metadata["events"].append({
                    "frame_index": frame_index, "text": text,
                    "sent_ns": sent_ns, "received_ns": received_ns,
                })
            frame_index += 1
            if stop.is_set():
                break
            ok, frame = capture.read()
            captured_ns = time.perf_counter_ns()
            if not ok:
                raise RuntimeError("Webcam stopped returning frames")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        for resource, method in ((writer, "release"), (capture, "release")):
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception as exc:
                    error = error or f"Cleanup failed: {type(exc).__name__}: {exc}"
        if metadata is not None:
            # One dump at the end: a killed worker loses the whole sidecar.
            try:
                with output.with_suffix(".json").open("x", encoding="utf-8") as file:
                    json.dump(metadata, file, indent=2)
            except Exception as exc:
                error = error or f"Metadata write failed: {type(exc).__name__}: {exc}"
        if error:
            # Error logging is best-effort and stays entirely in the worker.
            try:
                with output.with_suffix(".errors.txt").open("a", encoding="utf-8") as log:
                    log.write(f"{datetime.now().isoformat()} {error}\n")
            except Exception:
                pass
            try:
                status.send(("error", error[:2000]))
            except Exception:
                pass
        try:
            status.close()
        except Exception:
            pass


class WebcamRecorder:
    """Spawned recorder; start/stop block, send_text never waits for the worker.

    Each accepted message labels one frame, FIFO. A full queue rejects the message
    (False) instead of delaying the experiment. Call start/stop outside trials.
    Operational errors return False and set last_error; no logging on send_text.
    """

    def __init__(self, output, *, camera=0, width=640, height=480, fps=15.0,
                 encoder="auto", bitrate=1_000_000, ffmpeg="ffmpeg", queue_size=32):
        if any(not isinstance(value, int) or value <= 0
               for value in (width, height, queue_size, bitrate)):
            raise ValueError("width, height, queue_size and bitrate must be positive integers")
        if width % 2 or height % 2:
            raise ValueError("H.264 width and height must be even")
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("fps must be finite and positive")
        if encoder != "auto" and encoder not in ENCODERS:
            raise ValueError("encoder must be auto, h264_nvenc, h264_qsv or h264_amf")
        self.output = Path(output).resolve()
        if self.output.suffix.lower() != ".mp4":
            raise ValueError("Use an .mp4 output filename for hardware H.264")
        self.camera = camera
        self.width = width
        self.height = height
        self.fps = fps
        self.encoder = encoder
        self.bitrate = bitrate
        self.ffmpeg = str(ffmpeg)
        self.queue_size = queue_size
        self._process = None
        self._messages = self._stop = self._status = None
        self.last_error = None
        self._failed = False

    @classmethod
    def for_subject(cls, subject_data_dir, **options):
        """Create a unique recording under <subject_data_dir>/video/."""
        name = f"recording_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.mp4"
        return cls(Path(subject_data_dir) / "video" / name, **options)

    def start(self, timeout=20.0):
        """Create directories and wait for readiness; return False on failure."""
        if self._process is not None:
            self.last_error = "Recorder already started; call stop first"
            return False
        self.last_error = None
        self._failed = False
        try:
            if not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("timeout must be finite and positive")
            self.output.parent.mkdir(parents=True, exist_ok=True)
            for suffix in (self.output.suffix, ".json", ".errors.txt", ".ffmpeg.log"):
                path = self.output.with_suffix(suffix)
                if path.exists():
                    raise FileExistsError(path)
            self._start(timeout)
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._failed = True
            self._shutdown(1.0)
            self._close()
            return False

    def _start(self, timeout):
        context = mp.get_context("spawn")
        self._messages = context.Queue(maxsize=self.queue_size)
        # Never wait for pending labels to flush when the experiment exits.
        self._messages.cancel_join_thread()
        self._stop = context.Event()
        self._status, child_status = context.Pipe(duplex=False)
        self._process = context.Process(
            target=_record,
            args=(str(self.output), self.camera, self.width, self.height,
                   self.fps, self.encoder, self._messages, self._stop, child_status,
                   self.bitrate, self.ffmpeg),
            name="webcam-recorder", daemon=True,
        )
        try:
            self._process.start()
        finally:
            child_status.close()
        try:
            if not self._status.poll(timeout):
                raise TimeoutError("Webcam recorder startup timed out")
            kind, detail = self._status.recv()
            if kind != "ready":
                raise RuntimeError(detail)
        except EOFError as exc:
            raise RuntimeError("Recorder exited during startup") from exc

    def send_text(self, text):
        """Queue a short label; return False if full. Does not wait for a frame.

        True means queued, not yet recorded. OpenCV's built-in font supports
        basic ASCII; labels longer than 200 characters are rejected.
        """
        try:
            if (not isinstance(text, str) or not text or not text.isascii()
                    or len(text) > 200
                    or any(ord(char) < 32 or ord(char) == 127 for char in text)):
                self.last_error = "text must be printable ASCII, 1–200 characters"
                return False
            if self._failed:
                return False
            self._read_error()
            if self._failed:
                return False
            if self._process is None:
                self.last_error = "Recorder is not running"
                return False
            if not self._process.is_alive():
                self.last_error = f"Recorder exited with code {self._process.exitcode}"
                self._failed = True
                return False
            self._messages.put_nowait((text, time.perf_counter_ns()))
        except Full:
            return False
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._failed = True
            return False
        return True

    def _read_error(self):
        try:
            if self._status is None or not self._status.poll():
                return
            kind, detail = self._status.recv()
        except (EOFError, BrokenPipeError):
            # Windows may report a closed worker pipe as WinError 109.
            return
        if kind == "error":
            self.last_error = detail
            self._failed = True

    def stop(self, timeout=10.0):
        """Finish the file; return False on failure. Pending labels may be lost.

        A stuck camera is terminated after timeout, which may leave an incomplete
        video. Always call this explicitly rather than relying on process exit.
        """
        if self._process is None:
            return not self._failed
        try:
            if not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("timeout must be finite and positive")
            if not self._shutdown(timeout):
                self._failed = True
                self.last_error = "Recorder forced to stop; video may be incomplete"
            self._read_error()
            if self._process.exitcode != 0:
                self._failed = True
                self.last_error = self.last_error or f"Recorder exited with code {self._process.exitcode}"
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._failed = True
            self._shutdown(1.0)
        finally:
            self._close()
        return not self._failed

    def _shutdown(self, timeout):
        try:
            if self._process is None or self._process.pid is None:
                return True
            self._stop.set()
            self._process.join(timeout)
            if not self._process.is_alive():
                return True
            self._process.terminate()
            self._process.join(1.0)
        except Exception as exc:
            self.last_error = self.last_error or f"Shutdown failed: {exc}"
        return False

    def _close(self):
        # Retain a stuck process so stop() can be retried, without waiting forever.
        try:
            if self._process is not None and self._process.is_alive():
                self._failed = True
                return
        except Exception:
            pass
        for resource in (self._messages, self._status, self._process):
            if resource is not None:
                try:
                    resource.close()
                except Exception as exc:
                    self.last_error = self.last_error or f"Cleanup failed: {exc}"
                    self._failed = True
        self._process = self._messages = self._stop = self._status = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()


def _demo():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="New MP4 file, e.g. webcam-test.mp4")
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    with WebcamRecorder(args.output, camera=args.camera) as recorder:
        if recorder.last_error:
            print(f"Recording unavailable: {recorder.last_error}")
            return
        print("Recording. Enter a label for one frame; enter /quit to stop.")
        while True:
            try:
                text = input("> ")
            except (EOFError, KeyboardInterrupt):
                break
            if text == "/quit":
                break
            if text and not recorder.send_text(text):
                print(f"Label skipped: {recorder.last_error or 'queue full'}")
    if recorder.last_error:
        print(f"Recorder error: {recorder.last_error}")


if __name__ == "__main__":
    mp.freeze_support()
    _demo()
