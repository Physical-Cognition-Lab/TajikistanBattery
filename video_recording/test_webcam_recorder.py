"""Hardware-free tests: python -m unittest video_recording.test_webcam_recorder -v."""

import csv
import json
import queue
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from video_recording.webcam_recorder import WebcamRecorder, _draw_overlays, _record


class WorkerTests(unittest.TestCase):
    def run_worker(self, labels=(), fail_capture=False, fail_writer=False):
        stop = threading.Event()
        messages = queue.Queue()
        for label in labels:
            messages.put((label, 100))
        frames = [SimpleNamespace(shape=(240, 320, 3), label=None) for _ in range(3)]
        capture = Mock()
        capture.isOpened.return_value = not fail_capture
        capture.read.side_effect = [(True, frame) for frame in frames]
        writer = Mock()
        writer.isOpened.return_value = not fail_writer
        written = []

        def write(frame):
            written.append(frame.label)
            if len(written) == 3:
                stop.set()

        def put_text(frame, text, *args):
            if not text.startswith("Frame "):
                frame.label = text

        writer.write.side_effect = write
        cv2 = SimpleNamespace(
            setNumThreads=Mock(),
            VideoCapture=Mock(return_value=capture),
            VideoWriter=Mock(return_value=writer),
            VideoWriter_fourcc=Mock(return_value=123),
            putText=Mock(side_effect=put_text),
            rectangle=Mock(),
            getTextSize=Mock(side_effect=lambda text, font, scale, thickness:
                             ((round(len(text) * 10 * scale), round(20 * scale)), 5)),
            CAP_PROP_FRAME_WIDTH=1, CAP_PROP_FRAME_HEIGHT=2, CAP_PROP_FPS=3,
            FONT_HERSHEY_SIMPLEX=0, LINE_AA=16,
        )
        status = Mock()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "test.avi"
            self.output_path = str(output)
            with patch.dict("sys.modules", {"cv2": cv2}):
                _record(str(output), 0, 640, 480, 30, "MJPG", messages, stop, status)
            if output.with_suffix(".csv").exists():
                with output.with_suffix(".csv").open(newline="", encoding="utf-8") as file:
                    self.rows = list(csv.DictReader(file))
                self.metadata = json.loads(output.with_suffix(".json").read_text())
            self.has_error_log = output.with_suffix(".errors.txt").exists()
        return written, capture, writer, cv2, status

    def test_label_is_only_on_one_frame(self):
        written, capture, writer, cv2, status = self.run_worker(["Trial 1"])
        self.assertEqual(written, ["Trial 1", None, None])
        status.send.assert_called_once_with(("ready", None))
        cv2.VideoWriter.assert_called_once_with(self.output_path, 123, 30, (320, 240))
        self.assertEqual([row["text"] for row in self.rows], ["Trial 1", "", ""])
        self.assertEqual(self.rows[0]["message_sent_ns"], "100")
        self.assertGreater(int(self.rows[0]["message_received_ns"]), 100)
        self.assertTrue(all(int(row["capture_received_ns"]) > 0 for row in self.rows))
        self.assertEqual(self.rows[2]["frame_index"], "2")
        self.assertAlmostEqual(float(self.rows[2]["video_time_s"]), 2 / 30)
        self.assertEqual(self.metadata["width"], 320)
        capture.release.assert_called_once()
        writer.release.assert_called_once()
        status.close.assert_called_once()

    def test_labels_are_fifo_on_separate_frames(self):
        written, *_ = self.run_worker(["First", "Second"])
        self.assertEqual(written, ["First", "Second", None])

    def test_no_label_means_no_overlay(self):
        written, _, _, cv2, _ = self.run_worker()
        self.assertEqual(written, [None, None, None])
        labels = [call.args[1] for call in cv2.putText.call_args_list]
        self.assertEqual(labels, ["Frame 0", "Frame 0", "Frame 1", "Frame 1",
                                  "Frame 2", "Frame 2"])

    def test_camera_failure_is_reported(self):
        written, capture, _, cv2, status = self.run_worker(fail_capture=True)
        self.assertEqual(written, [])
        self.assertEqual(status.send.call_args.args[0][0], "error")
        self.assertTrue(self.has_error_log)
        capture.release.assert_called_once()
        cv2.VideoWriter.assert_not_called()

    def test_writer_failure_releases_resources(self):
        _, capture, writer, _, status = self.run_worker(fail_writer=True)
        self.assertEqual(status.send.call_args.args[0][0], "error")
        capture.release.assert_called_once()
        writer.release.assert_called_once()


