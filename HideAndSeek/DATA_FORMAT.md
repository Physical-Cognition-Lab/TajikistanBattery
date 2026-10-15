# Hide and Seek — data format

One JSON file per participant:

```
HideAndSeek/Data/S001/S001.json
```

The file is **rewritten in full after every completed trial**, and once more
when the study ends or is stopped. A crash therefore costs at most the trial in
progress, never the session. It is written with `json.dump(..., indent=2)`,
encoded UTF-8, with `allow_nan=False` so an invalid value fails loudly instead
of silently producing a file other parsers reject.

---

## Top level

The file has exactly three keys:

```json
{
  "metadata": { "...": "..." },
  "columns": ["trial", "phase", "action", "..."],
  "rows": [ { "...": "..." } ]
}
```

| Key | Contents |
|---|---|
| `metadata` | Everything about the session that is not a row. Free-form: add fields here without touching anything else. |
| `columns` | The exact key order of every row. Use it to build the table so column order is stable. |
| `rows` | One dict per action or event. All rows share the same keys; unused ones are `null`. |

### metadata

| Field | Meaning |
|---|---|
| `subject` | Participant id, e.g. `S001`. Also the folder and file name. |
| `study` | `"HideAndSeek"` |
| `psychopy` | PsychoPy version the session ran under, e.g. `"2025.1.1"` |
| `window_size` | `[width, height]` actually used, which can differ from the requested size |
| `started` | Local date and time the session began, ISO format, e.g. `"2026-10-14T15:02:11"` |
| `ended` | Local date and time the session finished, or `null` while running |
| `completed` | `false` until the session ends. `true` if the study finished on its own — a puppet had used all 35 of its locations, or the 83-trial cap was reached; `false` if it was stopped with Esc. |

A file with `ended: null` is one that never finished — the study was
interrupted, crashed, or is still running. That is the quickest way to spot an
incomplete session.

---

## The rows

**One row per touch, and one row per session marker.** A trial is not a row; it
is a group of rows sharing a `trial` number. This is the only shape that
survives a child switching puppet five times, or tapping six times and hitting
nothing.

Because only one contact can be accepted before the finger is lifted, there is
at most one row per physical touch.

| Column | Meaning |
|---|---|
| `trial` | Trial number, 1, 2, 3… `null` on session-level rows |
| `phase` | `event`, `choice`, or `predict` |
| `action` | What happened — see below |
| `puppet` | The puppet involved in this action |
| `x`, `y` | Where the touch landed, in window height units (centre is 0,0; up is positive) |
| `time_study` | Seconds since the session clock started. Present on every row. |
| `time_trial` | Seconds since this trial began. `null` on session-level rows. |
| `target_x`, `target_y`, `target_angle` | Where the puppet **actually appeared** (the true reveal position, from `locations.csv`) |
| `prediction_x`, `prediction_y` | Where the child **predicted** it would appear |

**Invariant:** `time_trial` is `null` exactly when `trial` is `null`. So
`time_trial` is present for every trial row, and session-level rows are the only
ones without it.

**Backfill:** the reveal position and the prediction belong to the whole trial,
but are only known once the trial has finished. They are copied into *every*
row of that trial when the file is written. So any row you pick up carries its
trial context, and you never need to join rows together to score a trial.

### Actions and events

| `phase` | `action` | Meaning |
|---|---|---|
| `event` | `study_start` | Session began |
| `event` | `trial_start` | Trial began. Its `time_study` **is** the trial origin; `time_trial` is `0.0` |
| `event` | `trial_end` | Trial finished (after the reveal). Its `time_trial` **is** the trial duration |
| `event` | `pause` | Esc was pressed. `trial` is `null` here — the pause is not tied to a trial |
| `event` | `study_end` | The study reached its end: a puppet had used all 35 of its locations, or the 83-trial cap was reached |
| `event` | `study_stopped` | Esc was pressed twice and the study was stopped early |
| `choice` | `switch` | A portrait was tapped; the puppet in the middle changed |
| `choice` | `hide` | The central puppet was tapped and it hid |
| `choice` | `miss` | A touch that hit neither a portrait nor the puppet |
| `predict` | `predict` | A touch above the middle, made after hiding — the child's prediction |
| `predict` | `miss` | A touch at or below the middle after hiding, which is not a prediction |

Three details worth knowing:

- A `switch` **after** hiding still counts as `phase: "choice"` and un-hides the
  puppet. So a `switch` row can appear after a `hide` row.
- When a puppet is hidden, only touches **above the middle** (`y > 0`) count as a
  prediction. Anything at or below the middle is recorded as a `predict` / `miss`
  so the attempt is not lost silently.
- The study ends when **one** puppet has used all 35 of its locations, or after
  **83** trials, whichever comes first. Sessions therefore vary in length — as
  few as 35 trials for a child who never switches — and the three puppets
  usually finish with different counts. Do not assume a fixed number of trials
  per session.

---

## A worked example

Trial 3, where the child switched five times before settling, then hid and
predicted. Reveal position was `(0.310, -0.120)` at `15°`; the prediction was
`(0.185, 0.240)`, copied onto every row of the trial.

