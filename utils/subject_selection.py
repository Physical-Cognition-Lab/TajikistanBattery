"""The participant-number window shared by every study.

Every study imports ``get_participant`` from here, so the dialog looks and
behaves the same everywhere: a big ``psychopy.gui.Dlg`` box with a large
participant-number field and optional recording/connection checkboxes below it.

    from utils.subject_selection import get_participant

    subject_id, subjnum, recording, tracker_checked, recalibrate = get_participant(data_dir)

``recording`` is the starting state of the webcam checkbox. Pass
``eye_tracker=False`` to also offer an initially unticked connection check.
The nested Recalibrate checkbox defaults to on. These options do not yet
calibrate the tracker or record gaze data.

Try the window on its own with:

    pixi run python -m utils.subject_selection
"""

from pathlib import Path

from psychopy import core, gui


# --------------------------- Look, edit to taste ---------------------------------
FONT_SIZE = 30          # point size for the whole dialog (labels, field, buttons)
MIN_WIDTH = 900         # the dialog is at least this wide (pixels)
FIELD_HEIGHT = 80       # height of the participant-number box (pixels)
CHECKBOX_SIZE = 44      # size of the tick box under the number (pixels)
WARNING_FONT_SIZE = 24  # the "check the number" pop-up
EYE_TRACKER_FONT_SIZE = 18  # supporting status messages and connection instructions

# The checkbox under the number. Pass another ``recording_label`` for other
# wording, and ``recording`` for its starting state.
RECORDING_LABEL = "Webcam recording"
RECORDING_DEFAULT = False


def _enlarge(dlg, font_size, min_width=0, min_height=0):
    """Make a PsychoPy ``gui.Dlg`` much bigger.

    PsychoPy uses Qt here; the wxPython branch keeps it working elsewhere.
    Setting the font on the dialog also enlarges its labels, field and buttons.
    """
    try:                                   # Qt backend (what PsychoPy uses here)
        font = dlg.font()
        font.setPointSize(font_size)
        dlg.setFont(font)
        dlg.setMinimumSize(min_width, min_height)
    except AttributeError:                 # wxPython backend
        font = dlg.GetFont()
        font.SetPointSize(font_size)
        dlg.SetFont(font)
        dlg.SetMinSize((min_width, min_height))


def _enlarge_checkbox(box, size):
    """Make the tick box itself bigger (Qt only; harmless on the wx backend)."""
    try:
        box.setStyleSheet(
            f"QCheckBox::indicator {{ width: {size}px; height: {size}px; }}"
        )
    except AttributeError:
        pass


def _only_ok(dlg):
    """Leave just the OK button on a dialog, dropping Cancel (Qt backend)."""
    try:
        dlg.cancelBtn.hide()
    except AttributeError:
        pass


def _build_dialog(next_number, recording, recording_label, eye_tracker=None,
                  recalibrate=True):
    """Create the participant dialog, with an optional Tobii connection check."""
    dlg = gui.Dlg(title="StatLearning", alwaysOnTop=True)
    _enlarge(dlg, FONT_SIZE, MIN_WIDTH)

    field = dlg.addField("Participant number:", initial=str(next_number))
    # Make the number box itself tall, so it is easy to hit and read
    try:
        field.setMinimumHeight(FIELD_HEIGHT)
    except AttributeError:
        field.SetMinSize((-1, FIELD_HEIGHT))

    if gui.haveQt:
        from psychopy.gui.qtgui import QtWidgets

        separator = QtWidgets.QFrame(dlg)
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        dlg.layout.addWidget(separator, dlg.irow, 0, 1, 2)
        dlg.irow += 1

    # A bool initial makes gui.Dlg build a checkbox. Its value comes back in
    # dlg.data, and the operator can tick or untick it.
    check = dlg.addField(recording_label, initial=bool(recording))
    _enlarge_checkbox(check, CHECKBOX_SIZE)

    if eye_tracker is not None:
        from .eye_tracker_check import EyeTrackerCheck

        check = dlg.addField("Eye tracker", initial=bool(eye_tracker))
        _enlarge_checkbox(check, CHECKBOX_SIZE)

        calibration = dlg.addField("Recalibrate", initial=bool(recalibrate))
        _enlarge_checkbox(calibration, CHECKBOX_SIZE)
        label = dlg.layout.itemAtPosition(dlg.irow - 1, 0).widget()
        label.setContentsMargins(36, 0, 0, 0)
        label.setEnabled(check.isChecked())
        calibration.setEnabled(check.isChecked())
        check.toggled.connect(label.setEnabled)
        check.toggled.connect(calibration.setEnabled)

        status = dlg.addText("")
        font = status.font()
        font.setPointSize(EYE_TRACKER_FONT_SIZE)
        status.setFont(font)
        status.setWordWrap(True)
        dlg.tracker_check = EyeTrackerCheck(dlg, check, status, _eye_tracker_warning)

    # Remove the message about required asterisks
    dlg.requiredMsg.setText("")

    return dlg


def _build_warning(message, title="Check participant number"):
    """Create an enlarged warning with a single OK button."""
    dlg = gui.Dlg(title=title, alwaysOnTop=True)
    _enlarge(dlg, WARNING_FONT_SIZE, MIN_WIDTH)
    # Drop the default "Fields marked with an asterisk (*) ..." note
    dlg.requiredMsg.setText("")
    _only_ok(dlg)
    dlg.addText(message)
    return dlg


