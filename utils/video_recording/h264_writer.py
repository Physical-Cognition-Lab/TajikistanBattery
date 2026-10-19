"""Small FFmpeg hardware-H.264 writer, used only in the recording process."""

import shutil
import subprocess
from pathlib import Path


ENCODERS = {
    "h264_nvenc": ["-preset", "p1", "-tune", "ll", "-rc", "cbr"],
    "h264_qsv": ["-preset", "veryfast"],
    "h264_amf": ["-usage", "lowlatency", "-quality", "speed"],
}


def _command(ffmpeg, width, height, fps, encoder, bitrate):
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-filter_threads", "1", "-threads", "1",
        "-f", "rawvideo", "-pixel_format", "bgr24",
        "-video_size", f"{width}x{height}", "-framerate", str(fps),
        "-i", "pipe:0", "-an", "-c:v", encoder, *ENCODERS[encoder],
        "-pix_fmt", "yuv420p", "-b:v", str(bitrate),
        "-maxrate", str(bitrate), "-bufsize", str(2 * bitrate),
        "-g", str(max(1, round(2 * fps))), "-bf", "0", "-threads", "1",
        "-fps_mode", "passthrough",
    ]


def _select_encoder(ffmpeg, encoder, fps, bitrate, width=640, height=480):
    candidates = ENCODERS if encoder == "auto" else [encoder]
    failures = []
    for candidate in candidates:
        command = _command(ffmpeg, width, height, fps, candidate, bitrate)
        command += ["-frames:v", "1", "-f", "null", "-"]
        try:
            result = subprocess.run(
                command, input=bytes(width * height * 3), stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                return candidate
            detail = result.stderr.decode("utf-8", errors="replace")[:500]
            failures.append(f"{candidate}: {detail.strip()}")
        except subprocess.TimeoutExpired:
            failures.append(f"{candidate}: hardware probe timed out")
    raise RuntimeError("No working hardware H.264 encoder. " + "; ".join(failures))


class H264Writer:
    def __init__(self, output, width, height, fps, encoder, bitrate, ffmpeg):
        executable = shutil.which(str(ffmpeg))
        if not executable:
            raise FileNotFoundError("FFmpeg not found; install it or pass ffmpeg=its_path")
        self.encoder = _select_encoder(executable, encoder, fps, bitrate, width, height)
        self._size = (height, width, 3)
        self._log_path = Path(output).with_suffix(".ffmpeg.log")
        self._log = self._log_path.open("xb")
        command = _command(executable, width, height, fps, self.encoder, bitrate)
        # Fragmented MP4 retains completed fragments if recording is interrupted.
        command += ["-movflags", "+frag_keyframe+empty_moov+default_base_moof",
                    "-f", "mp4", str(output)]
        try:
            self._process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=self._log, bufsize=0,
                creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                               | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)),
            )
        except Exception:
            self._log.close()
            raise

    def write(self, frame):
        if frame.shape != self._size:
            raise ValueError(f"Expected BGR frame shape {self._size}, got {frame.shape}")
        if self._process.poll() is not None:
            raise RuntimeError(f"Hardware encoder stopped; see {self._log_path}")
        data = memoryview(frame.tobytes())
        while data:
            count = self._process.stdin.write(data)
            if not count:
                raise RuntimeError("Hardware encoder stopped accepting frames")
            data = data[count:]

    def release(self):
        error = None
        try:
            try:
                self._process.stdin.close()
            except OSError as exc:
                error = exc
            try:
                code = self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1)
                raise TimeoutError("Hardware encoder did not finish; MP4 may be incomplete")
            if code != 0:
                raise RuntimeError(f"Hardware encoder exited with code {code}; see {self._log_path}")
            if error is not None:
                raise error
        finally:
            self._log.close()
