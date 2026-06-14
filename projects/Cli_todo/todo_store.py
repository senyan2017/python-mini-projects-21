"""Storage and core logic for the CLI todo app.

All file-path, parsing, serialization and task-ID handling live here so the CLI
layer (``todo.py``) never has to know how tasks are stored on disk. Keeping this
separate means new commands can be added without touching file details.

The on-disk format is kept identical to the original ``todo.txt`` layout so that
existing data keeps working without any migration::

    <next-id>
    <id>```<task text>
    <id>```<task text>
    ...

The first line is the next ID to hand out; every following line is a single
task, with the id and the text separated by a triple-backtick delimiter.

The parser is deliberately forgiving: empty files, blank lines, a missing
trailing newline and malformed lines are all tolerated rather than crashing,
so an old or hand-edited ``todo.txt`` degrades smoothly instead of blowing up.
"""

import os

DEFAULT_PATH = "./todo.txt"
DELIMITER = "```"


def parse(lines):
    """Parse raw ``todo.txt`` lines into ``(next_id, tasks)``.

    ``lines`` is any iterable of strings (with or without trailing newlines).
    Returns a tuple of ``(int next_id, dict {str id: str text})``.

    Tolerates empty input, blank lines, a missing trailing newline and lines
    that lack the delimiter (those are skipped). ``next_id`` is always kept
    strictly greater than every existing numeric id so ids can never collide,
    even if the stored counter is stale.
    """
    cleaned = [line.rstrip("\n") for line in lines]
    cleaned = [line for line in cleaned if line.strip() != ""]
    if not cleaned:
        return 0, {}

    header, body = cleaned[0], cleaned[1:]
    try:
        latest = int(header)
    except ValueError:
        # Garbled counter line: fall back to 0 and let the collision guard
        # below recompute a safe value from whatever tasks we can recover.
        latest = 0

    tasks = {}
    for line in body:
        if DELIMITER not in line:
            continue
        key, value = line.split(DELIMITER, 1)
        key = key.strip()
        if key == "":
            continue
        tasks[key] = value

    max_id = max((int(k) for k in tasks if k.isdigit()), default=-1)
    if latest <= max_id:
        latest = max_id + 1
    return latest, tasks


def serialize(latest, tasks):
    """Serialize ``(next_id, tasks)`` back into a list of ``todo.txt`` lines."""
    lines = ["%d\n" % latest]
    for key, value in tasks.items():
        lines.append("%s%s%s\n" % (key, DELIMITER, value))
    return lines


class TodoStore:
    """In-memory view of the todo list, backed by a text file.

    Owns the data-file path and all read/write/ID bookkeeping. The CLI talks to
    this object instead of opening files itself.
    """

    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        self.latest = 0
        self.tasks = {}

    @classmethod
    def load(cls, path=DEFAULT_PATH):
        """Create a store and populate it from ``path`` (missing file is ok)."""
        store = cls(path)
        store.reload()
        return store

    def reload(self):
        """(Re)read the backing file into memory. Missing file -> empty list."""
        if os.path.exists(self.path):
            with open(self.path) as f:
                lines = f.readlines()
        else:
            lines = []
        self.latest, self.tasks = parse(lines)
        return self

    def save(self):
        """Write the current state back to the backing file."""
        with open(self.path, "w") as f:
            f.writelines(serialize(self.latest, self.tasks))

    def add(self, text):
        """Add a task, returning the id (as a string) assigned to it."""
        task_id = str(self.latest)
        self.tasks[task_id] = text
        self.latest += 1
        return task_id

    def remove(self, task_id):
        """Remove a task by id.

        Returns the removed task's text, or ``None`` if no such id exists.
        Removing the final task resets the id counter to 0 (mirroring the
        original behavior) so a freshly emptied list starts numbering again.
        """
        key = str(task_id)
        if key not in self.tasks:
            return None
        text = self.tasks.pop(key)
        if not self.tasks:
            self.latest = 0
        return text

    def __contains__(self, task_id):
        return str(task_id) in self.tasks
