import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from click.testing import CliRunner

import todo as todo_mod


def run(data_file, *args, **kwargs):
    '''Invoke the CLI against an isolated data file.'''
    runner = CliRunner()
    return runner.invoke(todo_mod.todo, ['--file', str(data_file), *args],
                         **kwargs)


# --- new attribute persistence -------------------------------------------

def test_add_persists_priority_and_metadata(tmp_path):
    data = tmp_path / 'todo.txt'
    result = run(data, 'add', 'buy milk', '-p', 'high')
    assert result.exit_code == 0
    assert 'ID 0' in result.output

    # File on disk is JSON now.
    raw = json.loads(data.read_text())
    assert 'tasks' in raw

    store = todo_mod.load_store(str(data))
    assert len(store['tasks']) == 1
    task = store['tasks'][0]
    assert task['id'] == 0
    assert task['priority'] == 'high'
    assert task['status'] == 'pending'
    assert task['created'] is not None
    assert task['completed'] is None


def test_default_priority_is_medium(tmp_path):
    data = tmp_path / 'todo.txt'
    run(data, 'add', 'no flag task')
    store = todo_mod.load_store(str(data))
    assert store['tasks'][0]['priority'] == 'medium'


def test_add_prompts_when_no_argument(tmp_path):
    data = tmp_path / 'todo.txt'
    result = run(data, 'add', input='prompted task\n')
    assert result.exit_code == 0
    store = todo_mod.load_store(str(data))
    assert store['tasks'][0]['text'] == 'prompted task'


# --- completed tasks stay visible (not deleted) --------------------------

def test_done_keeps_task_in_history(tmp_path):
    data = tmp_path / 'todo.txt'
    run(data, 'add', 'finish report', '-p', 'medium')
    result = run(data, 'done', '0')
    assert result.exit_code == 0

    store = todo_mod.load_store(str(data))
    # Still present, just marked done.
    assert len(store['tasks']) == 1
    assert store['tasks'][0]['status'] == 'done'
    assert store['tasks'][0]['completed'] is not None


def test_done_task_hidden_by_default_but_visible_with_filters(tmp_path):
    data = tmp_path / 'todo.txt'
    run(data, 'add', 'archived task')
    run(data, 'done', '0')

    default_view = run(data, 'tasks')
    assert 'archived task' not in default_view.output

    all_view = run(data, 'tasks', '--all')
    assert 'archived task' in all_view.output
    assert 'done' in all_view.output

    done_view = run(data, 'tasks', '--status', 'done')
    assert 'archived task' in done_view.output


def test_done_prompts_when_no_id(tmp_path):
    data = tmp_path / 'todo.txt'
    run(data, 'add', 'prompt finish')
    result = run(data, 'done', input='0\n')
    assert result.exit_code == 0
    assert todo_mod.load_store(str(data))['tasks'][0]['status'] == 'done'


def test_done_unknown_id_reports_error(tmp_path):
    data = tmp_path / 'todo.txt'
    result = run(data, 'done', '99')
    assert 'no task with id 99' in result.output


def test_done_twice_is_reported(tmp_path):
    data = tmp_path / 'todo.txt'
    run(data, 'add', 'x')
    run(data, 'done', '0')
    result = run(data, 'done', '0')
    assert 'already done' in result.output


# --- filtered listing -----------------------------------------------------

def _seed_mixed(data):
    run(data, 'add', 'high task', '-p', 'high')
    run(data, 'add', 'medium task', '-p', 'medium')
    run(data, 'add', 'low task', '-p', 'low')


def test_filter_by_priority(tmp_path):
    data = tmp_path / 'todo.txt'
    _seed_mixed(data)
    result = run(data, 'tasks', '--priority', 'high')
    assert 'high task' in result.output
    assert 'low task' not in result.output
    assert 'medium task' not in result.output


def test_filter_by_status(tmp_path):
    data = tmp_path / 'todo.txt'
    _seed_mixed(data)
    run(data, 'done', '1')  # complete the medium task

    pending = run(data, 'tasks')
    assert 'high task' in pending.output
    assert 'low task' in pending.output
    assert 'medium task' not in pending.output

    done = run(data, 'tasks', '--status', 'done')
    assert 'medium task' in done.output
    assert 'high task' not in done.output


def test_listing_sorted_high_priority_first(tmp_path):
    data = tmp_path / 'todo.txt'
    _seed_mixed(data)
    result = run(data, 'tasks')
    pos_high = result.output.index('high task')
    pos_med = result.output.index('medium task')
    pos_low = result.output.index('low task')
    assert pos_high < pos_med < pos_low


def test_empty_store_message(tmp_path):
    data = tmp_path / 'todo.txt'
    result = run(data, 'tasks')
    assert 'No tasks yet' in result.output


# --- legacy todo.txt compatibility ---------------------------------------

def test_reads_legacy_line_format(tmp_path):
    data = tmp_path / 'todo.txt'
    data.write_text('2\n0```old task one\n1```old task two\n')

    result = run(data, 'tasks', '--all')
    assert result.exit_code == 0
    assert 'old task one' in result.output
    assert 'old task two' in result.output

    store = todo_mod.load_store(str(data))
    assert len(store['tasks']) == 2
    # Legacy tasks default to sane attributes.
    for task in store['tasks']:
        assert task['status'] == 'pending'
        assert task['priority'] == 'medium'


def test_legacy_upgrades_to_json_on_write(tmp_path):
    data = tmp_path / 'todo.txt'
    data.write_text('2\n0```old task\n1```another\n')

    result = run(data, 'add', 'brand new', '-p', 'low')
    assert result.exit_code == 0
    assert 'ID 2' in result.output  # counter continued from legacy file

    # File is now JSON and round-trips.
    raw = json.loads(data.read_text())
    assert 'tasks' in raw

    store = todo_mod.load_store(str(data))
    assert len(store['tasks']) == 3
    new_task = next(t for t in store['tasks'] if t['id'] == 2)
    assert new_task['text'] == 'brand new'
    assert new_task['priority'] == 'low'


def test_lone_zero_legacy_file_is_empty_store(tmp_path):
    # Mirrors the repo's current todo.txt which just contains "0".
    data = tmp_path / 'todo.txt'
    data.write_text('0\n')
    store = todo_mod.load_store(str(data))
    assert store == {'latest': 0, 'tasks': []}

    run(data, 'add', 'first', '-p', 'high')
    store = todo_mod.load_store(str(data))
    assert store['tasks'][0]['id'] == 0


def test_missing_file_is_empty_store(tmp_path):
    data = tmp_path / 'does_not_exist.txt'
    store = todo_mod.load_store(str(data))
    assert store == {'latest': 0, 'tasks': []}


def test_counter_recovers_from_bad_legacy_counter(tmp_path):
    # Counter says 0 but ids already go up to 5 -> next add must not collide.
    data = tmp_path / 'todo.txt'
    data.write_text('0\n5```stale\n')
    run(data, 'add', 'next', '-p', 'medium')
    store = todo_mod.load_store(str(data))
    ids = sorted(t['id'] for t in store['tasks'])
    assert ids == [5, 6]


if __name__ == '__main__':
    sys.exit(__import__('pytest').main([__file__, '-v']))
