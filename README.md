# labbook-json
A small library to transparently allow you to save your experiment state to a human readable JSON file.

Works with state represented as a dictionary or as a more structured Pydantic model.

## Installation

```bash
pip install labbook-json
```

## Usage

### Persisting dictionary state

```python
from pathlib import Path

from labbook_json import persist_state

state = persist_state(Path("state.json"))
state["epoch"] = 4
state["accuracy"] = 0.97

# Changes are written immediately, including nested dictionaries.
state["metrics"] = {"loss": 0.12}
state["metrics"]["loss"] = 0.08
```

`persist_state` returns a mutable mapping backed by a JSON file. Its existing contents are loaded
when it is created, and every mapping mutation is immediately written back to disk.

### Persisting Pydantic models

```python
from pathlib import Path

from pydantic import BaseModel

from labbook_json import persist_model


class RunState(BaseModel):
    epoch: int = 0
    accuracy: float | None = None


state = persist_model(Path("state.json"), RunState)
state.epoch = 4
state.accuracy = 0.97
```

`persist_model` loads the selected JSON object into the supplied Pydantic model and returns a
proxy. Direct assignments to model attributes are immediately persisted. Access the underlying
model through `state.wrapped` when a concrete `RunState` instance is required.

### Persisting a section of a shared file

Use `sub_key` to manage independent dictionary or model state within one JSON document:

```python
from pathlib import Path

from labbook_json import persist_state

task_state = persist_state(Path("pipeline.json"), sub_key="tasks.current")
task_state["status"] = "running"
```

`sub_key` may be a key, a dotted path, or an explicit sequence of dictionary keys, list indexes,
and `(field, value)` pairs that select an object from a list.

## Releasing to PyPI

1. Update the package version in `pyproject.toml`.
2. Run the test suite and confirm the working tree is clean:

   ```bash
   pytest
   git status --short
   ```

3. Remove old build artifacts and create distribution files:

   ```bash
   rm -rf build dist *.egg-info
   python -m build
   python -m twine check dist/*
   ```

4. Upload the verified distributions:

   ```bash
   python -m twine upload dist/*
   ```

`build` and `twine` can be installed with `python -m pip install build twine`.
Use a PyPI API token as the password when prompted (username: `__token__`). PyPI does not allow replacing an existing version, so verify the version before uploading.
