"""No-participant fullscreen checks. Add --interactive for real finger taps.

Run from the repository root: pixi run python -m HideAndSeek.check_display
"""

import argparse
import csv
import json
import time
from unittest.mock import patch

from utils.display_settings import enable_native_pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    enable_native_pixels()
    from psychopy import core, event, visual
    from utils.display_settings import DisplaySettings
    from utils.pause_video import show_pause_video
    from HideAndSeek import HideAndSeek as study

    display = DisplaySettings.detect()
    win = visual.Window(size=display.size, screen=display.screen, fullscr=True,
                        units="height", color="black")
    try:
        scale = study.scene_scale(win.size)
        study.set_view_scale(win, (scale, scale))
        failures = []
        print("DISPLAY", json.dumps({"size": list(map(int, win.size)),
                                     "event_size": list(win.winHandle.get_size()),
                                     "scale": scale}), flush=True)

        def capture():
            win.getMovieFrame(buffer="back")
            return win.movieFrames.pop().convert("RGB")

        def white(pixel):
            return min(pixel) > 240

        scene = visual.Rect(win, width=study.SCENE_ASPECT, height=1,
                            fillColor="white", lineColor="white")
        scene.draw()
        frame = capture()
        width, height = frame.size
        left = (width - height * scale * study.SCENE_ASPECT) / 2
        top = (height - height * scale) / 2
        # Inspect the GPU framebuffer, not just the geometry calculation.
        for x in (int(left + 3), width // 2, int(width - left - 4)):
            assert white(frame.getpixel((x, int(top + 3))))
            assert white(frame.getpixel((x, int(height - top - 4))))
        if top >= 4:
            if not (max(frame.getpixel((width // 2, int(top - 3)))) < 10 and
                    max(frame.getpixel((width // 2, int(height - top + 2)))) < 10):
                failures.append("Initial frame ignores newly assigned viewScale (no black bars).")
        if left >= 4:
            assert max(frame.getpixel((int(left - 3), height // 2))) < 10
        if not failures:
            print("PASS: initial scene frame has correct bounds and black bars", flush=True)
        win.flip()
        scene.draw()
        frame = capture()
        if top >= 4:
            assert max(frame.getpixel((width // 2, int(top - 3)))) < 10
            assert max(frame.getpixel((width // 2, int(top + 3)))) > 240
        win.flip()
        core.wait(.3)
        win.flip()
        print("PASS: actual GPU scene bounds and black bars AFTER first flip", flush=True)

        square = visual.Rect(win, units="pix", width=100, height=100,
                             fillColor="white", lineColor="white")
        with study.unscaled_view(win):
            square.draw()
            frame = capture()
            if not white(frame.getpixel((width // 2 + 48, height // 2))):
                failures.append("First unscaled overlay frame is still scene-scaled (100px square too small).")
            assert max(frame.getpixel((width // 2 + 53, height // 2))) < 10
            win.flip()
        assert tuple(win.viewScale) == (scale, scale)
        # The first scene frame after restoring the scale must also be fitted.
        scene.draw()
        frame = capture()
        if top >= 4 and max(frame.getpixel((width // 2, int(top - 3)))) >= 10:
            failures.append("First scene frame after unscaled_view remains unscaled.")
        if not failures:
            print("PASS: first overlay and first restored scene frames use the correct scale", flush=True)
        win.flip()
        print("PASS: viewScale attribute restored; framebuffer transitions checked separately", flush=True)

        sky = visual.ImageStim(win, image=str(study.scene_files["sky"]), size=(study.SCENE_ASPECT, 1))
        foreground = visual.ImageStim(win, image=str(study.scene_files["foreground"]), size=(study.SCENE_ASPECT, 1))
        portraits = {colour: visual.ImageStim(win, image=str(study.puppet_files[colour]["portrait"]),
                                             pos=pos, size=(.16428, .2))
                     for colour, pos in study.portrait_positions.items()}
        cue = visual.ImageStim(win, image=str(study.puppet_files["blue"]["cue"]),
                               pos=(0, -.1), size=(.15, .2))
        for image in [cue, *portraits.values()]:
            x, y = image.pos
            ex, ey = win.winHandle.get_size()
            pos = study.scene_position(ex / 2 + x * ey * scale,
                                       ey / 2 + y * ey * scale, (ex, ey), scale)
            assert image.contains(pos)
            assert not image.contains((pos[0] + .3, pos[1]))
        print("PASS: real ImageStim hit-testing at cue and all portraits", flush=True)

        # Exercise the study's actual pause drawing without waiting for an operator.
        with patch.object(study, "visual", visual, create=True), \
                patch.object(study, "event", event, create=True), \
                patch.object(study, "save_event"), \
                patch.object(event, "waitKeys", return_value=["space"]):
            assert not study.pause_study(win)
        assert tuple(win.viewScale) == (scale, scale)
        print("PASS: actual pause/resume drawing and scale restoration", flush=True)

        start = time.monotonic()
        with study.unscaled_view(win), \
                patch.object(event, "getKeys", side_effect=lambda **kw: ["x"] if time.monotonic() - start > 2 else []):
            show_pause_video(win, lambda action: None)
        assert tuple(win.viewScale) == (scale, scale)
        print("PASS: actual break-video playback/unload and scale restoration", flush=True)

        with (study.stimuli_dir / "locations.csv").open(newline="") as source:
            rows = list(csv.DictReader(source))
        extremes = [min(rows, key=lambda r: float(r["x"])), max(rows, key=lambda r: float(r["x"]))]
        targets = [("central puppet", (0, -.1)), *study.portrait_positions.items(),
                   *[(f"extreme {i + 1}", (float(row["x"]), float(row["y"]))) for i, row in enumerate(extremes)]]

        def draw():
            sky.draw()
            foreground.draw()
            cue.draw()
            for portrait in portraits.values():
                portrait.draw()

        draw()
        win.flip()
        core.wait(.5)
        print("PASS: native fullscreen study assets render", flush=True)
        for failure in failures:
            print("FAIL:", failure, flush=True)
        if not args.interactive:
            print("AUTOMATED CHECKS COMPLETE. Physical touch alignment is NOT tested.\n"
                  "Run again with --interactive and tap each crosshair with a finger.", flush=True)
            if failures:
                raise SystemExit(1)
            return

        # Keep raw pyglet events, exactly as the study does. No participant files.
        pending = []

        def press(x, y, button, modifiers):
            pending.append((x, y, button))

        win.winHandle.push_handlers(on_mouse_press=press)
        cross = visual.TextStim(win, text="+", height=.06, color="red")
        label = visual.TextStim(win, pos=(0, -.25), height=.023, color="black", wrapWidth=1.5)
        try:
            for name, position in targets:
                pending.clear()
                cross.pos = position
                label.text = f"Tap the red + with your FINGER: {name}\nEsc = exit"
                deadline = time.monotonic() + 60
                while True:
                    draw()
                    cross.draw()
                    label.draw()
                    win.flip()
                    if "escape" in event.getKeys() or time.monotonic() > deadline:
                        print("INCOMPLETE: manual check cancelled or timed out", flush=True)
                        raise SystemExit(1)
                    accepted = False
                    for x, y, button in pending:
                        pos = study.scene_position(x, y, win.winHandle.get_size(), scale)
                        error = ((pos[0] - position[0]) ** 2 + (pos[1] - position[1]) ** 2) ** .5
                        print(f"TOUCH {name}: scene={pos}, button={button}, error={error:.4f}", flush=True)
                        accepted |= error < .03
                    pending.clear()
                    if accepted:
                        break
                core.wait(.3)
            print("PASS: all six manual targets tapped within 0.03 scene units.\n"
                  "Mouse and finger events look alike here; operator must confirm finger use.", flush=True)
            if failures:
                raise SystemExit(1)
        finally:
            win.winHandle.remove_handlers(on_mouse_press=press)
    finally:
        win.close()


if __name__ == "__main__":
    main()