def _eye_tracker_warning(message):
    """Offer a fresh check, an explicit opt-out, or cancellation of the study."""
    from psychopy.gui.qtgui import QtWidgets

    dlg = gui.Dlg(title="Check eye tracker", alwaysOnTop=True)
    _enlarge(dlg, WARNING_FONT_SIZE, MIN_WIDTH)
    dlg.requiredMsg.setText("")
    text = dlg.addText(
        f"{message}\n\n"
        "1. Check the eye tracker's power and cable connections.\n"
        "2. Check its USB or network connection to this computer.\n"
        "3. Wait a few seconds, then press Retry.\n\n"
        "Uncheck eye tracker: return to the participant dialog without the check.\n"
        "Cancel: close the study without creating a participant folder.\n\n"
        "This checks connection only; it does not record gaze data."
    )
    font = text.font()
    font.setPointSize(EYE_TRACKER_FONT_SIZE)
    text.setFont(font)
    text.setWordWrap(True)
    dlg.okBtn.setText("Retry")
    uncheck = QtWidgets.QPushButton("Uncheck eye tracker", dlg)
    dlg.buttonBox.addButton(uncheck, QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
    action = "cancel"

    def without_tracker():
        nonlocal action
        action = "uncheck"
        dlg.reject()

    uncheck.clicked.connect(without_tracker)
    dlg.show()
    return "retry" if dlg.OK else action


def get_participant(data_dir, recording=RECORDING_DEFAULT,
                    recording_label=RECORDING_LABEL, eye_tracker=None,
                    recalibrate=True):
    """Ask which participant this session belongs to.

    ``recording`` sets the checkbox under the number field; the operator can
    change it before pressing OK. ``eye_tracker=None`` hides the connection
    checkbox; a bool shows it with that starting state. When checked, finding
    a Tobii tracker is required before continuing. ``recalibrate`` sets the
    nested checkbox's starting state. It is disabled when eye tracking is off.
    No calibration or gaze recording is started here.

    Creates Data/Sxxx only after validation and returns
    ``(subject_id, subjnum, recording, tracker_checked, recalibrate)``.
    The last two values are False when eye tracking is off.
    """
    # Create the data folder if it does not exist
    data_dir = Path(data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        # Find participant folders such as S001 and S002.
        numbers = [
            int(folder.name[1:])
            for folder in data_dir.iterdir()
            if folder.is_dir()
            and folder.name.startswith("S")
            and folder.name[1:].isdigit()
        ]
    except OSError as exc:
        _build_warning(
            f"Cannot open the study data folder:\n{data_dir}\n\n"
            f"Check the folder location and write permissions.\n{exc}",
            title="Check data folder",
        ).show()
        core.quit()

    # Suggest the highest number + 1, or 1 if there are no participants
    next_number = max(numbers, default=0) + 1

    # Keep asking until a valid, unused number is entered
    while True:
        dlg = _build_dialog(next_number, recording, recording_label, eye_tracker,
                            recalibrate)
        selection = dlg.show()

        # End the script if the user clicks Cancel
        if not dlg.OK:
            core.quit()

        # Preserve the operator's choices if the participant number needs fixing.
        next_number = selection[0]
        recording = bool(selection[1])
        tracker_checked = False
        if eye_tracker is not None:
            eye_tracker = bool(selection[2])
            recalibrate = bool(selection[3])
            tracker_checked = eye_tracker and dlg.tracker_check.passed
            if eye_tracker and not tracker_checked:
                continue  # Fail closed even if the dialog was accepted another way.

        # Check that the answer is a positive whole number
        try:
            subjnum = int(selection[0])

            if subjnum < 1:
                raise ValueError

        except (ValueError, TypeError):
            message = "Please enter a positive whole number."

        else:
            # Format the number: 1 becomes S001, 12 becomes S012
            subject_id = f"S{subjnum:03d}"

            # Exclusive creation also protects against a folder appearing while
            # the dialog was open. Never reuse an existing participant's data.
            try:
                if subjnum in numbers:
                    raise FileExistsError(subject_id)
                (data_dir / subject_id).mkdir()
            except FileExistsError:
                message = f"{subject_id} already exists. Choose another number."
            except OSError as exc:
                _build_warning(
                    f"Cannot create {subject_id} in:\n{data_dir}\n\n"
                    f"Check write permissions and available disk space.\n{exc}",
                    title="Check data folder",
                ).show()
                core.quit()
            else:
                return (
                    subject_id, subjnum, recording,
                    tracker_checked, tracker_checked and recalibrate,
                )

        # Explain the problem before showing the entry dialog again
        _build_warning(message).show()


if __name__ == "__main__":
    # A throwaway folder so the demo never touches real study data.
    import tempfile

    demo_dir = Path(tempfile.gettempdir()) / "subject_dialog_demo_data"
    demo_dir.mkdir(parents=True, exist_ok=True)
    for existing_subject in (1, 2):        # pretend S001 and S002 are done
        (demo_dir / f"S{existing_subject:03d}").mkdir(exist_ok=True)

    chosen_id, chosen_number, chosen_recording, tracker_checked, recalibrate = get_participant(
        demo_dir, eye_tracker=False,
    )
    print(f"Chosen: {chosen_id} (number {chosen_number}), "
          f"recording={chosen_recording}, tracker_checked={tracker_checked}, "
          f"recalibrate={recalibrate}")
