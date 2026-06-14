# Simple CLI Todo App
Simple Todo app with command line interface. Supports adding tasks with a
priority, completing them (kept as history rather than deleted), and viewing /
filtering task entries by status or priority.

## Dependencies
Requires Python 3 and Click

Install Click: `pip install click`

## How to use
### Running
either run it from your code editor or Ide or type `python todo.py [command]` in your command line.
(insted of [command] add desired command u want)

### Commands
|Command | Description|
|-------|-------|
|`add [TASK] [-p/--priority low\|medium\|high]`| Adds a task (priority defaults to `medium`). Prompts for the text if `TASK` is omitted. |
|`done [ID]`| Marks a task as done. The task is kept in history (not deleted). Prompts for the id if omitted. |
|`tasks [-a/--all] [-s/--status ...] [-p/--priority ...]`| Lists tasks. Shows pending tasks by default, sorted highest priority first. |

The old `add` / `tasks` / `done` usage still works exactly as before — the new
options are all optional additions.

### Options
- `-f, --file PATH` (on the `todo` group): path to the data file (default `./todo.txt`).
- `add -p, --priority`: one of `low`, `medium`, `high`.
- `tasks -a, --all`: include completed tasks.
- `tasks -s, --status`: show only `pending` or `done` tasks.
- `tasks -p, --priority`: show only tasks of the given priority.

#### Examples
```
python todo.py add "Write the report" -p high
python todo.py tasks                 # pending tasks, high priority first
python todo.py done 0                # mark task 0 done (kept in history)
python todo.py tasks --all           # include completed tasks
python todo.py tasks --status done   # review what you've finished
python todo.py tasks --priority high # only high-priority tasks
```

### Data format & compatibility
Tasks are stored locally in `todo.txt` as JSON (id, text, status, priority,
created/completed timestamps). Older line-based `todo.txt` files from previous
versions are detected and read automatically; they are upgraded to the new JSON
layout the next time the file is written.
