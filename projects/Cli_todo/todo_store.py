import os
from pathlib import Path

DELIMITER = "```"
DEFAULT_PATH = Path(__file__).resolve().parent / "todo.txt"


def resolve_path(path=None):
    if path is not None:
        return Path(path)
    override = os.environ.get("TODO_FILE")
    if override:
        return Path(override)
    return DEFAULT_PATH


def parse(lines):
    cleaned = [line.rstrip("\n") for line in lines]
    cleaned = [line for line in cleaned if line.strip()]
    if not cleaned:
        return 0, {}

    try:
        latest = int(cleaned[0])
    except ValueError:
        latest = 0

    tasks = {}
    for line in cleaned[1:]:
        if DELIMITER not in line:
            continue
        key, value = line.split(DELIMITER, 1)
        key = key.strip()
        if not key:
            continue
        tasks[key] = value

    max_id = max((int(key) for key in tasks if key.isdigit()), default=-1)
    if latest <= max_id:
        latest = max_id + 1
    return latest, tasks


def serialize(latest, tasks):
    lines = [f"{latest}\n"]
    for key, value in tasks.items():
        lines.append(f"{key}{DELIMITER}{value}\n")
    return lines


class TodoStore:
    def __init__(self, path=None):
        self.path = resolve_path(path)
        self.latest = 0
        self.tasks = {}

    @classmethod
    def load(cls, path=None):
        store = cls(path)
        store.reload()
        return store

    def reload(self):
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                lines = handle.readlines()
        else:
            lines = []
        self.latest, self.tasks = parse(lines)
        return self

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            handle.writelines(serialize(self.latest, self.tasks))

    def add(self, text):
        task_id = str(self.latest)
        self.tasks[task_id] = text
        self.latest += 1
        return task_id

    def remove(self, task_id):
        key = str(task_id)
        if key not in self.tasks:
            return None
        return self.tasks.pop(key)

    def __contains__(self, task_id):
        return str(task_id) in self.tasks
