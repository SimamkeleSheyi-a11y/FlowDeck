import pytest
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

from apps.users.models import User

pytestmark = pytest.mark.django_db

OLD_PASSWORD = "OldPassword123!"


@pytest.fixture
def user():
    return User.objects.create_user(email="reset@example.com", password=OLD_PASSWORD, display_name="Resetter")


def test_forgot_password_returns_generic_response_for_unknown_email(api_client):
    response = api_client.post(reverse("users:password-forgot"), {"email": "nobody@example.com"})
    assert response.status_code == status.HTTP_200_OK  # never reveals whether the email exists


def test_forgot_password_sends_email_for_known_user(api_client, user, mailoutbox):
    response = api_client.post(reverse("users:password-forgot"), {"email": user.email})
    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 1
    assert "reset" in mailoutbox[0].subject.lower()


def test_reset_password_with_valid_token(api_client, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = api_client.post(reverse("users:password-reset"), {
        "uid": uid,
        "token": token,
        "new_password": "BrandNewPass123!",
        "new_password_confirm": "BrandNewPass123!",
    })

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("BrandNewPass123!")


def test_reset_password_token_is_stale_after_first_use(api_client, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    api_client.post(reverse("users:password-reset"), {
        "uid": uid, "token": token,
        "new_password": "FirstReset123!", "new_password_confirm": "FirstReset123!",
    })

    # same token — now stale because the password (part of the token hash)
    # has already changed once
    second = api_client.post(reverse("users:password-reset"), {
        "uid": uid, "token": token,
        "new_password": "SecondReset123!", "new_password_confirm": "SecondReset123!",
    })

    assert second.status_code == status.HTTP_400_BAD_REQUEST


def test_reset_password_rejects_mismatched_confirmation(api_client, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = api_client.post(reverse("users:password-reset"), {
        "uid": uid, "token": token,
        "new_password": "SomePassword123!", "new_password_confirm": "DifferentPassword123!",
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_change_password_requires_authentication(api_client):
    response = api_client.post(reverse("users:password-change"), {
        "old_password": OLD_PASSWORD, "new_password": "New12345!", "new_password_confirm": "New12345!",
    })
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_change_password_requires_correct_old_password(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse("users:password-change"), {
        "old_password": "WrongOldPassword!",
        "new_password": "NewPassword123!",
        "new_password_confirm": "NewPassword123!",
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_change_password_succeeds_and_forces_relogin(api_client, user):
    # Real login is required here (not force_authenticate) — this test
    # specifically verifies that the refresh *cookie* issued at login stops
    # working after a password change, which needs a genuine cookie to
    # invalidate in the first place.
    login_response = api_client.post(reverse("users:login"), {"email": user.email, "password": OLD_PASSWORD})
    assert login_response.status_code == status.HTTP_200_OK, (
        f"Login failed unexpectedly: {login_response.status_code} {login_response.data}"
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

    response = api_client.post(reverse("users:password-change"), {
        "old_password": OLD_PASSWORD,
        "new_password": "NewPassword123!",
        "new_password_confirm": "NewPassword123!",
    })

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("NewPassword123!")

    # the refresh cookie issued before the password change must no longer work
    refresh_response = api_client.post(reverse("users:refresh"))
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