class RecorderTests(unittest.TestCase):
    def test_send_is_nonblocking_when_queue_is_full(self):
        recorder = WebcamRecorder("test.avi", queue_size=1)
        recorder._process = Mock()
        recorder._process.is_alive.return_value = True
        recorder._messages = queue.Queue(maxsize=1)
        self.assertTrue(recorder.send_text("First"))
        self.assertFalse(recorder.send_text("Second"))
        self.assertEqual(recorder._messages.get_nowait()[0], "First")

    def test_send_before_start_fails(self):
        recorder = WebcamRecorder("test.avi")
        self.assertFalse(recorder.send_text("Trial"))
        self.assertIn("not running", recorder.last_error)

    def test_invalid_text_is_rejected(self):
        recorder = WebcamRecorder("test.avi")
        for text in ("", "line\nbreak", "é", "x" * 201, None):
            with self.subTest(text=text):
                self.assertFalse(recorder.send_text(text))

    def test_invalid_configuration_is_rejected(self):
        for options in ({"fps": 0}, {"fps": float("nan")}, {"width": 0},
                        {"height": -1}, {"queue_size": 0}, {"codec": "bad"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                WebcamRecorder("test.avi", **options)

    def test_existing_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.avi"
            output.write_bytes(b"keep")
            recorder = WebcamRecorder(output)
            self.assertFalse(recorder.start())
            self.assertIn("FileExistsError", recorder.last_error)
            self.assertEqual(output.read_bytes(), b"keep")

    def test_stop_before_start_is_safe(self):
        WebcamRecorder("test.avi").stop()

    def test_subject_folder_created_and_names_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            subject = Path(directory) / "study" / "data" / "S001"
            recorder = WebcamRecorder.for_subject(subject)
            self.assertEqual(recorder.output.parent, subject / "video")
            self.assertNotEqual(recorder.output, WebcamRecorder.for_subject(subject).output)
            with patch.object(recorder, "_start"):
                self.assertTrue(recorder.start())
            self.assertTrue((subject / "video").is_dir())

    def test_directory_error_does_not_raise(self):
        recorder = WebcamRecorder("test.avi")
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            self.assertFalse(recorder.start())
        self.assertIn("denied", recorder.last_error)
        self.assertFalse(recorder.send_text("Trial"))

    def test_dead_worker_does_not_raise(self):
        recorder = WebcamRecorder("test.avi")
        recorder._process = Mock()
        recorder._process.is_alive.return_value = False
        self.assertFalse(recorder.send_text("Trial"))

    def test_queue_transport_error_does_not_raise(self):
        recorder = WebcamRecorder("test.avi")
        recorder._process = Mock()
        recorder._process.is_alive.return_value = True
        recorder._messages = Mock()
        recorder._messages.put_nowait.side_effect = OSError("broken queue")
        self.assertFalse(recorder.send_text("Trial"))
        self.assertIn("broken queue", recorder.last_error)

    def test_worker_error_is_saved_without_raising(self):
        recorder = WebcamRecorder("test.avi")
        recorder._status = Mock()
        recorder._status.poll.return_value = True
        recorder._status.recv.return_value = ("error", "camera failed")
        self.assertFalse(recorder.send_text("Trial"))
        self.assertEqual(recorder.last_error, "camera failed")

    def test_stop_error_does_not_raise_or_mask_experiment_error(self):
        recorder = WebcamRecorder("test.avi")
        recorder._process = Mock()
        recorder._process.is_alive.return_value = False
        recorder._process.exitcode = 1
        recorder._stop = Mock()
        recorder._messages = Mock()
        recorder._status = Mock()
        recorder._status.poll.side_effect = OSError("broken pipe")
        with self.assertRaisesRegex(ValueError, "experiment failure"):
            try:
                raise ValueError("experiment failure")
            finally:
                self.assertFalse(recorder.stop())
        self.assertIn("broken pipe", recorder.last_error)

    def test_forced_stop_has_bounded_wait(self):
        recorder = WebcamRecorder("test.avi")
        recorder._process = Mock()
        recorder._process.is_alive.side_effect = [True, False]
        recorder._process.exitcode = -15
        recorder._stop = Mock()
        process = recorder._process
        self.assertFalse(recorder.stop(timeout=0.01))
        process.terminate.assert_called_once()
        self.assertEqual(process.join.call_args_list[0].args, (0.01,))
        self.assertEqual(process.join.call_args_list[1].args, (1.0,))
        self.assertIn("incomplete", recorder.last_error)


class SpawnTests(unittest.TestCase):
    def test_real_spawn_with_synthetic_camera(self):
        # Exercise actual Windows spawn/queues/files without activating a camera.
        backend = '''
import os
import time
from types import SimpleNamespace
CAP_PROP_FRAME_WIDTH = 1
CAP_PROP_FRAME_HEIGHT = 2
CAP_PROP_FPS = 3
FONT_HERSHEY_SIMPLEX = 0
LINE_AA = 16
def setNumThreads(value): pass
def VideoWriter_fourcc(*args): return 123
def putText(*args): pass
def rectangle(*args): pass
def getTextSize(text, font, scale, thickness):
    return ((round(len(text) * 10 * scale), round(20 * scale)), 5)
class VideoCapture:
    def __init__(self, camera):
        self.camera = camera
        self.reads = 0
    def isOpened(self): return self.camera != -1
    def set(self, *args): pass
    def read(self):
        time.sleep(0.01)
        self.reads += 1
        if self.reads == 6:
            if self.camera == -2: raise RuntimeError('camera disconnected')
            if self.camera == -3: os._exit(7)
        return True, SimpleNamespace(shape=(240, 320, 3))
    def release(self): pass
class VideoWriter:
    def __init__(self, output, *args): self.file = open(output, 'wb')
    def isOpened(self): return True
    def write(self, frame): self.file.write(b'frame')
    def release(self): self.file.close()
'''
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "cv2.py").write_text(backend, encoding="utf-8")
            with patch.object(sys, "path", [directory] + sys.path):
                recorder = WebcamRecorder.for_subject(Path(directory) / "data" / "S001")
                self.assertTrue(recorder.start(), recorder.last_error)
                try:
                    self.assertTrue(recorder.send_text("Trial 1"))
                    deadline = time.monotonic() + 4
                    found = False
                    while time.monotonic() < deadline:
                        with recorder.output.with_suffix(".csv").open(encoding="utf-8") as file:
                            found = "Trial 1" in file.read()
                        if found:
                            break
                        time.sleep(0.05)
                    self.assertTrue(found, "Label was not received by spawned worker")
                finally:
                    self.assertTrue(recorder.stop(), recorder.last_error)
                self.assertTrue(recorder.output.exists())
                with recorder.output.with_suffix(".csv").open(newline="", encoding="utf-8") as file:
                    rows = list(csv.DictReader(file))
                self.assertEqual(sum(row["text"] == "Trial 1" for row in rows), 1)
                failed = WebcamRecorder.for_subject(Path(directory) / "data" / "S002", camera=-1)
                self.assertFalse(failed.start())
                self.assertFalse(failed.send_text("Trial"))
                self.assertTrue(failed.output.with_suffix(".errors.txt").exists())
                for camera in (-2, -3):
                    with self.subTest(camera=camera):
                        crashed = WebcamRecorder.for_subject(
                            Path(directory) / "data" / "S003", camera=camera)
                        self.assertTrue(crashed.start(), crashed.last_error)
                        try:
                            crashed._process.join(4)
                            self.assertFalse(crashed._process.is_alive())
                            self.assertFalse(crashed.send_text("After crash"))
                        finally:
                            self.assertFalse(crashed.stop())
                        self.assertIsNotNone(crashed.last_error)
                        self.assertEqual(crashed.output.with_suffix(".errors.txt").exists(),
                                         camera == -2)


class OverlayTests(unittest.TestCase):
    def backend(self):
        return SimpleNamespace(
            FONT_HERSHEY_SIMPLEX=0, LINE_AA=16, putText=Mock(), rectangle=Mock(),
            getTextSize=Mock(side_effect=lambda text, font, scale, thickness:
                             ((round(len(text) * 10 * scale), round(20 * scale)), 5)),
        )

    def test_frame_top_left_and_message_top_right(self):
        cv2 = self.backend()
        frame = SimpleNamespace(shape=(480, 640, 3))
        _draw_overlays(cv2, frame, 42, "Trial 1")
        number, message = cv2.putText.call_args_list[1:]
        self.assertEqual(number.args[1], "Frame 42")
        self.assertEqual(number.args[2], (10, 24))
        self.assertEqual(message.args[2], (640 - 10 - 8 - 70, 38))
        self.assertEqual(message.args[4], 1.0)
        self.assertEqual(message.args[5], (0, 0, 0))
        self.assertEqual(message.args[6], 2)
        cv2.rectangle.assert_called_once_with(
            frame, (544, 10), (630, 51), (255, 255, 255), -1)

    def test_long_message_shrinks_without_overlapping_frame_number(self):
        cv2 = self.backend()
        frame = SimpleNamespace(shape=(480, 640, 3))
        text = "x" * 200
        _draw_overlays(cv2, frame, 100, text)
        number, message = cv2.putText.call_args_list[1:]
        self.assertLess(message.args[4], 1.0)
        number_width = cv2.getTextSize("Frame 100", 0, 0.7, 1)[0][0]
        self.assertGreaterEqual(message.args[2][0], 10 + number_width + 20)
        self.assertEqual(message.args[1], text)
        self.assertGreaterEqual(cv2.rectangle.call_args.args[1][0],
                                10 + number_width + 20)

    def test_no_message_means_no_white_rectangle(self):
        cv2 = self.backend()
        frame = SimpleNamespace(shape=(480, 640, 3))
        _draw_overlays(cv2, frame, 0, None)
        cv2.rectangle.assert_not_called()
        self.assertEqual(cv2.putText.call_count, 2)


if __name__ == "__main__":
    unittest.main()
