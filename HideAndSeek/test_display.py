"""Display checks without opening PsychoPy or creating participant data.

Run from the repository root: python -m unittest HideAndSeek.test_display
"""

from types import SimpleNamespace
import csv
import unittest
from unittest.mock import Mock, patch

from HideAndSeek import HideAndSeek as study


class DisplayTests(unittest.TestCase):
    def run_contacts(self, frames, keys=None, pause_result=False, fail_draw=False):
        """Drive the real trial handler, including contacts between flips."""
        win = Mock(viewScale=(0.9, 0.9))
        win.winHandle.get_size.return_value = (1920, 1200)
        mouse = Mock()
        mouse.getPressed.return_value = (False, False, False)
        events = Mock()
        events.Mouse.return_value = mouse
        events.getKeys.side_effect = keys if keys is not None else lambda **kw: []
        frames = iter(frames)

        def flip():
            # Exhaustion fails immediately rather than leaving a test looping.
            contacts = next(frames)
            handlers = win.winHandle.push_handlers.call_args.kwargs
            for kind, x, y, button in contacts:
                handlers[f"on_mouse_{kind}"](x, y, button, None)

        win.flip.side_effect = flip
        cue = Mock()
        cue.contains.side_effect = lambda p: abs(p[0]) < .075 and -.2 < p[1] < 0
        portrait = Mock()
        portrait.contains.side_effect = lambda p: abs(p[0] - .16428) < .08 and -.47 < p[1] < -.27
        stimuli = {
            "hidden_patch": Mock(), "portraits": {"green": portrait},
            "instructions": {"hint": Mock(), "footer": Mock()},
            "puppets": {colour: {"cue": cue} for colour in ("blue", "green")},
            "sounds": {"hiding": Mock()},
        }
        with patch.object(study, "event", events, create=True), \
                patch.object(study, "study_clock", Mock(), create=True), \
                patch.object(study, "stop_requested", False, create=True), \
                patch.object(study, "pause_study", return_value=pause_result), \
                patch.object(study, "draw_scene") as draw:
            if fail_draw:
                draw.side_effect = ValueError("draw failed")
            try:
                return study.select_and_predict(win, stimuli, "blue", False)
            finally:
                win.winHandle.remove_handlers.assert_called_once()

    @staticmethod
    def tap(x, y, button=1):
        return [("press", x, y, button), ("release", x, y, button)]

    def test_quick_taps_between_frames_are_not_lost(self):
        _, prediction, clicks = self.run_contacts([
            self.tap(960, 492) + self.tap(1500, 816), []])
        self.assertEqual([c["action"] for c in clicks], ["hide", "predict"])
        self.assertEqual(prediction, (.5, .2))

    def test_long_press_right_button_is_accepted(self):
        _, _, clicks = self.run_contacts([
            self.tap(960, 492, 4), self.tap(960, 816, 4)])
        self.assertEqual([c["action"] for c in clicks], ["hide", "predict"])

    def test_overlapping_buttons_do_not_create_extra_actions(self):
        _, _, clicks = self.run_contacts([
            [("press", 960, 492, 1), ("press", 1500, 816, 4),
             ("release", 960, 492, 1), ("release", 1500, 816, 4)],
            self.tap(960, 816)])
        self.assertEqual([c["action"] for c in clicks], ["hide", "predict"])

    def test_lost_release_does_not_block_next_contact(self):
        _, _, clicks = self.run_contacts([
            [("press", 960, 492, 1)], self.tap(960, 816)])
        self.assertEqual([c["action"] for c in clicks], ["hide", "predict"])

    def test_both_bars_and_lower_scene_cannot_submit_predictions(self):
        _, _, clicks = self.run_contacts([
            self.tap(960, 1190), self.tap(960, 10), self.tap(960, 492),
            self.tap(960, 1190), self.tap(960, 10), self.tap(960, 600),
            self.tap(960, 816)])
        self.assertEqual([c["action"] for c in clicks],
                         ["miss", "miss", "hide", "miss", "miss", "miss", "predict"])
        self.assertEqual([c["phase"] for c in clicks],
                         ["choice", "choice", "choice", "predict", "predict", "predict", "predict"])

    def test_portrait_switch_requires_hiding_new_puppet(self):
        puppet, _, clicks = self.run_contacts([
            self.tap(960, 492), self.tap(1137.4224, 200.4),
            self.tap(960, 816), self.tap(960, 492), self.tap(960, 816)])
        self.assertEqual(puppet, "green")
        self.assertEqual([c["action"] for c in clicks],
                         ["hide", "switch", "miss", "hide", "predict"])

    def test_pause_discards_queued_touch(self):
        _, _, clicks = self.run_contacts([
            self.tap(960, 492), self.tap(960, 492), self.tap(960, 816)],
            keys=[["escape"], [], []])
        self.assertEqual([c["action"] for c in clicks], ["hide", "predict"])

    def test_stop_and_exception_remove_touch_handlers(self):
        self.assertEqual(self.run_contacts([[]], keys=[["escape"]], pause_result=True),
                         (None, None, []))
        with self.assertRaisesRegex(ValueError, "draw failed"):
            self.run_contacts([], fail_draw=True)

    def test_every_stored_reveal_centre_is_visible(self):
        with (study.stimuli_dir / "locations.csv").open(newline="") as source:
            locations = list(csv.DictReader(source))
        self.assertEqual(len(locations), 105)
        for size in [(1920, 1200), (1920, 1080), (1280, 1024), (1080, 1920), (2560, 1080)]:
            width, height = size
            scale = study.scene_scale(size)
            for row in locations:
                x, y = float(row["x"]), float(row["y"])
                with self.subTest(size=size, pattern=row["pattern"], position=row["position"]):
                    px, py = width / 2 + x * height * scale, height / 2 + y * height * scale
                    self.assertTrue(0 <= px <= width and 0 <= py <= height)
                    actual = study.scene_position(px, py, size, scale)
                    self.assertAlmostEqual(actual[0], x)
                    self.assertAlmostEqual(actual[1], y)

    def test_original_display_is_unchanged(self):
        self.assertEqual(study.scene_scale((1920, 1080)), 1)
        self.assertEqual(study.scene_position(960, 540, (1920, 1080), 1), (0, 0))

    def test_taller_display_has_60_pixel_bars(self):
        scale = study.scene_scale((1920, 1200))
        self.assertAlmostEqual(scale, 0.9)
        scene_height = 1200 * scale
        self.assertAlmostEqual(scene_height * study.SCENE_ASPECT, 1920)
        self.assertAlmostEqual((1200 - scene_height) / 2, 60)
        self.assertAlmostEqual(study.scene_position(960, 60, (1920, 1200), scale)[1], -0.5)
        self.assertAlmostEqual(study.scene_position(960, 1140, (1920, 1200), scale)[1], 0.5)

    def test_scene_coordinates_round_trip_on_different_displays(self):
        # Include the central puppet, portraits, and extreme reveal positions.
        points = [(0, -0.1), (-0.16428, -0.37), (0.16428, -0.37),
                  (-0.833131, 0.19988), (0.833131, 0.19988)]
        for size in [(1920, 1080), (1920, 1200), (1280, 1024), (2560, 1080)]:
            width, height = size
            scale = study.scene_scale(size)
            self.assertLessEqual(height * scale, height + 1e-9)
            self.assertLessEqual(height * scale * study.SCENE_ASPECT, width + 1e-9)
            for x, y in points:
                with self.subTest(size=size, point=(x, y)):
                    pixel_x = width / 2 + x * height * scale
                    pixel_y = height / 2 + y * height * scale
                    actual = study.scene_position(pixel_x, pixel_y, size, scale)
                    self.assertAlmostEqual(actual[0], x)
                    self.assertAlmostEqual(actual[1], y)

    def test_unscaled_view_restores_scale_even_on_error(self):
        applied = []
        win = SimpleNamespace(viewScale=(0.9, 0.9))
        win.setDefaultView = Mock(side_effect=lambda **kw: applied.append(win.viewScale))
        with study.unscaled_view(win):
            self.assertEqual(win.viewScale, (1, 1))
            self.assertEqual(applied, [(1, 1)])
        self.assertEqual(win.viewScale, (0.9, 0.9))
        self.assertEqual(applied, [(1, 1), (0.9, 0.9)])
        with self.assertRaises(ValueError):
            with study.unscaled_view(win):
                raise ValueError("test cleanup")
        self.assertEqual(win.viewScale, (0.9, 0.9))
        self.assertEqual(applied, [(1, 1), (0.9, 0.9)] * 2)
        self.assertEqual(win.setDefaultView.call_count, 4)
        win.setDefaultView.assert_called_with(clearDepth=False)

    def test_scene_scale_is_applied_immediately_without_flipping(self):
        win = Mock(viewScale=(1, 1))
        applied = []
        win.setDefaultView.side_effect = lambda **kw: applied.append(win.viewScale)
        study.set_view_scale(win, (0.9, 0.9))
        self.assertEqual(applied, [(0.9, 0.9)])
        win.setDefaultView.assert_called_once_with(clearDepth=False)
        win.flip.assert_not_called()

    def test_bar_touch_is_a_miss_not_a_prediction(self):
        # Simulate hiding, tapping the upper black bar, then predicting in-scene.
        win = Mock(viewScale=(0.9, 0.9))
        win.winHandle.get_size.return_value = (1920, 1200)
        taps = iter([(960, 492), (960, 1190), (960, 816)])

        def flip():
            x, y = next(taps)
            handlers = win.winHandle.push_handlers.call_args.kwargs
            handlers["on_mouse_press"](x, y, 1, None)
            handlers["on_mouse_release"](x, y, 1, None)

        win.flip.side_effect = flip
        mouse = Mock()
        mouse.getPressed.return_value = (False, False, False)
        events = Mock()
        events.Mouse.return_value = mouse
        events.getKeys.return_value = []
        cue = Mock()
        cue.contains.side_effect = lambda pos: abs(pos[0]) < 0.075 and -0.2 < pos[1] < 0
        stimuli = {
            "hidden_patch": Mock(), "portraits": {},
            "instructions": {"hint": Mock(), "footer": Mock()},
            "puppets": {"blue": {"cue": cue}},
            "sounds": {"hiding": Mock()},
        }
        with patch.object(study, "event", events, create=True), \
                patch.object(study, "study_clock", Mock(), create=True), \
                patch.object(study, "draw_scene"):
            puppet, prediction, clicks = study.select_and_predict(
                win, stimuli, "blue", first_trial=False)

        self.assertEqual(puppet, "blue")
        self.assertAlmostEqual(prediction[0], 0)
        self.assertAlmostEqual(prediction[1], 0.2)
        self.assertEqual([click["action"] for click in clicks], ["hide", "miss", "predict"])
        self.assertEqual(clicks[1]["phase"], "predict")
        self.assertGreater(clicks[1]["y"], 0.5)
        win.winHandle.remove_handlers.assert_called_once()


if __name__ == "__main__":
    unittest.main()
