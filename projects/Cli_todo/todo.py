import click
import os
from datetime import datetime

TODO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'todo.txt')
SEPARATOR = '```'
PRIORITIES = ('low', 'mid', 'high')
PRIORITY_ORDER = {'high': 0, 'mid': 1, 'low': 2}
STATUSES = ('pending', 'done')


def _parse_line(line):
    """Parse a single task line. Backward compatible with old 2-field format."""
    parts = line.rstrip('\n').split(SEPARATOR)
    if len(parts) < 2:
        return None
    task_id = parts[0]
    desc = parts[1]
    priority = parts[2] if len(parts) > 2 and parts[2] in PRIORITIES else 'mid'
    status = parts[3] if len(parts) > 3 and parts[3] in STATUSES else 'pending'
    created = parts[4] if len(parts) > 4 and parts[4] else ''
    completed = parts[5] if len(parts) > 5 else ''
    return {
        'id': task_id,
        'desc': desc,
        'priority': priority,
        'status': status,
        'created': created,
        'completed': completed,
    }


def _format_line(task):
    """Serialize a task dict back to a line."""
    return SEPARATOR.join([
        task['id'],
        task['desc'],
        task['priority'],
        task['status'],
        task['created'],
        task['completed'],
    ])


def _load():
    """Load tasks from todo.txt. Returns (next_id, tasks_dict)."""
    if not os.path.exists(TODO_FILE):
        return 0, {}
    with open(TODO_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if not lines:
        return 0, {}
    try:
        next_id = int(lines[0].strip())
    except (ValueError, IndexError):
        next_id = 0
    tasks = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        task = _parse_line(line)
        if task:
            tasks[task['id']] = task
    return next_id, tasks


def _save(next_id, tasks):
    """Write next_id + all tasks to todo.txt."""
    with open(TODO_FILE, 'w', encoding='utf-8') as f:
        f.write(str(next_id) + '\n')
        for task in tasks.values():
            f.write(_format_line(task) + '\n')


def _priority_label(p):
    """Return a colored priority indicator."""
    symbols = {'high': '!!!', 'mid': '!! ', 'low': '!  '}
    return symbols.get(p, '!! ')


def _print_task(task):
    pri = _priority_label(task['priority'])
    status_mark = '[x]' if task['status'] == 'done' else '[ ]'
    extra = ''
    if task['status'] == 'done' and task['completed']:
        extra = ' (finished ' + task['completed'] + ')'
    click.echo(f"  {status_mark} {pri}  {task['desc']}  (ID: {task['id']}){extra}")


def _sorted_tasks(task_list):
    """Sort: pending first, then by priority (high > mid > low), then by ID."""
    def sort_key(t):
        s = 0 if t['status'] == 'pending' else 1
        p = PRIORITY_ORDER.get(t['priority'], 1)
        return (s, p, int(t['id']))
    return sorted(task_list, key=sort_key)


# ── CLI ──────────────────────────────────────────────────────────────────────


@click.group()
@click.pass_context
def todo(ctx):
    '''Simple CLI Todo App'''
    ctx.ensure_object(dict)
    next_id, tasks = _load()
    ctx.obj['NEXT_ID'] = next_id
    ctx.obj['TASKS'] = tasks


@todo.command()
@click.pass_context
@click.option('-add', '--add_task', prompt='Enter task to add', help='Task description')
@click.option('-p', '--priority',
              type=click.Choice(PRIORITIES, case_sensitive=False),
              default='mid', show_default=True,
              help='Priority level')
def add(ctx, add_task, priority):
    '''Add a new task'''
    if not add_task.strip():
        click.echo('Task description cannot be empty.')
        return
    task_id = str(ctx.obj['NEXT_ID'])
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    task = {
        'id': task_id,
        'desc': add_task,
        'priority': priority,
        'status': 'pending',
        'created': now,
        'completed': '',
    }
    ctx.obj['TASKS'][task_id] = task
    ctx.obj['NEXT_ID'] = int(task_id) + 1
    _save(ctx.obj['NEXT_ID'], ctx.obj['TASKS'])
    click.echo(f'Added task "{add_task}" [{priority}] with ID {task_id}')


@todo.command()
@click.pass_context
@click.option('-s', '--status',
              type=click.Choice(['pending', 'done', 'all'], case_sensitive=False),
              default='pending', show_default=True,
              help='Filter by status')
@click.option('-p', '--priority',
              type=click.Choice(list(PRIORITIES) + ['all'], case_sensitive=False),
              default='all', show_default=True,
              help='Filter by priority')
def tasks(ctx, status, priority):
    '''Display tasks (with optional filters)'''
    all_tasks = list(ctx.obj['TASKS'].values())

    # Apply filters
    if status != 'all':
        all_tasks = [t for t in all_tasks if t['status'] == status]
    if priority != 'all':
        all_tasks = [t for t in all_tasks if t['priority'] == priority]

    if not all_tasks:
        click.echo('No matching tasks.')
        return

    sorted_tasks = _sorted_tasks(all_tasks)

    # Build header
    parts = []
    if status == 'all':
        parts.append('ALL')
    elif status == 'done':
        parts.append('COMPLETED')
    else:
        parts.append('PENDING')
    if priority != 'all':
        parts.append(f'[{priority.upper()}]')
    header = ' '.join(parts) + ' TASKS'

    click.echo(header)
    click.echo('*' * len(header))
    for t in sorted_tasks:
        _print_task(t)
    click.echo(f'\nTotal: {len(sorted_tasks)} task(s)')


@todo.command()
@click.pass_context
@click.option('-fin', '--fin_taskid', prompt='Enter ID of task to finish', type=int,
              help='ID of the task to mark as done')
def done(ctx, fin_taskid):
    '''Mark a task as done (keeps it in history)'''
    tid = str(fin_taskid)
    if tid not in ctx.obj['TASKS']:
        click.echo(f'Error: no task with ID {fin_taskid}')
        return
    task = ctx.obj['TASKS'][tid]
    if task['status'] == 'done':
        click.echo(f'Task {fin_taskid} ("{task["desc"]}") is already done.')
        return
    task['status'] = 'done'
    task['completed'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    _save(ctx.obj['NEXT_ID'], ctx.obj['TASKS'])
    click.echo(f'Finished task {fin_taskid}: "{task["desc"]}"')


@todo.command()
@click.pass_context
@click.option('-id', '--task_id', prompt='Enter ID of task to reopen', type=int,
              help='ID of the task to mark as pending again')
def undo(ctx, task_id):
    '''Reopen a completed task'''
    tid = str(task_id)
    if tid not in ctx.obj['TASKS']:
        click.echo(f'Error: no task with ID {task_id}')
        return
    task = ctx.obj['TASKS'][tid]
    if task['status'] == 'pending':
        click.echo(f'Task {task_id} ("{task["desc"]}") is already pending.')
        return
    task['status'] = 'pending'
    task['completed'] = ''
    _save(ctx.obj['NEXT_ID'], ctx.obj['TASKS'])
    click.echo(f'Reopened task {task_id}: "{task["desc"]}"')


@todo.command()
@click.pass_context
@click.option('-id', '--task_id', prompt='Enter ID of task to permanently remove', type=int,
              help='ID of the task to delete permanently')
def remove(ctx, task_id):
    '''Permanently delete a task'''
    tid = str(task_id)
    if tid not in ctx.obj['TASKS']:
        click.echo(f'Error: no task with ID {task_id}')
        return
    task = ctx.obj['TASKS'].pop(tid)
    _save(ctx.obj['NEXT_ID'], ctx.obj['TASKS'])
    click.echo(f'Removed task {task_id}: "{task["desc"]}"')


@todo.command()
@click.pass_context
@click.option('-p', '--priority',
              type=click.Choice(PRIORITIES, case_sensitive=False),
              default=None, help='New priority')
@click.option('-id', '--task_id', prompt='Enter task ID to edit', type=int,
              help='Task ID')
@click.option('-d', '--desc', default=None, help='New description')
def edit(ctx, task_id, priority, desc):
    '''Edit a task\'s description or priority'''
    tid = str(task_id)
    if tid not in ctx.obj['TASKS']:
        click.echo(f'Error: no task with ID {task_id}')
        return
    task = ctx.obj['TASKS'][tid]
    changed = []
    if desc is not None and desc.strip():
        old = task['desc']
        task['desc'] = desc.strip()
        changed.append(f'desc: "{old}" -> "{task["desc"]}"')
    if priority is not None:
        old = task['priority']
        task['priority'] = priority
        changed.append(f'priority: {old} -> {priority}')
    if not changed:
        click.echo('Nothing to change. Provide --desc or --priority.')
        return
    _save(ctx.obj['NEXT_ID'], ctx.obj['TASKS'])
    click.echo(f'Updated task {task_id}: ' + ', '.join(changed))


if __name__ == '__main__':
    todo()
