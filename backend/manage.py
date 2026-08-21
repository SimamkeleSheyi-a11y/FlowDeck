#!/usr/bin/env python
"""FlowDeck backend management entrypoint."""
import os
import sys

# Django 5.0.x officially supports Python 3.10-3.12 only (3.13 support
# arrived in Django 5.1). Confirmed working locally on Python 3.12.10 — see
# README.md. Checked here, before Django is even imported, so running on an
# unsupported interpreter (e.g. 3.13 or 3.14) fails with one clear message
# instead of a confusing downstream import/compatibility error.
_MIN_PYTHON = (3, 10)
_MAX_PYTHON_EXCLUSIVE = (3, 13)
if not (_MIN_PYTHON <= sys.version_info[:2] < _MAX_PYTHON_EXCLUSIVE):
    sys.exit(
        f"FlowDeck backend requires Python 3.10-3.12 for Django 5.0.x "
        f"(detected {sys.version_info.major}.{sys.version_info.minor}). "
        "Django 5.0 does not support Python 3.13+. Use a supported "
        "interpreter (3.12 recommended, matching .python-version) or "
        "upgrade Django if you specifically need a newer Python — see "
        "README.md."
    )


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
