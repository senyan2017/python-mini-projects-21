"""Regression tests for the CLI todo app.

Focus areas (per the hardening work):
  * the tool works from any current working directory;
  * missing / empty / dirty / corrupt data files degrade instead of crashing;
  * task ids increase monotonically and are never reused or inflated;
  * the add / finish flow behaves and persists correctly;
  * arbitrary task content (quotes, delimiters, unicode) round-trips losslessly.
"""

import json
import os
import sys

import pytest
from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import todo  # noqa: E402


@pytest.fixture()
def todo_file(tmp_path, monkeypatch):
    """Point the app at an isolated data file via the TODO_FILE override."""
    path = tmp_path / "todo.txt"
    monkeypatch.setenv("TODO_FILE", str(path))
    return path


def run(*args, input=None):
    return CliRunner().invoke(todo.todo, list(args), input=input)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- missing / empty / corrupt data -----------------------------------------

def test_missing_file_does_not_crash(todo_file):
    assert not todo_file.exists()
    result = run("tasks")
    assert result.exit_code == 0
    assert result.exception is None
    assert "No tasks yet!" in result.output


def test_empty_file_does_not_crash(todo_file):
    todo_file.write_text("", encoding="utf-8")
    result = run("tasks")
    assert result.exit_code == 0
    assert result.exception is None
    assert "No tasks yet!" in result.output


def test_corrupt_file_degrades_to_empty(todo_file):
    todo_file.write_text("this is not json and has no delimiter", encoding="utf-8")
    result = run("tasks")
    assert result.exit_code == 0
    assert result.exception is None
    assert "No tasks yet!" in result.output


def test_corrupt_file_then_add_recovers(todo_file):
    todo_file.write_text("{garbage", encoding="utf-8")
    result = run("add", "--add_task", "fresh start")
    assert result.exit_code == 0
    assert "with ID 0" in result.output
    data = read_json(todo_file)
    assert data["tasks"] == {"0": "fresh start"}


# --- legacy format compatibility --------------------------------------------

def test_reads_legacy_format(todo_file):
    todo_file.write_text("1\n0```buy milk\n", encoding="utf-8")
    result = run("tasks")
    assert result.exit_code == 0
    assert "buy milk" in result.output
    assert "(ID: 0)" in result.output


def test_legacy_delimiter_inside_content_recovered(todo_file):
    # A task body that itself contains the legacy delimiter must survive.
    todo_file.write_text("1\n0```a```b\n", encoding="utf-8")
    result = run("tasks")
    assert result.exit_code == 0
    assert "a```b" in result.output


def test_legacy_migrates_to_json_on_write(todo_file):
    todo_file.write_text("1\n0```old task\n", encoding="utf-8")
    result = run("add", "--add_task", "new task")
    assert result.exit_code == 0
    data = read_json(todo_file)  # file is now JSON
    assert data["tasks"]["0"] == "old task"
    assert data["tasks"]["1"] == "new task"
    assert data["latest"] == 2


# --- id semantics ------------------------------------------------------------

def test_ids_increment_monotonically(todo_file):
    assert "with ID 0" in run("add", "--add_task", "a").output
    assert "with ID 1" in run("add", "--add_task", "b").output
    assert "with ID 2" in run("add", "--add_task", "c").output
    assert read_json(todo_file)["latest"] == 3


def test_done_does_not_inflate_counter(todo_file):
    run("add", "--add_task", "a")  # id 0
    run("add", "--add_task", "b")  # id 1
    assert read_json(todo_file)["latest"] == 2
    run("done", "--fin_taskid", "0")
    # Finishing must NOT advance the counter.
    assert read_json(todo_file)["latest"] == 2
    # Next add continues from 2, never reusing 0 or skipping to 3.
    assert "with ID 2" in run("add", "--add_task", "c").output


def test_ids_not_reused_after_clearing_all(todo_file):
    run("add", "--add_task", "a")  # id 0
    run("done", "--fin_taskid", "0")
    assert read_json(todo_file)["tasks"] == {}
    # Counter is preserved across an empty list -> next id is 1, not 0.
    assert "with ID 1" in run("add", "--add_task", "b").output


def test_normalize_latest_prevents_collision_from_bad_counter(todo_file):
    # Counter says 0 but a task with id 5 already exists -> next must be 6.
    todo_file.write_text(
        json.dumps({"latest": 0, "tasks": {"5": "x"}}), encoding="utf-8"
    )
    assert "with ID 6" in run("add", "--add_task", "y").output


# --- finish flow -------------------------------------------------------------

def test_done_removes_task(todo_file):
    run("add", "--add_task", "a")
    result = run("done", "--fin_taskid", "0")
    assert result.exit_code == 0
    assert "Finished and removed" in result.output
    assert read_json(todo_file)["tasks"] == {}


def test_done_unknown_id_is_friendly(todo_file):
    run("add", "--add_task", "a")
    result = run("done", "--fin_taskid", "999")
    assert result.exit_code == 0
    assert result.exception is None  # no traceback
    assert "Error: no task with id 999" in result.output


# --- special characters ------------------------------------------------------

@pytest.mark.parametrize(
    "content",
    [
        'has "double" quotes',
        "contains ``` delimiter",
        "comma, separated, values",
        "emoji 🚀 and accents éà",
        "back\\slash and tab\tend",
    ],
)
def test_special_characters_round_trip(todo_file, content):
    add_result = run("add", "--add_task", content)
    assert add_result.exit_code == 0
    # File must remain valid JSON regardless of content.
    data = read_json(todo_file)
    assert data["tasks"]["0"] == content
    # A subsequent run (fresh load) must read the exact same content back.
    list_result = run("tasks")
    assert content in list_result.output


# --- cwd independence --------------------------------------------------------

def test_works_from_any_cwd(tmp_path, monkeypatch):
    data_path = tmp_path / "data" / "todo.txt"
    data_path.parent.mkdir()
    monkeypatch.setenv("TODO_FILE", str(data_path))

    other_dir = tmp_path / "somewhere" / "else"
    other_dir.mkdir(parents=True)
    monkeypatch.chdir(other_dir)  # run from an unrelated directory

    result = run("add", "--add_task", "from elsewhere")
    assert result.exit_code == 0
    assert data_path.exists()  # written to TODO_FILE, not the cwd
    assert read_json(data_path)["tasks"]["0"] == "from elsewhere"


def test_default_path_is_anchored_to_script_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("TODO_FILE", raising=False)
    monkeypatch.chdir(tmp_path)  # cwd changed, default must not follow it
    expected = os.path.join(os.path.dirname(os.path.abspath(todo.__file__)), "todo.txt")
    assert str(todo.data_file()) == expected
