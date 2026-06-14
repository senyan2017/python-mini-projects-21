"""Storage layer for the CLI todo app.

Handles reading, writing, and parsing of the todo.txt data file.
File format (backward-compatible with original):
  - Line 1: next_id (integer counter)
  - Lines 2+: ``<id>```<task_text>``
"""

import os

# Separator used in the data file between task ID and task text.
SEP = "```"


class TodoStore:
    """Manages the task list and its persistence to a text file.

    Parameters
    ----------
    path : str
        Path to the data file (e.g. ``./todo.txt``).
    """

    def __init__(self, path="./todo.txt"):
        self.path = path
        self.next_id = 0
        self.tasks = {}  # type: dict[str, str]  {id_str: task_text}
        self._load()

    # ------------------------------------------------------------------
    # Parsing helpers (static / class-level so they are easy to test)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_content(raw: str) -> tuple[int, dict[str, str]]:
        """Parse the raw text content of a todo data file.

        Returns
        -------
        (next_id, tasks)
            ``next_id`` is the counter for the next new task.
            ``tasks`` maps id-strings to task text.
        """
        lines = raw.splitlines()
        if not lines or not lines[0].strip():
            return 0, {}

        # First line: next_id counter.
        try:
            next_id = int(lines[0].strip())
        except ValueError:
            next_id = 0

        tasks: dict[str, str] = {}
        for line in lines[1:]:
            line = line.rstrip("\n")
            if not line:
                continue
            if SEP in line:
                id_part, task_text = line.split(SEP, 1)
                tasks[id_part.strip()] = task_text
            # Silently skip malformed lines (forward-compatible).

        return next_id, tasks

    @staticmethod
    def serialize(next_id: int, tasks: dict[str, str]) -> str:
        """Serialize *next_id* and *tasks* into the data-file format."""
        lines = [str(next_id)]
        for id_str, text in tasks.items():
            lines.append(f"{id_str}{SEP}{text}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load data from disk.  Creates an empty store if the file is
        missing or unreadable."""
        if not os.path.exists(self.path):
            self.next_id = 0
            self.tasks = {}
            return
        try:
            with open(self.path, "r") as fh:
                raw = fh.read()
        except OSError:
            raw = ""
        self.next_id, self.tasks = self.parse_content(raw)

    def save(self) -> None:
        """Write the current state back to disk."""
        content = self.serialize(self.next_id, self.tasks)
        with open(self.path, "w") as fh:
            fh.write(content)

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def add_task(self, text: str) -> int:
        """Add a new task and persist it.  Returns the assigned ID."""
        task_id = self.next_id
        self.tasks[str(task_id)] = text
        self.next_id += 1
        self.save()
        return task_id

    def complete_task(self, task_id: int) -> str | None:
        """Remove the task with *task_id*.

        Returns the task text on success, or ``None`` if not found.
        """
        key = str(task_id)
        if key not in self.tasks:
            return None
        text = self.tasks.pop(key)
        # Reset counter when the list becomes empty (matches original
        # behaviour and keeps IDs small for casual use).
        if not self.tasks:
            self.next_id = 0
        self.save()
        return text

    def list_tasks(self) -> list[tuple[str, str]]:
        """Return a list of ``(id_str, task_text)`` pairs."""
        return list(self.tasks.items())
