# Stimuli

Everything the study shows. The study scales each picture to the full screen
height (so 720x576 pictures become 1350x1080 on a 1920x1080 screen).

## objects/

The 18 objects, plus the two extra objects that make up the second study
version. All are 720x576 PNGs on the orange background used in the old Blob
study, and they are the files that participants saw (checked byte for byte
against the originals).

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
30 fps, and its shapes are drawn on the study's exact orange (248,169,122) with
the original white background keyed out. Nothing flashes at the picture
boundary. The sounds are the attention getter sounds from the old Blob study,
encoded as AAC starting at the beginning of each movie, with silence after the
sound finishes to keep the audio track at 2 s. The video streams were copied
without re-encoding. The study does not play separate WAV files.

`old/` preserves the three original silent MP4s and their matching WAVs unchanged.
These archived files are not used by the study.

`attention_candidates/` next to this folder is the review area where the clips
were chosen from. The study does not use it.

## music/

`background.wav` is the music from the old session video, with the attention
getter beeps cut out (~115 s). It plays on a loop for the whole session and
stops at the end. Any single audio file named `background.` plus an extension
works instead.
