from rest_framework.permissions import BasePermission


class IsEmailVerified(BasePermission):
    """
    Not wired into any Phase 2 endpoint yet — provided here as a ready-made
    building block for later phases (e.g. requiring a verified email before
    a user can create a workspace or be assigned tasks).
    """

    message = "Please verify your email address before continuing."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_email_verified
        )
