"""Regression tests for projects/Cli_todo/todo.py"""

import os
import sys
import subprocess
import tempfile
import shutil

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'projects', 'Cli_todo', 'todo.py')
DATA_FILE = os.path.join(os.path.dirname(SCRIPT), 'todo.txt')


def run(args, cwd=None, input_text=None):
    """Run the CLI and return (exit_code, stdout)."""
    cmd = [sys.executable, SCRIPT] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                            input=input_text)
    return result.returncode, result.stdout + result.stderr


def cleanup():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)


def write_data(content):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        f.write(content)


def read_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return f.read()


# ── helpers ──────────────────────────────────────────────────────────────────
passed = 0
failed = 0


def check(name, condition, detail=''):
    global passed, failed
    if condition:
        print(f'  PASS  {name}')
        passed += 1
    else:
        print(f'  FAIL  {name}  {detail}')
        failed += 1


# ── tests ────────────────────────────────────────────────────────────────────

print('\n=== 1. Missing data file (first run) ===')
cleanup()
rc, out = run(['tasks'])
check('exit 0 when no file', rc == 0, f'rc={rc}')
check('no-tasks message', 'No tasks yet' in out, out)

print('\n=== 2. Add a task (default cwd) ===')
cleanup()
rc, out = run(['add', '-add', 'Buy milk'])
check('add exit 0', rc == 0, f'rc={rc}')
check('add output', 'Added task "Buy milk" with ID 0' in out, out)
check('data file created', os.path.exists(DATA_FILE))

print('\n=== 3. Add + list tasks ===')
rc, out = run(['tasks'])
check('tasks exit 0', rc == 0, f'rc={rc}')
check('task shown', 'Buy milk' in out and 'ID: 0' in out, out)

print('\n=== 4. Add second task, then finish first ===')
rc, out = run(['add', '-add', 'Walk dog'])
check('add 2nd exit 0', rc == 0, f'rc={rc}')
check('second task ID is 1', 'ID 1' in out, out)

rc, out = run(['done', '-fin', '0'])
check('done exit 0', rc == 0, f'rc={rc}')
check('done output', 'Finished and removed' in out, out)

rc, out = run(['tasks'])
check('task 0 gone', 'Buy milk' not in out, out)
check('task 1 still there', 'Walk dog' in out, out)

print('\n=== 5. ID monotonicity after delete+add ===')
rc, out = run(['add', '-add', 'Read book'])
check('new task gets ID 2 (not 0)', 'ID 2' in out, out)
raw = read_data()
check('counter in file >= 3', int(raw.splitlines()[0]) >= 3, raw.splitlines()[0])

print('\n=== 6. Finish non-existent ID ===')
rc, out = run(['done', '-fin', '999'])
check('no crash on bad id', rc == 0, f'rc={rc}')
check('error message', 'no task with id 999' in out.lower() or 'error' in out.lower(), out)

print('\n=== 7. Run from a different cwd ===')
cleanup()
with tempfile.TemporaryDirectory() as tmpdir:
    rc, out = run(['add', '-add', 'From other dir'], cwd=tmpdir)
    check('add from other cwd exit 0', rc == 0, f'rc={rc}')
    check('data file is next to script', os.path.exists(DATA_FILE))
    rc, out = run(['tasks'], cwd=tmpdir)
    check('tasks visible from other cwd', 'From other dir' in out, out)

print('\n=== 8. Empty data file ===')
cleanup()
write_data('')
rc, out = run(['tasks'])
check('empty file: no crash', rc == 0, f'rc={rc}')
check('empty file: no tasks msg', 'No tasks yet' in out, out)

print('\n=== 9. Corrupt header line ===')
write_data('not_a_number\n')
rc, out = run(['tasks'])
check('corrupt header: no crash', rc == 0, f'rc={rc}')
check('corrupt header: warning', 'warning' in out.lower() or 'corrupt' in out.lower() or 'No tasks' in out, out)

print('\n=== 10. Corrupt task line (no separator) ===')
write_data('5\nthis line has no tab separator\n')
rc, out = run(['tasks'])
check('corrupt line: no crash', rc == 0, f'rc={rc}')
check('corrupt line: warning emitted', 'warning' in out.lower() or 'skipping' in out.lower() or 'malformed' in out.lower(), out)

print('\n=== 11. Special characters in task text ===')
cleanup()
special = 'Task with "quotes" & <angle> and pipe|chars'
rc, out = run(['add', '-add', special])
check('special chars: add ok', rc == 0, f'rc={rc}')
rc, out = run(['tasks'])
check('special chars: roundtrip', special in out, out)

# Task with tab and newline characters should be sanitised
rc, out = run(['add', '-add', 'tabs\there\nand newlines'])
check('tab/newline: add ok', rc == 0, f'rc={rc}')
rc, out = run(['tasks'])
check('tab/newline: data file still parseable', rc == 0, f'rc={rc}')

print('\n=== 12. Finish all tasks then add again ===')
cleanup()
run(['add', '-add', 'Only task'])
run(['done', '-fin', '0'])
rc, out = run(['add', '-add', 'After empty'])
check('add after empty: ok', rc == 0, f'rc={rc}')
# New task should get ID >= 1 (monotonic), not 0
check('add after empty: ID not 0 again',
      'ID 0' not in out or 'ID 1' in out, out)
raw = read_data()
lines = raw.strip().splitlines()
check('file has 2 lines (counter + 1 task)', len(lines) == 2, f'lines={len(lines)} raw={raw!r}')

print('\n=== 13. Delete all tasks resets gracefully ===')
cleanup()
run(['add', '-add', 'X'])
run(['done', '-fin', '0'])
rc, out = run(['tasks'])
check('all done: no tasks msg', 'No tasks yet' in out, out)

# ── summary ──────────────────────────────────────────────────────────────────
cleanup()
print(f'\n{"="*50}')
print(f'Results: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
