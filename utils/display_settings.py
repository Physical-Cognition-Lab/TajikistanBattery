"""Select a fullscreen monitor and report its pixel resolution."""

from dataclasses import dataclass
from math import gcd
import sys


def enable_native_pixels():
    """Call before importing PsychoPy/Qt so Windows scaling cannot shrink pixels."""
    if sys.platform == "win32":
        import ctypes

        # Per-monitor awareness; E_ACCESSDENIED means awareness was already set.
        result = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if result not in (0, -2147024891):
            raise OSError(f"Cannot enable display DPI awareness: {result}")


@dataclass
class DisplaySettings:
    screens: list
    screen: int = 0

    @classmethod
    def detect(cls, preferred=0):
        import pyglet

        screens = pyglet.canvas.get_display().get_screens()
        sizes = [(int(screen.width), int(screen.height)) for screen in screens]
        if not sizes:
            raise RuntimeError("No participant display was detected.")
        return cls(sizes, preferred if preferred < len(sizes) else 0)

    @property
    def size(self):
        return self.screens[self.screen]

    def description(self):
        width, height = self.size
        divisor = gcd(width, height)
        ratio = "16:10" if width * 10 == height * 16 else f"{width // divisor}:{height // divisor}"
        text = (f"Detected: {width} × {height} ({ratio})\n"
                "Fullscreen at this resolution.\n"
                "Stimulus sizes and positions are defined in each study's code. No automatic layout fitting.")
        warning = self.size not in ((1920, 1080), (1920, 1200))
        if warning:
            text += "\nCheck display: use the planned 1920 × 1080 or 1920 × 1200 setup. Fixed stimuli may not fit other screens."
        return text, warning

    def metadata(self, win):
        return {
            "window_size": [int(value) for value in win.size],
            "fullscreen": bool(win.fullscr),
            "screen_index": self.screen,
            "requested_display_size": list(self.size),
        }


def add_display_section(dlg, settings):
    """Qt-only display controls, separate from PsychoPy's participant data fields."""
    from psychopy.gui.qtgui import QtWidgets

    panel = QtWidgets.QFrame(dlg)
    panel.setObjectName("participantDisplay")
    panel.setStyleSheet(
        "QFrame#participantDisplay { border: 1px solid #aab4c0; border-radius: 8px; }"
        "QPushButton { text-align: left; font-size: 15pt; font-weight: bold; "
        "padding: 10px; border: none; border-radius: 5px; }"
        "QPushButton:hover { background: palette(mid); }"
        "QLabel, QComboBox { font-size: 14pt; font-weight: normal; }"
        "QComboBox { padding: 6px; min-height: 28px; }"
    )
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(10)
    heading = QtWidgets.QPushButton(panel)
    heading.setCheckable(True)
    heading.setAutoDefault(False)
    heading.setAccessibleName("Participant display settings")
    heading.setToolTip("Expand to choose the participant monitor and review display information.")
    layout.addWidget(heading)
    details = QtWidgets.QWidget(panel)
    details_layout = QtWidgets.QVBoxLayout(details)
    details_layout.setContentsMargins(8, 0, 8, 10)
    details_layout.setSpacing(10)
    layout.addWidget(details)
    details.hide()
    picker = QtWidgets.QComboBox(details)
    for index, (width, height) in enumerate(settings.screens):
        picker.addItem(f"Display {index + 1} — {width} × {height}")
    picker.setCurrentIndex(settings.screen)
    details_layout.addWidget(picker)
    status = QtWidgets.QLabel(details)
    status.setWordWrap(True)
    details_layout.addWidget(status)
    note = QtWidgets.QLabel(
        "Select the participant monitor, not the operator monitor. Check that Windows "
        "uses its recommended/native resolution. Videos and pictures keep their own aspect ratios.", details,
    )
    note.setWordWrap(True)
    details_layout.addWidget(note)

    def update_heading():
        width, height = settings.size
        arrow = "▾" if heading.isChecked() else "▸"
        warning = " · Check display" if settings.description()[1] else ""
        heading.setText(f"{arrow}  Participant display · {width} × {height}{warning}")

    def refresh(index):
        settings.screen = index
        update_heading()
        text, warning = settings.description()
        status.setText(text)
        status.setStyleSheet("color: #704400; background: #fff0cc; padding: 10px; border-radius: 5px;"
                            if warning else "color: #183e36; background: #e9f3ef; padding: 10px; border-radius: 5px;")

    picker.currentIndexChanged.connect(refresh)

    def toggle_details(expanded):
        details.setVisible(expanded)
        update_heading()
        dlg.adjustSize()

    heading.toggled.connect(toggle_details)
    refresh(settings.screen)
    dlg.layout.addWidget(panel, dlg.irow, 0, 1, 2)
    dlg.irow += 1
