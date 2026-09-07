from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_state(path: str | Path, state: Any, *, indent: int = 2, sort_keys: bool = True) -> None:
    """Write ``state`` as UTF-8 JSON, creating parent directories as needed.

    Output is formatted with indentation by default to keep the file human
    readable, and keys are sorted unless ``sort_keys`` is disabled.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(state, output_file, indent=indent, sort_keys=sort_keys)
        output_file.write("\n")


def load_state(path: str | Path) -> Any:
    """Load and parse a UTF-8 JSON state file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
