# Stimuli

Everything the study shows. Pictures are displayed at a fixed 1350x1080 pixels.

## objects/

The 18 objects, plus the two extra objects that make up the second study
version. All are 720x576 PNGs on an orange background.

| Category | Stimuli |
|---|---|
| 1, familiar to infants and adults | `Bottle1`, `Bottle2` (bottles version) or `Pacifier1`, `Pacifier2` (pacifiers version), `Cup1`, `Cup2`, `Keyring`, `Spoon` |
| 2, familiar to adults only | `Drill`, `Horn`, `Microscope`, `Trowel1`, `Trowel2`, `Trumpet` |
| 3, unfamiliar to everyone | `Object1`, `Object3`, `Object4`, `Object6`, `Object7`, `Object8` |

## attention/

The three attention getters, played for 2 s before every stimulus, each with
its sound embedded in the MP4:

- `spinning_wedge.mp4` — a disc with a wedge rotating around it
- `shattering_hexagon.mp4` — a hexagon breaking into shards and reforming
- `morphing_quarters.mp4` — four quarter circles converging and dividing

Each clip is exactly 2.000 s, 720x576 (4:3, so it is scaled like the pictures),
30 fps, with shapes on the study's orange background (248,169,122).
Audio is embedded as AAC from the beginning of each movie, with silence after
the sound finishes to keep the audio track at 2 s. The study does not play
separate WAV files for these clips.

## music/

`background.wav` contains about 115 s of music without attention-getter beeps.
It loops during the trials and stops at session end. Any single audio file
named `background.` plus an extension works instead.
