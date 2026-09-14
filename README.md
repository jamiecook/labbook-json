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

## Why use labbook-json instead of another persistence package?

`labbook-json` is intended for small experiment-state documents that should remain readable and
editable by people and other tools. Its distinguishing behavior is a write-through mapping or
Pydantic-model view: assignments, including nested dictionary assignments, are immediately written
to a selected section of one JSON document.

| Alternative | Prefer it when | Why use `labbook-json` instead |
| --- | --- | --- |
| Python's `json` module | Explicit load/modify/save code is sufficient | `labbook-json` supplies a mutable view, immediate write-through behavior, nested section addressing, and optional Pydantic model proxies. |
| Python's `shelve` | Values are arbitrary Python objects and Python-only storage is acceptable | A shelf stores pickled objects in a platform-dependent DBM database. Nested mutations require reassignment or `writeback=True`, which caches accessed values until synchronization. `labbook-json` stores portable JSON and detects nested dictionary mutations immediately. It also avoids pickle's arbitrary-code-execution risk when loading untrusted data. |
| TinyDB | The application needs document IDs, tables, searches, queries, updates, or deletion across a collection of records | `labbook-json` is deliberately not a document database. It manages one known experiment document and can address an existing nested section directly, without introducing tables or a query API. |
| SQLite | The application needs transactions, concurrent access, relational queries, indexes, constraints, or efficient partial updates | `labbook-json` keeps the complete state visible as ordinary formatted JSON and provides a much smaller mapping/model API. SQLite is the better choice once database guarantees or query performance matter. |
| `pickle`, `joblib`, or similar object serialization | Faithful persistence of complex Python or NumPy objects is more important than interoperability | `labbook-json` limits state to JSON-compatible values (or values serialized by a supported model), producing files that can be inspected, diffed, edited, and consumed outside Python. |
| Pydantic JSON parsing/serialization alone | Validation and explicit model load/dump operations are enough | `persist_model` adds a write-through proxy and nested-document placement around Pydantic validation; field assignments are persisted without a separate dump step. |

This simplicity has important limits. `labbook-json` rewrites the complete JSON document after every
mutation. It currently provides no transactions, file locking, atomic replacement, merge handling,
or safe concurrent writers. It is therefore appropriate for small state files with one writer, not
as a general database. Use SQLite or another database when durability, concurrency, large documents,
or frequent high-volume updates matter.

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
