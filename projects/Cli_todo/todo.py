import os
import sys
import click

# Anchor data file next to this script so it works from any cwd.
_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'todo.txt')
_SEP = '\t'  # single tab as field separator – safe after sanitisation


def _load():
    """Return (latest_id: int, tasks: dict[str, str]).

    Handles missing file, empty file, and corrupt lines gracefully.
    """
    if not os.path.exists(_DATA_FILE):
        return 0, {}

    try:
        with open(_DATA_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except OSError as exc:
        click.echo(f'Warning: could not read {_DATA_FILE}: {exc}')
        return 0, {}

    if not lines:
        return 0, {}

    # First line: next-ID counter
    try:
        latest_id = int(lines[0].strip())
    except ValueError:
        click.echo('Warning: data file header is corrupt; resetting ID counter to 0.')
        latest_id = 0

    tasks = {}
    for lineno, line in enumerate(lines[1:], start=2):
        line = line.rstrip('\n')
        if not line:
            continue
        parts = line.split(_SEP, 1)
        if len(parts) != 2 or not parts[0].strip():
            click.echo(f'Warning: skipping malformed line {lineno}: {line!r}')
            continue
        task_id = parts[0].strip()
        task_text = parts[1]
        tasks[task_id] = task_text

    # Ensure latest_id is at least as large as any existing task ID + 1
    for tid in tasks:
        try:
            numeric = int(tid)
            if numeric >= latest_id:
                latest_id = numeric + 1
        except ValueError:
            pass

    return latest_id, tasks


def _save(latest_id, tasks):
    """Persist latest_id and tasks to the data file."""
    lines = [f'{latest_id}\n']
    for tid, text in tasks.items():
        lines.append(f'{tid}{_SEP}{text}\n')
    try:
        with open(_DATA_FILE, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except OSError as exc:
        click.echo(f'Error: could not write {_DATA_FILE}: {exc}')
        sys.exit(1)


def _sanitise(text):
    """Strip characters that would break the on-disk format."""
    return text.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').strip()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
@click.pass_context
def todo(ctx):
    '''Simple CLI Todo App'''
    ctx.ensure_object(dict)
    latest_id, tasks = _load()
    ctx.obj['LATEST'] = latest_id
    ctx.obj['TASKS'] = tasks


@todo.command()
@click.pass_context
def tasks(ctx):
    '''Display tasks'''
    task_dict = ctx.obj['TASKS']
    if task_dict:
        click.echo('YOUR TASKS\n**********')
        for tid, text in task_dict.items():
            click.echo(f'\u2022 {text} (ID: {tid})')
        click.echo('')
    else:
        click.echo('No tasks yet! Use ADD to add one.\n')


@todo.command()
@click.pass_context
@click.option('-add', '--add_task', prompt='Enter task to add')
def add(ctx, add_task):
    '''Add a task'''
    clean = _sanitise(add_task)
    if not clean:
        click.echo('Error: task text is empty after sanitisation.')
        return

    task_id = ctx.obj['LATEST']
    ctx.obj['TASKS'][str(task_id)] = clean
    click.echo(f'Added task "{clean}" with ID {task_id}')

    _save(task_id + 1, ctx.obj['TASKS'])


@todo.command()
@click.pass_context
@click.option('-fin', '--fin_taskid', prompt='Enter ID of task to finish', type=int)
def done(ctx, fin_taskid):
    '''Delete a task by ID'''
    tid = str(fin_taskid)
    task_dict = ctx.obj['TASKS']

    if tid not in task_dict:
        click.echo(f'Error: no task with id {fin_taskid}.')
        return

    task_text = task_dict.pop(tid)
    click.echo(f'Finished and removed task "{task_text}" with id {fin_taskid}')

    # Keep LATEST unchanged – IDs are monotonic, never reused.
    _save(ctx.obj['LATEST'], task_dict)


if __name__ == '__main__':
    todo()
