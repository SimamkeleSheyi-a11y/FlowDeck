"""
Dedicated throttle tests. Rates are patched directly onto
ScopedRateThrottle.THROTTLE_RATES rather than via
@override_settings(REST_FRAMEWORK=...).

Why: DRF's `api_settings` object does refresh when the REST_FRAMEWORK
setting changes (it's connected to Django's `setting_changed` test signal
for exactly that purpose) — but rest_framework.throttling.SimpleRateThrottle
(the base class ScopedRateThrottle extends) does:

    THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES

as a plain class attribute, evaluated ONCE at import time. Reassigning the
module-level `api_settings` object later (which is what the signal handler
does) does not retroactively update that already-bound class attribute —
so @override_settings alone silently has no effect on the rate a throttle
actually enforces. This is what made these three tests fail. Patching
ScopedRateThrottle.THROTTLE_RATES directly targets the exact mapping
get_rate() reads at request time, sidestepping the staleness entirely.
"""
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle

from apps.users.models import User

pytestmark = pytest.mark.django_db


def _patched_rates(scope: str, rate: str) -> dict:
    """Full THROTTLE_RATES mapping (every scope, from the relaxed
    test-suite-wide settings) with exactly one scope re-tightened — a
    dict, not a partial override, since patch.object replaces the whole
    attribute rather than merging into it."""
    return {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], scope: rate}


def test_login_is_throttled_after_the_configured_rate(api_client):
    cache.clear()
    user = User.objects.create_user(
        email="throttle@example.com", password="ThrottlePass123!", display_name="Throttle Test"
    )

    with patch.object(ScopedRateThrottle, "THROTTLE_RATES", _patched_rates("login", "3/min")):
        # The wrong password is deliberate — only the *rate* is under test,
        # not whether the credentials are correct, and the throttle engages
        # before authentication is even checked.
        for _ in range(3):
            response = api_client.post(reverse("users:login"), {"email": user.email, "password": "WrongPassword!"})
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS

        blocked = api_client.post(reverse("users:login"), {"email": user.email, "password": "WrongPassword!"})
        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    cache.clear()


def test_register_is_throttled_after_the_configured_rate(api_client):
    cache.clear()

    with patch.object(ScopedRateThrottle, "THROTTLE_RATES", _patched_rates("register", "2/min")):
        for i in range(2):
            response = api_client.post(
                reverse("users:register"),
                {
                    "email": f"throttlereg{i}@example.com",
                    "password": "ThrottleRegPass123!",
                    "password_confirm": "ThrottleRegPass123!",
                    "display_name": "Reg Throttle",
                },
            )
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS

        blocked = api_client.post(
            reverse("users:register"),
            {
                "email": "throttlereg-blocked@example.com",
                "password": "ThrottleRegPass123!",
                "password_confirm": "ThrottleRegPass123!",
                "display_name": "Reg Throttle",
            },
        )
        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    cache.clear()


def test_forgot_password_is_throttled_after_the_configured_rate(api_client):
    cache.clear()

    with patch.object(ScopedRateThrottle, "THROTTLE_RATES", _patched_rates("password_reset", "2/min")):
        for _ in range(2):
            response = api_client.post(reverse("users:password-forgot"), {"email": "nobody@example.com"})
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS

        blocked = api_client.post(reverse("users:password-forgot"), {"email": "nobody@example.com"})
        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    cache.clear()


def test_production_settings_keep_the_real_login_throttle_rate():
    """
    Not a request-level test — imports config.settings (production, NOT
    config.settings_test) as a plain module and checks its throttle rate
    directly, confirming the fix above didn't quietly loosen what actually
    ships. Production keeps the real 10/minute login limit regardless of
    what the test settings module relaxes for its own runs, and regardless
    of the THROTTLE_RATES patching the tests above do (patch.object always
    restores the original value on exit, and this test doesn't even go
    through that code path — it reads the settings module directly).
    """
    from config import settings as production_settings

    assert production_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"] == "10/minute"
