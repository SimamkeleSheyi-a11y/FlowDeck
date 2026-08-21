"""
Email-sending and security-adjacent helpers for the users app. Kept out of
views.py so views stay thin and this logic is independently reusable/testable.
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def _build_uid(user) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def send_verification_email(user) -> None:
    uid = _build_uid(user)
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"
    send_mail(
        subject="Verify your FlowDeck email",
        message=(
            f"Hi {user.display_name},\n\n"
            "Confirm your email address to finish setting up your FlowDeck account:\n"
            f"{link}\n\n"
            "If you didn't create this account, you can safely ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def send_password_reset_email(user) -> None:
    uid = _build_uid(user)
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_mail(
        subject="Reset your FlowDeck password",
        message=(
            f"Hi {user.display_name},\n\n"
            "Use this link to reset your FlowDeck password:\n"
            f"{link}\n\n"
            "If you didn't request this, you can ignore this email — your password will not change."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def blacklist_all_outstanding_tokens_for_user(user) -> None:
    """
    Force logout everywhere by blacklisting every outstanding refresh token
    for this user. Called after a password change/reset so a stolen or
    leaked refresh token doesn't survive a credential rotation.
    """
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)
