"""Command-line interface for the Simple CLI Todo App.

This module is intentionally thin: it only wires up the ``add`` / ``tasks`` /
``done`` commands and prints output. All parsing, persistence and task-ID logic
lives in :mod:`todo_store`, so the data format can evolve without touching the
commands (and vice versa).
"""

import click

from todo_store import TodoStore


@click.group()
@click.pass_context
def todo(ctx):
    '''Simple CLI Todo App'''
    ctx.ensure_object(dict)
    # Load the list once; commands read/mutate this shared store.
    ctx.obj['STORE'] = TodoStore.load()


@todo.command()
@click.pass_context
def tasks(ctx):
    '''Display tasks'''
    store = ctx.obj['STORE']
    if store.tasks:
        click.echo('YOUR TASKS\n**********')
        for i, task in store.tasks.items():
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
        store = ctx.obj['STORE']
        task_id = store.add(add_task)
        click.echo('Added task "' + add_task + '" with ID ' + task_id)
        store.save()


@todo.command()
@click.pass_context
@click.option('-fin', '--fin_taskid', prompt='Enter ID of task to finish', type=int)
def done(ctx, fin_taskid):
    '''Delete a task by ID'''
    store = ctx.obj['STORE']
    task = store.remove(fin_taskid)
    if task is not None:
        click.echo('Finished and removed task "' + task + '" with id ' + str(fin_taskid))
        store.save()
    else:
        click.echo('Error: no task with id ' + str(fin_taskid))


if __name__ == '__main__':
    todo()
