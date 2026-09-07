from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_state(path: str | Path, state: Any, *, indent: int = 2, sort_keys: bool = True) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(state, indent=indent, sort_keys=sort_keys) + "\n",
        encoding="utf-8",
    )


def load_state(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
