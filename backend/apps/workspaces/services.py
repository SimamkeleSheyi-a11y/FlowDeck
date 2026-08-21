"""
Business logic for the invitation lifecycle, kept out of views.py. Nothing
here touches ActivityEvent or Notification models — those don't exist until
Phase 7 and Phase 10 respectively; invitations rely on plain email for now.
"""
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import InvitationStatus, WorkspaceInvitation, WorkspaceMembership


def create_invitation(workspace, email, invited_by, intended_role):
    raw_token = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation(
        workspace=workspace,
        email=email,
        invited_by=invited_by,
        intended_role=intended_role,
    )
    invitation.set_token(raw_token)
    invitation.save()
    _send_invitation_email(invitation, raw_token)
    return invitation


def _send_invitation_email(invitation, raw_token) -> None:
    link = f"{settings.FRONTEND_URL}/invitations/{raw_token}"
    inviter_name = invitation.invited_by.display_name if invitation.invited_by else "A teammate"
    send_mail(
        subject=f'You\'re invited to join "{invitation.workspace.name}" on FlowDeck',
        message=(
            f"{inviter_name} invited you to join \"{invitation.workspace.name}\" on FlowDeck "
            f"as {invitation.get_intended_role_display()}.\n\n"
            f"Accept here: {link}\n\n"
            f"This link expires on {invitation.expires_at:%d %b %Y}."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
    )


def expire_stale_invitations(workspace=None) -> int:
    """
    Flip any PENDING invitation whose expiry has passed to EXPIRED.

    Called defensively before anything that cares whether an invitation is
    *actually* still pending — listing a workspace's invitations, and
    checking for a duplicate before sending a new one. Without this, an
    invitation that expired weeks ago would sit at status=PENDING forever
    (nothing else updates it), which both misrepresents it in admin/owner
    listings and incorrectly blocks re-inviting that email, since the
    partial-unique "one pending invite per email" constraint only looks at
    the `status` column, not `expires_at`.
    """
    queryset = WorkspaceInvitation.objects.filter(
        status=InvitationStatus.PENDING, expires_at__lte=timezone.now()
    )
    if workspace is not None:
        queryset = queryset.filter(workspace=workspace)
    return queryset.update(status=InvitationStatus.EXPIRED, responded_at=timezone.now())


def resolve_invitation_by_raw_token(raw_token):
    """
    Direct indexed lookup on the token's hash (token_hash is unique+indexed
    on WorkspaceInvitation) rather than scanning every pending invitation
    and comparing each one — O(1) instead of O(n) in the number of
    outstanding invitations system-wide.

    A per-row constant-time compare isn't needed here: what's being matched
    is a hash of the token, not the token's own bytes, so there's no
    meaningful timing side-channel to defend against the way there would be
    for a raw secret comparison — a DB index equality lookup doesn't leak
    exploitable per-byte timing to a remote caller.
    """
    token_hash = WorkspaceInvitation.hash_token(raw_token)
    return (
        WorkspaceInvitation.objects.select_related("workspace", "invited_by")
        .filter(token_hash=token_hash, status=InvitationStatus.PENDING, expires_at__gt=timezone.now())
        .first()
    )


def accept_invitation(invitation, user) -> None:
    WorkspaceMembership.objects.get_or_create(
        workspace=invitation.workspace,
        user=user,
        defaults={"role": invitation.intended_role},
    )
    invitation.status = InvitationStatus.ACCEPTED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at"])


def revoke_invitation(invitation) -> None:
    invitation.status = InvitationStatus.REVOKED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at"])
