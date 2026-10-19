"""Small, shared helpers for participant output."""

import json
from pathlib import Path


def write_json(path, data, *, allow_nan=False):
    """Replace a JSON file only after its new contents have been written fully.

    Keep the temporary file beside the destination so replacement stays on the
    same filesystem. If writing fails, the previous participant file is intact.
    """
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as output:
            json.dump(data, output, indent=2, allow_nan=allow_nan)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
