import pytest
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

from apps.users.models import User
from apps.users.tokens import email_verification_token

pytestmark = pytest.mark.django_db


@pytest.fixture
def unverified_user():
    return User.objects.create_user(
        email="pending@example.com", password="StrongPass123!", display_name="Pending"
    )


def test_verify_email_with_valid_token(api_client, unverified_user):
    uid = urlsafe_base64_encode(force_bytes(unverified_user.pk))
    token = email_verification_token.make_token(unverified_user)

    response = api_client.post(reverse("users:verify-email"), {"uid": uid, "token": token})

    assert response.status_code == status.HTTP_200_OK
    unverified_user.refresh_from_db()
    assert unverified_user.is_email_verified is True


def test_verify_email_with_invalid_token(api_client, unverified_user):
    uid = urlsafe_base64_encode(force_bytes(unverified_user.pk))

    response = api_client.post(reverse("users:verify-email"), {"uid": uid, "token": "not-a-real-token"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    unverified_user.refresh_from_db()
    assert unverified_user.is_email_verified is False


def test_verify_email_with_malformed_uid(api_client):
    response = api_client.post(reverse("users:verify-email"), {"uid": "not-base64!!", "token": "whatever"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_reposting_an_already_verified_link_is_idempotent(api_client, unverified_user):
    uid = urlsafe_base64_encode(force_bytes(unverified_user.pk))
    token = email_verification_token.make_token(unverified_user)

    first = api_client.post(reverse("users:verify-email"), {"uid": uid, "token": token})
    assert first.status_code == status.HTTP_200_OK

    # Same token, now stale because `is_email_verified` (part of the hash)
    # has flipped — but re-posting still succeeds quietly instead of erroring.
    second = api_client.post(reverse("users:verify-email"), {"uid": uid, "token": token})
    assert second.status_code == status.HTTP_200_OK


def test_resend_verification_is_generic_for_unknown_email(api_client):
    response = api_client.post(reverse("users:resend-verification"), {"email": "nobody@example.com"})
    assert response.status_code == status.HTTP_200_OK


def test_resend_verification_sends_email_for_unverified_user(api_client, unverified_user, mailoutbox):
    response = api_client.post(reverse("users:resend-verification"), {"email": unverified_user.email})
    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 1


def test_resend_verification_is_a_noop_for_already_verified_user(api_client, unverified_user, mailoutbox):
    unverified_user.is_email_verified = True
    unverified_user.save(update_fields=["is_email_verified"])

    response = api_client.post(reverse("users:resend-verification"), {"email": unverified_user.email})

    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 0
