"""A bounded Tobii connection check; this does not start gaze recording."""

import sys
from importlib import import_module

from psychopy.gui import haveQt


QtCore = import_module(f"{haveQt}.QtCore")


CHECK_TIMEOUT_MS = 8000

# DeToX uses this same discovery call. Run it separately so a stalled SDK can
# be stopped without freezing the participant dialog or re-running the study.
PROBE = """
import tobii_research as tr
raise SystemExit(0 if tr.find_all_eyetrackers() else 1)
"""


class EyeTrackerCheck:
    """Keep the participant dialog open until the check passes or is unticked."""

    def __init__(self, dlg, checkbox, status, warning):
        self.dlg = dlg
        self.checkbox = checkbox
        self.status = status
        self.warning = warning
        self.passed = False
        self.process = None
        self.closed = False
        self.timer = QtCore.QTimer(dlg)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        checkbox.toggled.connect(self._toggled)
        dlg.finished.connect(self.close)
        # PsychoPy's own number-field validation can re-enable OK on each edit.
        dlg.inputFields[0].textEdited.connect(self._update_ok)
        self._update_ok()
        if checkbox.isChecked():
            QtCore.QTimer.singleShot(0, self.start)

    def _update_ok(self, *args):
        self.dlg.okBtn.setEnabled(not self.checkbox.isChecked() or self.passed)

    def _toggled(self, checked):
        self._stop()
        self.passed = False
        if checked:
            self.start()
        else:
            self.status.setText("")
            self._update_ok()

    def start(self):
        if self.closed or not self.checkbox.isChecked() or self.process is not None:
            return
        self.passed = False
        self._update_ok()
        self.status.setText("Checking...")
        process = QtCore.QProcess(self.dlg)
        self.process = process
        process.finished.connect(
            lambda code, state: self._finished(process, code, state)
        )
        process.errorOccurred.connect(lambda error: self._error(process, error))
        self.timer.start(CHECK_TIMEOUT_MS)
        process.start(sys.executable, ["-c", PROBE])

    def _finished(self, process, code, state):
        if process is not self.process:
            return
        details = bytes(process.readAllStandardError()).decode("utf-8", errors="replace")
        self.process = None
        self.timer.stop()
        process.deleteLater()
        if code == 0 and state == QtCore.QProcess.ExitStatus.NormalExit:
            self.passed = True
            self.status.setText("Eye tracker connected.")
            self._update_ok()
        else:
            if details:
                print(f"Eye-tracker check failed:\n{details}", flush=True)
            message = "No Tobii eye tracker was found."
            if details or state != QtCore.QProcess.ExitStatus.NormalExit:
                message = "The eye-tracker connection check could not complete."
            self._failed(message)

    def _error(self, process, error):
        if process is self.process and error == QtCore.QProcess.ProcessError.FailedToStart:
            self._failed("The eye-tracker connection check could not start.")

    def _timeout(self):
        self._failed("The eye-tracker connection check took too long.")

    def _failed(self, message):
        self._stop()
        if self.closed or not self.checkbox.isChecked():
            return
        self.passed = False
        self.status.setText("Eye-tracker check failed. Retry or uncheck the option.")
        self._update_ok()
        action = self.warning(message)
        if self.closed:
            return
        if action == "retry":
            self.start()
        elif action == "uncheck":
            self.checkbox.setChecked(False)
        else:
            self.dlg.reject()

    def _stop(self):
        self.timer.stop()
        process = self.process
        self.process = None  # Ignore signals from a cancelled or timed-out check.
        if process is not None:
            process.kill()
            process.waitForFinished(1000)
            process.deleteLater()

    def close(self, *args):
        self.closed = True
        self._stop()
