#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Windows consoles default to a narrow codepage (e.g. cp1250), which can't
# encode the emoji used in views.py's print() logging and crashes with
# UnicodeEncodeError. Force UTF-8 before anything else (e.g. colorama) wraps
# stdout/stderr.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trainme.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
