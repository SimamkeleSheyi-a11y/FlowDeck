"""
Settings for running the test suite — imports everything from the real
config.settings and overrides exactly two things. This is NOT used by
manage.py (which still defaults to config.settings for check/makemigrations/
migrate/runserver) — only pytest is pointed at this module, via
DJANGO_SETTINGS_MODULE in pytest.ini.

What's overridden and why:

1. Throttle rates are RAISED, not disabled. Production keeps its real
   10/minute login throttle etc. (config.settings is untouched) — but a
   full test run legitimately makes more real requests to auth endpoints in
   a short window than a production rate limit is meant to allow for actual
   users, across:
     - apps/users/tests/test_login_logout.py (tests login/logout/refresh
       mechanics directly — has to hit the real endpoint)
     - apps/users/tests/test_password_reset_change.py's
       test_change_password_succeeds_and_forces_relogin (needs a genuine
       refresh cookie to verify it gets invalidated)
     - the dedicated throttle tests below, which deliberately re-lower a
       single rate with @override_settings for one test at a time
   Every other test that previously called the real login endpoint now uses
   APIClient.force_authenticate() instead (see the _authenticate() helpers
   across apps/workspaces/tests/ and apps/users/tests/test_profile.py) —
   that was the primary fix. This settings module is the second layer:
   headroom for the real-login tests that legitimately remain, not a
   workaround for tests that shouldn't have been hitting login at all.

2. SECRET_KEY is a real random 48-byte value (not the "insecure-dev-key-
   change-me" placeholder default) so `manage.py check` doesn't flag it —
   generated once with `secrets.token_urlsafe(48)`. This is a TEST-ONLY key;
   production must keep setting SECRET_KEY via its own environment variable
   as already configured in config/settings.py.
"""
from .settings import *  # noqa: F401,F403

SECRET_KEY = "C21HfAX9QZJ63femz9c6qJhrTWBMVesPAXlo9wIsP0oiupZ6Gk93APOiJGBhATAe"

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "register": "1000/min",
        "login": "1000/min",
        "password_reset": "1000/min",
        "resend_verification": "1000/min",
    },
}
