import pytest
from django.urls import reverse
from rest_framework import status

from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_register_creates_unverified_user(api_client):
    url = reverse("users:register")
    payload = {
        "email": "flash@example.com",
        "password": "S3cure!Passw0rd",
        "password_confirm": "S3cure!Passw0rd",
        "display_name": "Flash",
    }
    response = api_client.post(url, payload)

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email="flash@example.com")
    assert user.is_email_verified is False
    assert user.check_password("S3cure!Passw0rd")
    assert response.data["email"] == "flash@example.com"
    assert "password" not in response.data


def test_register_rejects_duplicate_email(api_client):
    User.objects.create_user(email="dup@example.com", password="Whatever123!", display_name="Existing")
    url = reverse("users:register")

    response = api_client.post(url, {
        "email": "dup@example.com",
        "password": "AnotherPass123!",
        "password_confirm": "AnotherPass123!",
        "display_name": "New",
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_register_rejects_password_mismatch(api_client):
    url = reverse("users:register")

    response = api_client.post(url, {
        "email": "mismatch@example.com",
        "password": "Password123!",
        "password_confirm": "Different123!",
        "display_name": "Someone",
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert User.objects.filter(email="mismatch@example.com").exists() is False


def test_register_rejects_weak_password(api_client):
    url = reverse("users:register")

    response = api_client.post(url, {
        "email": "weak@example.com",
        "password": "password",
        "password_confirm": "password",
        "display_name": "Weak",
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_register_sends_verification_email(api_client, mailoutbox):
    url = reverse("users:register")

    api_client.post(url, {
        "email": "verify@example.com",
        "password": "GoodPassword123!",
        "password_confirm": "GoodPassword123!",
        "display_name": "Verifier",
    })

    assert len(mailoutbox) == 1
    assert "verify" in mailoutbox[0].subject.lower()
    assert "verify@example.com" in mailoutbox[0].to
