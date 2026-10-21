"""Display checks without opening PsychoPy or creating participant data.

Run from the repository root: python -m unittest HideAndSeek.test_display
"""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from HideAndSeek import HideAndSeek as study


class DisplayTests(unittest.TestCase):
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
        win = SimpleNamespace(viewScale=(0.9, 0.9))
        with study.unscaled_view(win):
            self.assertEqual(win.viewScale, (1, 1))
        self.assertEqual(win.viewScale, (0.9, 0.9))
        with self.assertRaises(ValueError):
            with study.unscaled_view(win):
                raise ValueError("test cleanup")
        self.assertEqual(win.viewScale, (0.9, 0.9))

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
