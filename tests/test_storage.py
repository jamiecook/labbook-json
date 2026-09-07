from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labbook_json import load_state, save_state


class StorageTests(unittest.TestCase):
    def test_save_and_load_state_round_trip(self) -> None:
        state = {"trial": 1, "metrics": {"loss": 0.1}, "tags": ["baseline"]}

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runs" / "state.json"

            save_state(path, state)

            self.assertEqual(load_state(path), state)

    def test_save_state_uses_human_readable_json(self) -> None:
        state = {"z": 1, "a": {"value": True}, "title": "café"}

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"

            save_state(path, state)

            contents = path.read_text(encoding="utf-8")

            self.assertTrue(contents.endswith("\n"))
            self.assertEqual(json.loads(contents), state)
            self.assertIn('  "a"', contents)
            self.assertIn("café", contents)
            self.assertLess(contents.index('"a"'), contents.index('"title"'))
            self.assertLess(contents.index('"title"'), contents.index('"z"'))

    def test_load_state_raises_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text("{invalid json}\n", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                load_state(path)

    def test_save_state_rejects_non_json_float_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"

            with self.assertRaises(ValueError):
                save_state(path, {"value": float("nan")})


if __name__ == "__main__":
    unittest.main()
