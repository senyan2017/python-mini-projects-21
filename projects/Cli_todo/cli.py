"""CLI layer for the todo app.

Defines the ``todo`` command group and its subcommands (add, tasks, done).
All persistence is delegated to :class:`store.TodoStore`.
"""

import click

from store import TodoStore

# Default data-file path, resolved relative to the script directory so the
# tool works regardless of the caller's cwd.
import os as _os

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_DEFAULT_PATH = _os.path.join(_HERE, "todo.txt")


@click.group()
@click.pass_context
def todo(ctx):
    """Simple CLI Todo App"""
    ctx.ensure_object(dict)
    ctx.obj["store"] = TodoStore(_DEFAULT_PATH)


@todo.command()
@click.pass_context
def tasks(ctx):
    """Display tasks"""
    store = ctx.obj["store"]
    items = store.list_tasks()
    if items:
        click.echo("YOUR TASKS")
        click.echo("**********")
        for id_str, text in items:
            click.echo(f"\u2022 {text} (ID: {id_str})")
        click.echo("")
    else:
        click.echo("No tasks yet! Use ADD to add one.\n")


@todo.command()
@click.pass_context
@click.option("-add", "--add_task", prompt="Enter task to add")
def add(ctx, add_task):
    """Add a task"""
    if add_task:
        store = ctx.obj["store"]
        task_id = store.add_task(add_task)
        click.echo(f'Added task "{add_task}" with ID {task_id}')


@todo.command()
@click.pass_context
@click.option("-fin", "--fin_taskid", prompt="Enter ID of task to finish", type=int)
def done(ctx, fin_taskid):
    """Delete a task by ID"""
    store = ctx.obj["store"]
    text = store.complete_task(fin_taskid)
    if text is not None:
        click.echo(f'Finished and removed task "{text}" with id {fin_taskid}')
    else:
        click.echo(f"Error: no task with id {fin_taskid}")


if __name__ == "__main__":
    todo()
