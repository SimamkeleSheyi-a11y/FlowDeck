import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from apps.users.models import User

pytestmark = pytest.mark.django_db

RAW_PASSWORD = "ProfilePass123!"


@pytest.fixture
def authed_client(api_client):
    """
    Force-authenticates rather than going through the real login endpoint —
    these tests exercise profile/avatar behavior, not login itself, and
    doing a real login per test was contributing to the login endpoint's
    10/minute throttle being tripped once the full suite ran together.
    """
    user = User.objects.create_user(email="profile@example.com", password=RAW_PASSWORD, display_name="Profile Test")
    api_client.force_authenticate(user=user)
    return api_client, user


def test_get_me_returns_expected_fields(authed_client):
    client, user = authed_client
    response = client.get(reverse("users:me"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["display_name"] == user.display_name
    assert response.data["is_email_verified"] is False
    assert "avatar" in response.data
    assert "id" in response.data


def test_patch_me_updates_display_name_and_bio(authed_client):
    client, _ = authed_client
    response = client.patch(reverse("users:me"), {"display_name": "New Name", "bio": "Building FlowDeck."})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["display_name"] == "New Name"
    assert response.data["bio"] == "Building FlowDeck."


def test_patch_me_rejects_blank_display_name(authed_client):
    client, _ = authed_client
    response = client.patch(reverse("users:me"), {"display_name": "   "})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_patch_me_cannot_change_email(authed_client):
    client, user = authed_client
    client.patch(reverse("users:me"), {"email": "changed@example.com"})
    user.refresh_from_db()
    assert user.email == "profile@example.com"  # email is read-only via this endpoint


def _tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def test_avatar_upload_accepts_valid_image(authed_client):
    client, _ = authed_client
    upload = SimpleUploadedFile("avatar.png", _tiny_png_bytes(), content_type="image/png")

    response = client.post(reverse("users:me-avatar"), {"avatar": upload}, format="multipart")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["avatar"] is not None


def test_avatar_upload_rejects_oversized_file(authed_client):
    client, _ = authed_client
    oversized = SimpleUploadedFile("avatar.png", b"0" * (3 * 1024 * 1024), content_type="image/png")

    response = client.post(reverse("users:me-avatar"), {"avatar": oversized}, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_avatar_upload_rejects_wrong_content_type(authed_client):
    client, _ = authed_client
    bad_file = SimpleUploadedFile("notes.txt", b"just text", content_type="text/plain")

    response = client.post(reverse("users:me-avatar"), {"avatar": bad_file}, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_avatar_delete_clears_avatar(authed_client):
    client, user = authed_client
    upload = SimpleUploadedFile("avatar.png", _tiny_png_bytes(), content_type="image/png")
    client.post(reverse("users:me-avatar"), {"avatar": upload}, format="multipart")

    response = client.delete(reverse("users:me-avatar"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["avatar"] is None
