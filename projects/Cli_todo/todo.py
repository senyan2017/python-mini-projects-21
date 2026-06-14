import json
import os
from datetime import datetime

import click

DEFAULT_FILE = './todo.txt'
PRIORITIES = ('low', 'medium', 'high')
PRIORITY_RANK = {'high': 0, 'medium': 1, 'low': 2}
STATUSES = ('pending', 'done')
LEGACY_SEP = '```'


def _now():
    '''Current timestamp, second precision, ISO format.'''
    return datetime.now().isoformat(timespec='seconds')


def _normalize_task(raw):
    '''Coerce a raw task dict into the canonical shape with sane defaults.'''
    priority = raw.get('priority', 'medium')
    if priority not in PRIORITIES:
        priority = 'medium'
    status = raw.get('status', 'pending')
    if status not in STATUSES:
        status = 'pending'
    return {
        'id': int(raw['id']),
        'text': str(raw.get('text', '')),
        'status': status,
        'priority': priority,
        'created': raw.get('created'),
        'completed': raw.get('completed'),
    }


def _parse_legacy(content):
    '''Parse the original line-based format.

    Line 1 is the latest-id counter; each remaining line is "<id>```<text>".
    Missing attributes default to pending / medium so old data stays usable.
    '''
    lines = [ln.rstrip('\n') for ln in content.splitlines()]
    lines = [ln for ln in lines if ln != '']
    if not lines:
        return {'latest': 0, 'tasks': []}
    try:
        latest = int(lines[0])
    except ValueError:
        latest = 0
    tasks = []
    for line in lines[1:]:
        if LEGACY_SEP not in line:
            continue
        raw_id, text = line.split(LEGACY_SEP, 1)
        try:
            task_id = int(raw_id)
        except ValueError:
            continue
        tasks.append(_normalize_task({
            'id': task_id,
            'text': text,
            'status': 'pending',
            'priority': 'medium',
            'created': None,
            'completed': None,
        }))
    return {'latest': latest, 'tasks': tasks}


def _ensure_counter(store):
    '''Make sure the id counter is ahead of every existing task id.'''
    max_id = max((t['id'] for t in store['tasks']), default=-1)
    if store['latest'] <= max_id:
        store['latest'] = max_id + 1
    return store


def load_store(path):
    '''Load tasks from PATH, transparently migrating the legacy format.

    Returns a dict: {'latest': int, 'tasks': [task, ...]}.
    A missing or empty file yields an empty store. New data is JSON; old
    line-based files (including a lone "0") are detected and parsed instead.
    '''
    if not os.path.exists(path):
        return {'latest': 0, 'tasks': []}
    with open(path) as f:
        content = f.read()
    if content.strip() == '':
        return {'latest': 0, 'tasks': []}
    try:
        data = json.loads(content)
    except (ValueError, json.JSONDecodeError):
        data = None
    if isinstance(data, dict) and 'tasks' in data:
        store = {
            'latest': int(data.get('latest', 0)),
            'tasks': [_normalize_task(t) for t in data['tasks']],
        }
    else:
        # Not our JSON shape -> treat as the original line-based file.
        store = _parse_legacy(content)
    return _ensure_counter(store)


def save_store(path, store):
    '''Persist the store as JSON.'''
    with open(path, 'w') as f:
        json.dump(store, f, indent=2)
        f.write('\n')


def _fmt_task(task):
    '''Render a single task for display.'''
    label = '[' + task['priority'].upper() + ']'
    line = u'\u2022 ' + label + ' ' + task['text'] + ' (ID: ' + str(task['id']) + ')'
    if task['status'] == 'done':
        when = (task['completed'] or '')[:10]
        line += ' \u2014 done' + ((' @ ' + when) if when else '')
    else:
        line += ' \u2014 pending'
    return line


@click.group()
@click.option('-f', '--file', 'file', default=DEFAULT_FILE,
              help='Path to the todo data file.')
@click.pass_context
def todo(ctx, file):
    '''Simple CLI Todo App'''
    ctx.ensure_object(dict)
    ctx.obj['FILE'] = file
    ctx.obj['STORE'] = load_store(file)


@todo.command()
@click.option('-a', '--all', 'show_all', is_flag=True,
              help='Include completed tasks.')
@click.option('-s', '--status', type=click.Choice(STATUSES), default=None,
              help='Only show tasks with this status.')
@click.option('-p', '--priority', type=click.Choice(PRIORITIES), default=None,
              help='Only show tasks with this priority.')
@click.pass_context
def tasks(ctx, show_all, status, priority):
    '''Display tasks (pending by default; filter by status/priority).'''
    items = list(ctx.obj['STORE']['tasks'])

    if status is not None:
        items = [t for t in items if t['status'] == status]
    elif not show_all:
        items = [t for t in items if t['status'] == 'pending']

    if priority is not None:
        items = [t for t in items if t['priority'] == priority]

    items.sort(key=lambda t: (PRIORITY_RANK[t['priority']], t['id']))

    if items:
        click.echo('YOUR TASKS\n**********')
        for task in items:
            click.echo(_fmt_task(task))
        click.echo('')
    elif ctx.obj['STORE']['tasks']:
        click.echo('No tasks match that filter.\n')
    else:
        click.echo('No tasks yet! Use ADD to add one.\n')


@todo.command()
@click.argument('task', required=False)
@click.option('-p', '--priority', type=click.Choice(PRIORITIES), default='medium',
              help='Task priority (default: medium).')
@click.pass_context
def add(ctx, task, priority):
    '''Add a task.'''
    if not task:
        task = click.prompt('Enter task to add')
    if not task:
        return
    store = ctx.obj['STORE']
    new_id = store['latest']
    store['tasks'].append(_normalize_task({
        'id': new_id,
        'text': task,
        'status': 'pending',
        'priority': priority,
        'created': _now(),
        'completed': None,
    }))
    store['latest'] = new_id + 1
    save_store(ctx.obj['FILE'], store)
    click.echo('Added task "' + task + '" with ID ' + str(new_id) +
               ' [' + priority + ']')


@todo.command()
@click.argument('task_id', required=False, type=int)
@click.pass_context
def done(ctx, task_id):
    '''Mark a task as done by ID (kept in history, not deleted).'''
    if task_id is None:
        task_id = click.prompt('Enter ID of task to finish', type=int)
    store = ctx.obj['STORE']
    match = next((t for t in store['tasks'] if t['id'] == task_id), None)
    if match is None:
        click.echo('Error: no task with id ' + str(task_id))
        return
    if match['status'] == 'done':
        click.echo('Task "' + match['text'] + '" (id ' + str(task_id) +
                   ') is already done.')
        return
    match['status'] = 'done'
    match['completed'] = _now()
    save_store(ctx.obj['FILE'], store)
    click.echo('Finished task "' + match['text'] + '" with id ' + str(task_id))


if __name__ == '__main__':
    todo()
