import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from apps.users.models import User

pytestmark = pytest.mark.django_db

RAW_PASSWORD = "CorrectHorse123!"


@pytest.fixture
def user():
    return User.objects.create_user(email="login@example.com", password=RAW_PASSWORD, display_name="Login Test")


def test_login_returns_access_token_and_sets_refresh_cookie(api_client, user):
    response = api_client.post(reverse("users:login"), {"email": user.email, "password": RAW_PASSWORD})

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" not in response.data  # the refresh token must never appear in the response body
    assert response.data["user"]["email"] == user.email
    assert settings.SIMPLE_JWT["REFRESH_COOKIE_NAME"] in response.cookies

    cookie = response.cookies[settings.SIMPLE_JWT["REFRESH_COOKIE_NAME"]]
    assert cookie["httponly"] is True


def test_login_rejects_wrong_password(api_client, user):
    response = api_client.post(reverse("users:login"), {"email": user.email, "password": "WrongPassword!"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_rejects_unknown_email(api_client):
    response = api_client.post(reverse("users:login"), {"email": "ghost@example.com", "password": "whatever"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_requires_authentication(api_client):
    response = api_client.get(reverse("users:me"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_returns_current_user_after_login(api_client, user):
    login_response = api_client.post(reverse("users:login"), {"email": user.email, "password": RAW_PASSWORD})
    assert login_response.status_code == status.HTTP_200_OK, (
        f"Login failed unexpectedly: {login_response.status_code} {login_response.data}"
    )
    access = login_response.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = api_client.get(reverse("users:me"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email


def test_refresh_issues_a_new_access_token(api_client, user):
    api_client.post(reverse("users:login"), {"email": user.email, "password": RAW_PASSWORD})

    response = api_client.post(reverse("users:refresh"))

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data


def test_refresh_without_cookie_is_unauthorized(api_client):
    response = api_client.post(reverse("users:refresh"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_blacklists_the_refresh_token(api_client, user):
    login_response = api_client.post(reverse("users:login"), {"email": user.email, "password": RAW_PASSWORD})
    assert login_response.status_code == status.HTTP_200_OK, (
        f"Login failed unexpectedly: {login_response.status_code} {login_response.data}"
    )
    access = login_response.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    logout_response = api_client.post(reverse("users:logout"))
    assert logout_response.status_code == status.HTTP_200_OK

    # the refresh cookie that was valid before logout must be rejected now
    post_logout_refresh = api_client.post(reverse("users:refresh"))
    assert post_logout_refresh.status_code == status.HTTP_401_UNAUTHORIZED
