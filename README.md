# labbook-json
A small library to transparently allow you to save your experiment state to a human readable JSON file.

## Installation

```bash
pip install labbook-json
```

## Usage

```python
from labbook_json import load_state, save_state

state = {"epoch": 4, "accuracy": 0.97}
save_state("state.json", state)

restored_state = load_state("state.json")
```
