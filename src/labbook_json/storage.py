from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def save_state(path: str | Path, state: Any, *, indent: int = 2, sort_keys: bool = True) -> None:
    """Write ``state`` as UTF-8 JSON, creating parent directories as needed.

    Output is formatted with indentation by default to keep the file human
    readable, and keys are sorted unless ``sort_keys`` is disabled.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output_file:
            json.dump(
                state,
                output_file,
                indent=indent,
                sort_keys=sort_keys,
                ensure_ascii=False,
                allow_nan=False,
            )
            output_file.write("\n")
        temp_path.replace(output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def load_state(path: str | Path) -> Any:
    """Load and parse a UTF-8 JSON state file."""
    with Path(path).open("r", encoding="utf-8") as input_file:
        return json.load(input_file)
