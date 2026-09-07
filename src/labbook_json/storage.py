from __future__ import annotations

import json
from collections.abc import Iterator, MutableMapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar, Union
from typing import Sequence

T = TypeVar("T")
ModelT_co = TypeVar("ModelT_co", covariant=True)


class ModelValidator(Protocol[ModelT_co]):
    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> ModelT_co: ...


def persist_state(state_file: Path, sub_key: KeyPath = None) -> "PersistentState":
    """Return a dict-like state object backed by ``state_file`` that persists on every mutation.

    ``sub_key`` may be ``None`` (whole file), a single key, a dotted path (``"a.b.c"``), or an
    explicit sequence of steps where each step is a dict key (``str``), a list index (``int``),
    or a ``(field, value)`` tuple selecting the list element whose ``element[field] == value``.
    """
    return PersistentState(state_file, sub_key=sub_key)


def persist_model(state_file: Path, state_class: ModelValidator[T], sub_key: KeyPath = None) -> "PersistentModel[T]":
    """Load ``state_class`` from ``state_file`` and persist it on every attribute assignment.

    ``state_class`` must be a pydantic ``BaseModel``. Returns a transparent proxy that behaves
    like the model but re-writes ``state_file`` whenever a field is set. ``sub_key`` accepts the
    same forms as :func:`persist_state` (``None``, a key, a dotted path, or a sequence of steps
    including list indices and ``(field, value)`` match tuples).
    """
    raw_state = _read_state_file(state_file, sub_key=sub_key)
    model = state_class.model_validate(raw_state)
    proxy = PersistentModel(state_file, sub_key, model)
    proxy._flush()
    return proxy


# A single step in a key path:
#   str                -> dict key
#   int                -> list index
#   (key, value) tuple -> the list element whose element[key] == value (match by field)
KeyStep = Union[str, int, tuple[str, Any]]

# A key path addressing a node deep in a JSON document.
#   None -> the whole document (root)
#   str  -> a single dict key, or a dotted path like "tasks.metadata.stage_config"
#   Sequence  -> an explicit list of KeySteps
KeyPath = Union[None, str, Sequence[KeyStep]]


class NoMatchingElement(KeyError):
    """Raised when a ``(field, value)`` key-path step matches no list element.

    Distinct from a plain missing dict key: a match miss is always an error and is never
    silently treated as "empty node" when reading.
    """


def _normalize_key_path(sub_key: KeyPath) -> list[KeyStep]:
    if sub_key is None:
        return []
    if isinstance(sub_key, str):
        return [part for part in sub_key.split(".") if part]
    return list(sub_key)


def _describe_path(steps: Sequence[KeyStep]) -> str:
    return "".join(f"[{s[0]}={s[1]!r}]" if isinstance(s, tuple) else f"[{s!r}]" for s in steps) or "<root>"


def _match_index(container: list, step: tuple[str, Any], steps_so_far: Sequence[KeyStep], state_file: Path) -> int:
    key, value = step
    for i, element in enumerate(container):
        if isinstance(element, dict) and element.get(key) == value:
            return i
    raise NoMatchingElement(
        f"State file {state_file}: no list element with {key}={value!r} at {_describe_path(steps_so_far)}"
    )


def _descend(root: Any, steps: Sequence[KeyStep], state_file: Path, create: bool) -> Any:
    node = root
    for depth, step in enumerate(steps):
        walked = steps[:depth]
        if isinstance(step, tuple):
            if not isinstance(node, list):
                raise RuntimeError(f"State file {state_file}: expected a list at {_describe_path(walked)}")
            node = node[_match_index(node, step, walked, state_file)]
        elif isinstance(step, int):
            if not isinstance(node, list):
                raise RuntimeError(f"State file {state_file}: expected a list at {_describe_path(walked)}")
            node = node[step]
        else:
            if not isinstance(node, dict):
                raise RuntimeError(f"State file {state_file}: expected a dict at {_describe_path(walked)}")
            if step not in node:
                if not create:
                    raise KeyError(f"State file {state_file}: missing key at {_describe_path(steps[: depth + 1])}")
                node[step] = {}
            node = node[step]
    return node


def _read_state_file(state_file: Path, sub_key: KeyPath = None) -> dict[str, Any]:
    if not state_file.exists():
        return {}

    root = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(root, dict):
        raise RuntimeError(f"State file {state_file} contains non-dict JSON. Cannot read state.")

    steps = _normalize_key_path(sub_key)
    if not steps:
        return root

    try:
        node = _descend(root, steps, state_file, create=False)
    except NoMatchingElement:
        raise
    except KeyError:
        return {}
    if not isinstance(node, dict):
        raise RuntimeError(
            f"State file {state_file} contains non-dict JSON at {_describe_path(steps)}. Cannot read state."
        )
    return node


