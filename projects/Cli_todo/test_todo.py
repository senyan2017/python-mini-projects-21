"""Tests for the CLI todo app.

Covers both ends the refactor was meant to protect:

* the storage layer (:mod:`todo_store`) -- parsing, serialization, ID handling,
  task removal and round-tripping through a real file; and
* the CLI entry points (``add`` / ``tasks`` / ``done`` in :mod:`todo`) driven
  through Click's ``CliRunner`` in an isolated filesystem.

Run with::

    python -m unittest test_todo -v
"""

import tempfile
import unittest

from click.testing import CliRunner

import todo_store
from todo_store import TodoStore, parse, serialize
from todo import todo


class TestStorageLogic(unittest.TestCase):
    """Pure parsing / serialization / ID logic -- no CLI involved."""

    def test_parse_empty_inputs(self):
        self.assertEqual(parse([]), (0, {}))
        self.assertEqual(parse(["\n"]), (0, {}))
        # This is exactly what the shipped todo.txt contained ("0\n\n");
        # the original parser crashed on it, the new one degrades to empty.
        self.assertEqual(parse(["0\n", "\n"]), (0, {}))

    def test_parse_normal(self):
        latest, tasks = parse(["2\n", "0```buy milk\n", "1```walk dog\n"])
        self.assertEqual(latest, 2)
        self.assertEqual(tasks, {"0": "buy milk", "1": "walk dog"})

    def test_parse_missing_trailing_newline(self):
        # Original code did value[:-1], which chopped the last real character
        # when the final line had no newline. Here the text must stay intact.
        _, tasks = parse(["1\n", "0```buy milk"])
        self.assertEqual(tasks["0"], "buy milk")

    def test_parse_skips_blank_and_malformed_lines(self):
        _, tasks = parse(["1\n", "\n", "no-delimiter-here\n", "0```ok\n"])
        self.assertEqual(tasks, {"0": "ok"})

    def test_parse_value_may_contain_delimiter(self):
        # Splitting on the first delimiter only keeps the rest of the value.
        _, tasks = parse(["1\n", "0```a```b\n"])
        self.assertEqual(tasks["0"], "a```b")

    def test_parse_counter_never_collides(self):
        # Stale/too-small counter is bumped past the highest existing id.
        latest, _ = parse(["0\n", "5```late entry\n"])
        self.assertEqual(latest, 6)

    def test_serialize_round_trips_through_parse(self):
        latest_in, tasks_in = 2, {"0": "x", "1": "y z"}
        latest_out, tasks_out = parse(serialize(latest_in, tasks_in))
        self.assertEqual((latest_out, tasks_out), (latest_in, tasks_in))


class TestStoreOperations(unittest.TestCase):
    """TodoStore behavior: add / remove / ID counter / file round-trip."""

    def test_add_assigns_id_and_increments(self):
        store = TodoStore()
        self.assertEqual(store.add("first"), "0")
        self.assertEqual(store.add("second"), "1")
        self.assertEqual(store.latest, 2)
        self.assertEqual(store.tasks, {"0": "first", "1": "second"})

    def test_remove_existing_keeps_counter(self):
        store = TodoStore()
        store.latest, store.tasks = 3, {"0": "a", "1": "b"}
        self.assertEqual(store.remove("0"), "a")
        self.assertEqual(store.latest, 3)  # counter NOT bumped by removal
        self.assertEqual(store.tasks, {"1": "b"})

    def test_remove_last_task_resets_counter(self):
        store = TodoStore()
        store.latest, store.tasks = 5, {"2": "only"}
        self.assertEqual(store.remove(2), "only")  # int id accepted too
        self.assertEqual(store.latest, 0)
        self.assertEqual(store.tasks, {})

    def test_remove_missing_returns_none(self):
        store = TodoStore()
        store.latest, store.tasks = 1, {"0": "a"}
        self.assertIsNone(store.remove("99"))
        self.assertEqual(store.tasks, {"0": "a"})

    def test_contains(self):
        store = TodoStore()
        store.tasks = {"0": "a"}
        self.assertIn(0, store)
        self.assertIn("0", store)
        self.assertNotIn(1, store)

    def test_save_then_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = d + "/todo.txt"
            store = TodoStore(path)
            store.add("buy milk")
            store.add("walk dog")
            store.save()

            reloaded = TodoStore.load(path)
            self.assertEqual(reloaded.tasks, {"0": "buy milk", "1": "walk dog"})
            self.assertEqual(reloaded.latest, 2)

    def test_load_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            store = TodoStore.load(d + "/does-not-exist.txt")
            self.assertEqual((store.latest, store.tasks), (0, {}))

    def test_load_reads_legacy_file_format(self):
        # A file written in the original on-disk format must still load.
        with tempfile.TemporaryDirectory() as d:
            path = d + "/todo.txt"
            with open(path, "w") as f:
                f.write("3\n0```legacy one\n1```legacy two\n")
            store = TodoStore.load(path)
            self.assertEqual(store.tasks, {"0": "legacy one", "1": "legacy two"})
            self.assertEqual(store.latest, 3)


class TestCli(unittest.TestCase):
    """End-to-end CLI checks through Click's test runner."""

    def setUp(self):
        self.runner = CliRunner()

    def test_tasks_empty(self):
        with self.runner.isolated_filesystem():
            with open("todo.txt", "w") as f:
                f.write("0\n")
            result = self.runner.invoke(todo, ["tasks"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("No tasks yet! Use ADD to add one.", result.output)

    def test_tasks_with_missing_file_does_not_crash(self):
        # No todo.txt present -- the original code raised FileNotFoundError.
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(todo, ["tasks"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("No tasks yet!", result.output)

    def test_add_reports_id_and_persists(self):
        with self.runner.isolated_filesystem():
            with open("todo.txt", "w") as f:
                f.write("0\n")

            add_result = self.runner.invoke(todo, ["add", "--add_task", "buy milk"])
            self.assertEqual(add_result.exit_code, 0)
            self.assertIn('Added task "buy milk" with ID 0', add_result.output)

            # A fresh invocation must see the saved task.
            tasks_result = self.runner.invoke(todo, ["tasks"])
            self.assertIn("YOUR TASKS", tasks_result.output)
            self.assertIn("\u2022 buy milk (ID: 0)", tasks_result.output)

    def test_add_via_prompt(self):
        with self.runner.isolated_filesystem():
            with open("todo.txt", "w") as f:
                f.write("0\n")
            result = self.runner.invoke(todo, ["add"], input="walk dog\n")
            self.assertEqual(result.exit_code, 0)
            self.assertIn('Added task "walk dog" with ID 0', result.output)

    def test_done_removes_task(self):
        with self.runner.isolated_filesystem():
            with open("todo.txt", "w") as f:
                f.write("0\n")
            self.runner.invoke(todo, ["add", "--add_task", "buy milk"])

            done_result = self.runner.invoke(todo, ["done", "--fin_taskid", "0"])
            self.assertEqual(done_result.exit_code, 0)
            self.assertIn('Finished and removed task "buy milk" with id 0', done_result.output)

            tasks_result = self.runner.invoke(todo, ["tasks"])
            self.assertIn("No tasks yet!", tasks_result.output)

    def test_done_unknown_id_reports_error(self):
        with self.runner.isolated_filesystem():
            with open("todo.txt", "w") as f:
                f.write("0\n")
            result = self.runner.invoke(todo, ["done", "--fin_taskid", "99"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Error: no task with id 99", result.output)


if __name__ == "__main__":
    unittest.main()
