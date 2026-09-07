from __future__ import annotations

import json
import pytest
from pydantic import BaseModel

from labbook_json import persist_model, persist_state


class MyPydanticModel(BaseModel):
    arg1: int = 1


def test_persist_model_with_sub_key_and_typed_model(tmp_path):
    state_file = tmp_path / "pipeline.json"
    state_file.write_text(
        json.dumps(
            {
                "state": {
                    "data_dir": str(tmp_path / "workflow"),
                    "current_year": 2020,
                },
                "metadata": {"run_id": "abc123"},
            }
        ),
        encoding="utf-8",
    )

    run_state = persist_model(state_file, MyPydanticModel, sub_key="my_sub_key")
    assert run_state.arg1 == 1

    run_state.arg1 = 2026

    # Persisted immediately on mutation, no context exit required.
    updated = json.loads(state_file.read_text(encoding="utf-8"))
    assert updated["my_sub_key"]["arg1"] == 2026

    # Metadata should remain unchanged
    assert updated["metadata"]["run_id"] == "abc123"


def test_persist_state_dict_persists_on_each_mutation(tmp_path):
    state_file = tmp_path / "task.state.json"

    def from_file():
        return json.loads(state_file.read_text(encoding="utf-8"))

    task_state = persist_state(state_file)
    task_state["status"] = "running"

    assert from_file()["status"] == "running"

    task_state["status"] = "succeeded"
    task_state["duration"] = 1.5
    assert from_file() == {"status": "succeeded", "duration": 1.5}

    task_state["nesting"] = {"a": 1, "b": 2}
    assert from_file()["nesting"] == {"a": 1, "b": 2}

    task_state["nesting"]["a"] = 10
    assert from_file()["nesting"] == {"a": 10, "b": 2}

    task_state.pop("duration")
    assert from_file() == {"status": "succeeded", "nesting": {"a": 10, "b": 2}}


def test_persist_state_sub_key_isolates_namespaces(tmp_path):
    state_file = tmp_path / "shared.json"

    a = persist_state(state_file, sub_key="task_a")
    b = persist_state(state_file, sub_key="task_b")

    a["x"] = 1
    b["x"] = 2

    contents = json.loads(state_file.read_text(encoding="utf-8"))
    assert contents == {"task_a": {"x": 1}, "task_b": {"x": 2}}


def test_persist_state_deep_path_with_list_match(tmp_path):
    pipeline = tmp_path / "pipeline.json"
    pipeline.write_text(
        json.dumps(
            {
                "tasks": [
                    {"name": "usim_2020_2025", "metadata": {"stage_config": {"base_year": 2020}}},
                    {"name": "usim_2025_2030", "metadata": {"stage_config": {"base_year": 2025}}},
                ]
            }
        ),
        encoding="utf-8",
    )

    path = ["tasks", ("name", "usim_2025_2030"), "metadata", "stage_config"]
    cfg = persist_state(pipeline, sub_key=path)
    assert cfg["base_year"] == 2025

    cfg["simulation_id"] = "sim-123"

    contents = json.loads(pipeline.read_text(encoding="utf-8"))
    assert contents["tasks"][1]["metadata"]["stage_config"]["simulation_id"] == "sim-123"
    # Sibling task untouched.
    assert "simulation_id" not in contents["tasks"][0]["metadata"]["stage_config"]

    path = ["tasks", ("name", "usim_2025_203x"), "metadata", "stage_config"]
    with pytest.raises(KeyError):
        cfg = persist_state(pipeline, sub_key=path)


def test_persist_state_dotted_path(tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"a": {"b": {"c": 1}}}), encoding="utf-8")

    node = persist_state(f, sub_key="a.b")
    assert node["c"] == 1
    node["c"] = 42
    assert json.loads(f.read_text(encoding="utf-8"))["a"]["b"]["c"] == 42