def _write_state_file(state_file: Path, new_state: dict[str, Any], sub_key: KeyPath = None) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    root = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    if not isinstance(root, dict):
        raise RuntimeError(f"State file {state_file} contains non-dict JSON. Cannot update state.")

    steps = _normalize_key_path(sub_key)
    if not steps:
        root = new_state
    else:
        parent = _descend(root, steps[:-1], state_file, create=True)
        last = steps[-1]
        if isinstance(last, tuple):
            if not isinstance(parent, list):
                raise RuntimeError(f"State file {state_file}: expected a list at {_describe_path(steps[:-1])}")
            parent[_match_index(parent, last, steps[:-1], state_file)] = new_state
        elif isinstance(last, int):
            if not isinstance(parent, list):
                raise RuntimeError(f"State file {state_file}: expected a list at {_describe_path(steps[:-1])}")
            parent[last] = new_state
        else:
            if not isinstance(parent, dict):
                raise RuntimeError(f"State file {state_file}: expected a dict at {_describe_path(steps[:-1])}")
            parent[last] = new_state

    state_file.write_text(json.dumps(root, indent=4), encoding="utf-8")


def _serialize(obj: Any) -> dict[str, Any]:
    if isinstance(obj, PersistentState):
        return dict(obj._data)
    if isinstance(obj, dict):
        return obj

    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")

    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)

    if hasattr(obj, "__dict__"):
        return dict(vars(obj))

    raise TypeError(f"Unable to serialize state object of type {type(obj).__name__}")


class _WriteThroughDict(MutableMapping):
    """A ``dict`` view that mutates a backing dict in place and calls ``on_change`` after.

    ``__getitem__`` wraps nested dicts recursively so that arbitrarily deep in-place
    mutation (``d["a"]["b"] = 1``) bubbles a flush up to the owning :class:`PersistentState`.
    """

    __slots__ = ("_data", "_on_change")

    def __init__(self, data: dict[str, Any], on_change):
        self._data = data
        self._on_change = on_change

    def __getitem__(self, key: str) -> Any:
        value = self._data[key]
        if isinstance(value, dict):
            return _WriteThroughDict(value, self._on_change)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._on_change()

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        self._on_change()

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return repr(self._data)


class PersistentState(_WriteThroughDict):
    """A dict-like state object that writes through to a JSON file on every mutation.

    Manages its own lifetime: load happens on construction, and each ``__setitem__``,
    ``__delitem__``, ``pop``, ``update``, etc. is immediately flushed to ``state_file``
    (namespaced under ``sub_key`` when given), including nested-dict mutation such as
    ``state["a"]["b"] = 1``. No context manager required.
    """

    __slots__ = ("state_file", "sub_key")

    def __init__(self, state_file: Path, sub_key: KeyPath = None):
        self.state_file = state_file
        self.sub_key = sub_key
        super().__init__(_read_state_file(state_file, sub_key=sub_key), self._flush)

    def _flush(self) -> None:
        _write_state_file(self.state_file, self._data, sub_key=self.sub_key)

    def __repr__(self) -> str:
        return f"PersistentState({self._data!r}, file={self.state_file}, sub_key={self.sub_key!r})"


class PersistentModel(Generic[T]):
    """Transparent proxy around a (pydantic) model that persists on every attribute set.

    Reads/writes and method calls are forwarded to the wrapped model, so it behaves like the
    model itself (``.field``, ``.field = x``, ``.model_dump()``, ``isinstance`` via ``wrapped``).
    Any attribute assignment re-serializes the model to ``state_file`` (under ``sub_key``).

    Note: this is a proxy, not an instance of ``state_class``. Access the underlying model via
    ``.wrapped`` if a strict ``isinstance`` check is required.
    """

    __slots__ = ("_state_file", "_sub_key", "_model")

    def __init__(self, state_file: Path, sub_key: KeyPath, model: T):
        object.__setattr__(self, "_state_file", state_file)
        object.__setattr__(self, "_sub_key", sub_key)
        object.__setattr__(self, "_model", model)

    @property
    def wrapped(self) -> T:
        return self._model

    def _flush(self) -> None:
        _write_state_file(self._state_file, _serialize(self._model), sub_key=self._sub_key)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_model"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._model, name, value)
        self._flush()

    def __repr__(self) -> str:
        return f"PersistentModel({self._model!r}, file={self._state_file}, sub_key={self._sub_key!r})"