| # | trial | phase | action | puppet | x | y | time_study | time_trial |
|---|---|---|---|---|---|---|---|---|
| 1 | 3 | event | trial_start | – | – | – | 41.20 | 0.00 |
| 2 | 3 | choice | switch | blue | −0.160 | −0.366 | 42.05 | 0.85 |
| 3 | 3 | choice | switch | red | 0.004 | −0.372 | 43.62 | 2.42 |
| 4 | 3 | choice | switch | green | 0.161 | −0.368 | 44.90 | 3.70 |
| 5 | 3 | choice | switch | red | −0.003 | −0.371 | 46.31 | 5.11 |
| 6 | 3 | choice | switch | blue | −0.158 | −0.375 | 47.88 | 6.68 |
| 7 | 3 | choice | hide | blue | 0.006 | −0.104 | 49.40 | 8.20 |
| 8 | 3 | predict | predict | blue | 0.185 | 0.240 | 56.75 | 15.55 |
| 9 | 3 | event | trial_end | – | – | – | 57.30 | 16.10 |

Nine rows. Nothing is collapsed. The five switches keep their own position and
time, which a one-row-per-trial format cannot do.

---

## Reading it

### One participant

```python
import json
from pathlib import Path
import pandas as pd

data = json.loads(Path("HideAndSeek/Data/S001/S001.json").read_text(encoding="utf-8"))

df = pd.DataFrame(data["rows"], columns=data["columns"])
df.insert(0, "subject", data["metadata"]["subject"])
```

Use `columns=` as shown: it fixes the column order and guarantees every column
exists, even if some rows happened to omit a key.

### Every participant

```python
frames = []
for path in sorted(Path("HideAndSeek/Data").glob("S*/*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    frame = pd.DataFrame(data["rows"], columns=data["columns"])
    frame.insert(0, "subject", data["metadata"]["subject"])
    frames.append(frame)

df = pd.concat(frames, ignore_index=True)
```

Concat at load time like this rather than pasting raw rows together: the rows
themselves do not carry the subject, so the label has to come from each file's
metadata.

### Two pandas gotchas

`null` becomes `NaN`, so a column that contains any `null` is read as a float.
`trial` is the one that matters, because session-level rows are `null`:

```python
df["trial"] = df["trial"].astype("Int64")
```

And to keep the session-level rows out of the way while you work:

```python
actions = df[df.phase != "event"]     # only touches
events  = df[df.phase == "event"]     # only markers
```

---

## Useful derived measures

**Pointing error per prediction** — how far the prediction was from the true
reveal position:

```python
predict = actions[actions.action == "predict"].copy()
predict["error"] = ((predict.x - predict.target_x) ** 2
                    + (predict.y - predict.target_y) ** 2) ** 0.5
```

**How much the child switched** — the wide view, one row per trial, deriving
what the long rows already contain:

```python
wide = actions.pivot_table(index=["subject", "trial"], columns="action",
                           values=["x", "y"], aggfunc="last")
wide.columns = [f"{value}_{action}" for value, action in wide.columns]

counts = (actions.groupby(["subject", "trial"])["action"]
                 .value_counts().unstack(fill_value=0))

order = (actions[actions.action == "switch"]
         .groupby(["subject", "trial"])["puppet"]
         .agg(">".join).rename("switch_order"))

trial = wide.join(counts).join(order)
```

This produces `x_switch`, `x_hide`, `x_predict`, `x_miss`, `y_*`, plus
`switch`, `hide`, `predict`, `miss` counts and a `switch_order` string such as
`blue>red>green>red>blue`. Note what it costs: only the **last** position of
each action survives (`aggfunc="last"`). The individual switch positions and
times are in the long rows, not here.

**Trial pacing** — `trial_end`'s `time_trial` is the trial duration, and
`predict.time_trial - hide.time_trial` is the delay between hiding the puppet
and committing to a prediction.

---

## Timing, and what it can and cannot support

`time_study` and `time_trial` come from PsychoPy's clock, read inside the press
handler — that is, when the touch event reaches the application.

They are fine for trial duration, overall pacing, and "did this child take two
seconds or thirty". They are **not** a reaction time in any strict sense.

The reason is the same one that made clean taps invisible to the original code:
Windows does not forward touch directly. It recognises the gesture first and
only then promotes it to a mouse event. The coordinates survive that faithfully
— a dedicated drift test found no displacement — but the *delay* is unknown and
probably varies with the gesture. So treat these times as approximate, and do
not report them as reaction times without investigating that delay separately.

---

## What is not recorded

- **No reaction-time-grade timings**, for the reason above.
- **No per-frame or per-reveal events.** The puppet's true position is in
  `target_x`, `target_y`, `target_angle`; the animation itself is not logged.
- **Nothing about the trial in progress** if the application crashes.
- **Only completed trials are backfilled.** If the study is stopped mid-trial,
  its rows keep `null` for `target_*` and `prediction_*`.
- **No eye-tracker, block or video fields.** These belonged to other studies in
  this project and were dropped.
