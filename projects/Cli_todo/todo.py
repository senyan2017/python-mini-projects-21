import json
import os
from pathlib import Path

import click

LEGACY_DELIM = '```'


def data_file():
    '''Resolve the data file path independently of the current working dir.

    Order of precedence:
      1. ``TODO_FILE`` environment variable (handy for tests / custom setups).
      2. ``todo.txt`` next to this script, so the tool works from any cwd.
    '''
    override = os.environ.get('TODO_FILE')
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / 'todo.txt'


def _normalize_latest(latest, tasks):
    '''Guarantee the next-id counter never collides with or reuses an id.'''
    max_id = -1
    for key in tasks:
        try:
            max_id = max(max_id, int(key))
        except (ValueError, TypeError):
            continue
    if not isinstance(latest, int) or latest <= max_id:
        latest = max_id + 1
    return latest


def _parse_legacy(raw):
    '''Best-effort read of the original ``latest`` + ``id```task`` format.

    Tolerates: empty/non-int counter, blank lines, lines missing the
    delimiter, a missing trailing newline, and the delimiter appearing
    *inside* a task body (only the first one splits, so content survives).
    '''
    lines = raw.splitlines()
    latest = 0
    if lines:
        try:
            latest = int(lines[0].strip())
        except ValueError:
            latest = 0
    tasks = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        if LEGACY_DELIM not in line:
            continue
        tid, task = line.split(LEGACY_DELIM, 1)
        tid = tid.strip()
        if tid:
            tasks[tid] = task
    return _normalize_latest(latest, tasks), tasks


def load_state():
    '''Load ``(latest, tasks)`` robustly. Never raises on bad/missing data.'''
    path = data_file()
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return 0, {}
    except OSError as exc:
        click.echo('Warning: could not read %s (%s). Starting with an empty list.' % (path, exc))
        return 0, {}

    if not raw.strip():
        return 0, {}

    # Preferred format: JSON.
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get('tasks'), dict):
        tasks = {str(k): str(v) for k, v in data['tasks'].items()}
        latest = data.get('latest', 0)
        if not isinstance(latest, int):
            latest = 0
        return _normalize_latest(latest, tasks), tasks

    # Fallback: legacy line format / best-effort recovery of dirty data.
    try:
        return _parse_legacy(raw)
    except Exception:
        click.echo('Warning: %s is corrupted; starting with an empty list.' % path)
        return 0, {}


def save_state(latest, tasks):
    '''Persist state as JSON so any task content is stored losslessly.'''
    path = data_file()
    payload = json.dumps({'latest': latest, 'tasks': tasks}, ensure_ascii=False, indent=2)
    try:
        path.write_text(payload + '\n', encoding='utf-8')
    except OSError as exc:
        raise click.ClickException('Could not write %s (%s)' % (path, exc))


@click.group()
@click.pass_context
def todo(ctx):
    '''Simple CLI Todo App'''
    ctx.ensure_object(dict)
    latest, tasks = load_state()
    ctx.obj['LATEST'] = latest
    ctx.obj['TASKS'] = tasks


@todo.command()
@click.pass_context
def tasks(ctx):
    '''Display tasks'''
    if ctx.obj['TASKS']:
        click.echo('YOUR TASKS\n**********')
        # Iterate through all the tasks stored in the context
        for i, task in ctx.obj['TASKS'].items():
            click.echo('• ' + task + ' (ID: ' + i + ')')
        click.echo('')
    else:
        click.echo('No tasks yet! Use ADD to add one.\n')


@todo.command()
@click.pass_context
@click.option('-add', '--add_task', prompt='Enter task to add')
def add(ctx, add_task):
    '''Add a task'''
    if add_task:
        # Keys are always strings so the in-memory dict matches what we persist.
        new_id = str(ctx.obj['LATEST'])
        ctx.obj['TASKS'][new_id] = add_task
        click.echo('Added task "' + add_task + '" with ID ' + new_id)
        # Advance the monotonic counter; it is never rewound, so ids are unique.
        ctx.obj['LATEST'] += 1
        save_state(ctx.obj['LATEST'], ctx.obj['TASKS'])


@todo.command()
@click.pass_context
@click.option('-fin', '--fin_taskid', prompt='Enter ID of task to finish', type=int)
def done(ctx, fin_taskid):
    '''Delete a task by ID'''
    key = str(fin_taskid)
    # Find task with associated ID
    if key in ctx.obj['TASKS']:
        task = ctx.obj['TASKS'].pop(key)
        click.echo('Finished and removed task "' + task + '" with id ' + key)
        # Keep LATEST untouched: finishing a task must not advance the id counter.
        save_state(ctx.obj['LATEST'], ctx.obj['TASKS'])
    else:
        click.echo('Error: no task with id ' + str(fin_taskid))


if __name__ == '__main__':
    todo()
