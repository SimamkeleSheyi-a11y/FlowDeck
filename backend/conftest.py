import sys

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

# Same guard as manage.py — pytest doesn't go through manage.py at all, so
# without this an unsupported interpreter (3.13+) would only surface as a
# confusing failure somewhere inside Django/DRF's own import chain instead
# of one clear message up front. See manage.py and README.md.
_MIN_PYTHON = (3, 10)
_MAX_PYTHON_EXCLUSIVE = (3, 13)
if not (_MIN_PYTHON <= sys.version_info[:2] < _MAX_PYTHON_EXCLUSIVE):
    sys.exit(
        f"FlowDeck backend requires Python 3.10-3.12 for Django 5.0.x "
        f"(detected {sys.version_info.major}.{sys.version_info.minor}). "
        "See README.md."
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def _clear_cache():
    """
    DRF's throttle counters (and anything else cache-backed) live in
    Django's cache, not the database — pytest-django's per-test transaction
    rollback has no effect on it. Without clearing it between tests, a
    request count from one test can carry into the next and make an
    unrelated test flaky depending on run order. Autouse so every test gets
    a clean slate without needing to remember to ask for it.
    """
    cache.clear()
    yield
    cache.clear()
