# Display aspect-ratio fix

## Problem

The original study was designed for 1920 × 1080 (16:9). The recreated study
uses PsychoPy height units, so stimulus sizes and positions scale with the
screen height.

On a 1920 × 1200 (16:10) fullscreen display, the original scene would therefore
be about 2133 pixels wide. Its left and right edges would be cropped, and the
outermost reveal positions would have their centres outside the visible screen.

## Mitigation

- Keep fullscreen at the monitor's native resolution.
- Use PsychoPy's `Window.viewScale` to fit the original 16:9 scene uniformly,
  without stretching or changing the stored reveal positions.
- On 1920 × 1200, use a scale of 0.9: the scene occupies 1920 × 1080, centred
  with 60-pixel black bars above and below. At 1920 × 1080, the scale is 1.
- Undo that scale when converting touch coordinates, before hit-testing and
  saving, so coordinates retain their original meaning on either display.
- Record touches outside the scene as misses; they cannot submit predictions.
- Temporarily disable scene scaling for pixel-sized pause messages and the
  break video, restoring it afterward.
- Save the scene scale and dimensions alongside the actual window dimensions
  in session metadata.

The implementation is local to `HideAndSeek.py`; shared display utilities and
other studies were not changed.

## Verification and limitations

Five automated tests pass, covering coordinate conversion, scene fitting,
black-bar touches, and scale restoration. Run them from the repository root:

```text
pixi run python -m unittest HideAndSeek.test_display -v
```

Before collecting data, visually check the extreme reveal positions and touch
alignment on the participant display, plus pause/resume and the break video.
This fix removes the additional cropping caused by the taller display; it does
not correct any clipping already present in the original 16:9 layout. Matching
pixel geometry also does not guarantee matching physical stimulus size or
visual angle across different monitors and viewing distances.
