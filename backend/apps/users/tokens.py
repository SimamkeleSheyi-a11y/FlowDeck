from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Deliberately a *separate* token namespace from Django's built-in
    password-reset generator (different key_salt), so an email-verification
    link can never be replayed as a password-reset link or vice versa.

    Hashing on `is_email_verified` also means a token issued before
    verification stops validating the instant the account becomes verified,
    without needing to track single-use state anywhere.
    """

    key_salt = "apps.users.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.is_email_verified}{user.email}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()

# Password-reset tokens intentionally reuse Django's battle-tested
# django.contrib.auth.tokens.default_token_generator directly (imported
# where needed) rather than a second custom subclass here — it already
# hashes on the password field, so a token is invalidated the moment the
# password it was issued for changes.
