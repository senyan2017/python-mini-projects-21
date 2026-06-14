#!/usr/bin/env python
"""Entry point for the CLI todo app.

Delegates to ``cli.todo`` (command definitions) and ``store`` (data layer).
Run with: ``python todo.py [command]``
"""

from cli import todo

if __name__ == "__main__":
    todo()
