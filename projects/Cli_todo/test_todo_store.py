import os
import sys
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import todo
from todo_store import TodoStore, parse, resolve_path, DEFAULT_PATH


class ParseTests(unittest.TestCase):
    def test_parse_empty(self):
        self.assertEqual(parse([]), (0, {}))

    def test_parse_legacy_content(self):
        latest, tasks = parse(["2\n", "0```buy milk\n", "1```call mom\n"])
        self.assertEqual(latest, 2)
        self.assertEqual(tasks, {"0": "buy milk", "1": "call mom"})

    def test_parse_skips_malformed_lines_and_keeps_counter_safe(self):
        latest, tasks = parse(["0\n", "broken\n", "5```real task\n"])
        self.assertEqual(latest, 6)
        self.assertEqual(tasks, {"5": "real task"})


class StoreTests(unittest.TestCase):
    def test_default_path_is_script_relative(self):
        self.assertEqual(resolve_path(), DEFAULT_PATH)

    def test_env_override_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "custom.txt"
            old = os.environ.get("TODO_FILE")
            os.environ["TODO_FILE"] = str(override)
            try:
                self.assertEqual(resolve_path(), override)
            finally:
                if old is None:
                    os.environ.pop("TODO_FILE", None)
                else:
                    os.environ["TODO_FILE"] = old

    def test_add_remove_and_save_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "todo.txt"
            store = TodoStore(data_file)
            self.assertEqual(store.add("first"), "0")
            self.assertEqual(store.add("second"), "1")
            self.assertEqual(store.remove(0), "first")
            store.save()

            reloaded = TodoStore.load(data_file)
            self.assertEqual(reloaded.latest, 2)
            self.assertEqual(reloaded.tasks, {"1": "second"})


class CliTests(unittest.TestCase):
    def run_cli(self, data_file, *args):
        runner = CliRunner()
        old = os.environ.get("TODO_FILE")
        os.environ["TODO_FILE"] = str(data_file)
        try:
            return runner.invoke(todo.todo, list(args))
        finally:
            if old is None:
                os.environ.pop("TODO_FILE", None)
            else:
                os.environ["TODO_FILE"] = old

    def test_cli_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "todo.txt"
            add_result = self.run_cli(data_file, "add", "--add_task", "ship feature")
            self.assertEqual(add_result.exit_code, 0)
            self.assertIn("ID 0", add_result.output)

            list_result = self.run_cli(data_file, "tasks")
            self.assertEqual(list_result.exit_code, 0)
            self.assertIn("ship feature", list_result.output)

            done_result = self.run_cli(data_file, "done", "--fin_taskid", "0")
            self.assertEqual(done_result.exit_code, 0)
            self.assertIn("Finished and removed", done_result.output)

            store = TodoStore.load(data_file)
            self.assertEqual(store.latest, 1)
            self.assertEqual(store.tasks, {})


if __name__ == "__main__":
    unittest.main()
