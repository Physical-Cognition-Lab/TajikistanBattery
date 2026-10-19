# Video recorder: keep the top of each study file light

Applies to every study that records webcam video with
`utils/video_recording/webcam_recorder.py`:

- `InformationGain/InformationGain.py`
- `HideAndSeek/HideAndSeek.py`
- `WhatBabiesKnow/WhatBabiesKnow.py`
- `Features2Functions/Features2Functions.py`

---

## The problem

Symptom, usually on the first session after a reboot:

```
WARNING: no video this session: Webcam recorder startup timed out
```

The study runs normally, but no video file is produced.

## Why it happens

The recorder runs in a **separate process**. On Windows, `multiprocessing` uses
the **spawn** start method: a new process starts empty and is told to **run the
study file again**, under the name `__mp_main__`. Running a `.py` file executes
its `import` lines.

So the worker does this before it can touch the camera:

1. re-runs `InformationGain.py` (or whichever study),
2. which executes `import psychopy`, `import pandas`, `from utils... import ...`,
3. and every import is cold, because the new process has its own empty cache.

The worker never uses PsychoPy. It only needs OpenCV and the `_record`
function, but it pays for the study's imports anyway.

`WebcamRecorder.start()` waits **10 seconds** for the worker to report ready.
That budget has to cover:

```
spawn  ->  re-run the study file  ->  open the camera  ->  create the file  ->  ready
```

Measurements on this project:

| what | time |
|---|---|
| re-run the study file, disk cache **warm** | 3.4 – 3.6 s |
| re-run the study file, disk cache **cold** (first run after reboot) | 9.4 s |
| re-run after moving the imports inside the guard | **0.02 s** |
| `start()` timeout | 10 s |

Warm, that leaves ~6 s for the camera. Cold, it leaves under a second, and the
worker misses the deadline.

The main guard (`if __name__ == "__main__":`) already stops the worker from
launching a second copy of the experiment. It does **not** stop the imports
above it — the guard only skips its own block.

## The fix

Keep the **top of the study file light**. Move every non-stdlib import inside the
`if __name__ == "__main__":` block, so the worker's re-run only executes stdlib
imports and a few function definitions.

### Before

```python
from contextlib import nullcontext
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd
import psychopy
from psychopy import core, event, sound, visual
from psychopy.hardware.speaker import SpeakerDevice

from utils.subject_selection import get_participant


def save_event(...): ...
def get_bar(...): ...
...

if __name__ == "__main__":
    ...
```

### After

```python
import json
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

# Nothing heavy up here: the video recorder's worker process re-runs this file
# before it can start, and it has no use for PsychoPy.


def save_event(...): ...
def get_bar(...): ...
...

if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    import psychopy
    from psychopy import core, event, sound, visual
    from psychopy.hardware.speaker import SpeakerDevice

    from utils.subject_selection import get_participant
    ...
```

The worker's re-run now costs about 0.02 s instead of several seconds, so the
10 s timeout stops being a question.

## Why it works

An `if` block at module level does not create a scope: names imported inside it
are still **module globals**. The functions defined above (`save_event`,
`get_bar`, `show_stimulus`, …) look them up at call time and find `core`,
`event`, `visual` exactly as before. No `global` declarations are needed.

The guard itself is unchanged — it is what stops the worker from starting a
second study.

## Rules

At the **top** of the file, only stdlib:

- `contextlib`, `csv`, `datetime`, `json`, `math`, `pathlib`, `random`, `sys`, `time`

Inside `if __name__ == "__main__":`:

- everything else: `numpy`, `pandas`, `psychopy`, `psychopy.*`, and any local
  module that itself imports PsychoPy (e.g. `utils.subject_selection`).
- `WebcamRecorder` is already imported lazily inside `if recording:`, which is
  fine — keep it there.

Also: nothing at module level may *use* a heavy import. A constant computed with
`numpy`, for example, has to move inside the guard too.

## Per-study checklist

| file | main guard | heavy imports at top |
|---|---|---|
| `InformationGain/InformationGain.py` | yes | no — inside guard |
| `HideAndSeek/HideAndSeek.py` | yes | no — inside guard |
| `WhatBabiesKnow/WhatBabiesKnow.py` | yes | no — inside guard |
| `Features2Functions/Features2Functions.py` | yes | no — inside guard |

All four pixi tasks already launch with `-m`, which is what lets `utils` be
imported without touching `sys.path`. Keep it that way:

```toml
hide-and-seek = "python -m HideAndSeek.HideAndSeek"
what-babies-know = "python -m WhatBabiesKnow.WhatBabiesKnow"
information-gain = "python -m InformationGain.InformationGain"
features-to-functions = "python -m Features2Functions.Features2Functions"
```

## How to check one study

This runs a study file exactly the way the recorder's worker does — it executes
the top level and skips the guard:

```powershell
pixi run python -c "import runpy, time; t=time.perf_counter(); runpy.run_path(r'InformationGain\InformationGain.py', run_name='__mp_main__'); print(round(time.perf_counter()-t,1), 's')"
```

Expected after the fix: about 0.02 s, and **no window and no dialog** appear.
Before the fix it prints something like `3.5 s`.

Run it twice; the first run of the day is slower than the second.

## Why not just raise the timeout

`start(timeout=30)` widens the window, but the worker still spends ~3.5 s
importing PsychoPy it will never use. That is dead time on every session, and a
cold machine could still exceed any fixed number. It is a workaround, not a fix.

If a study ever does need a longer timeout anyway, the `with` form has to become
an explicit start/stop:

```python
recorder = WebcamRecorder.for_subject(subject_dir)
recorder.start(timeout=30)
try:
    ...
finally:
    recorder.stop()
```

## Why the recorder re-runs the study at all

Windows has no `fork()`, so a new process cannot inherit the parent's memory.
`multiprocessing` therefore reconstructs it by re-running the main module in the
child, under the name `__mp_main__`. This is documented Python behaviour
("safe importing of the main module"), and it is exactly why every study needs
the `if __name__ == "__main__":` guard. There is no switch to turn it off; the
only lever is what the file does at the top.
