import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status

from apps.users.models import User
from apps.workspaces.models import (
    InvitationStatus,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceRole,
)

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"


def _make_user(email, display_name, verified=True):
    user = User.objects.create_user(email=email, password=PASSWORD, display_name=display_name)
    if verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
    return user


def _authenticate(api_client, user):
    """Force-authenticates without touching the real login endpoint — see
    test_workspace_crud.py's _authenticate() for the full rationale."""
    api_client.force_authenticate(user=user)


@pytest.fixture
def workspace_with_owner_and_member(api_client):
    owner = _make_user("invite_owner@example.com", "Owner")
    member = _make_user("invite_member@example.com", "Member")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Invite Workspace"})
    workspace = Workspace.objects.get(id=created.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)
    return workspace, owner, member


@pytest.fixture
def workspace_with_owner_admin_member(api_client):
    owner = _make_user("invite_owner2@example.com", "Owner")
    admin = _make_user("invite_admin2@example.com", "Admin")
    member = _make_user("invite_member2@example.com", "Member")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Invite Workspace 2"})
    workspace = Workspace.objects.get(id=created.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)
    return workspace, owner, admin, member


def test_owner_can_send_invitation(api_client, workspace_with_owner_and_member, mailoutbox):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "newbie@example.com", "intended_role": "MEMBER"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == InvitationStatus.PENDING
    assert len(mailoutbox) == 1
    invitation = WorkspaceInvitation.objects.get(workspace=workspace, email="newbie@example.com")
    assert invitation.token_hash  # a hash was stored...
    assert len(invitation.token_hash) == 64  # ...but never the raw token


def test_member_cannot_send_invitation(api_client, workspace_with_owner_and_member):
    workspace, _owner, member = workspace_with_owner_and_member
    _authenticate(api_client, member)

    response = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "newbie2@example.com", "intended_role": "MEMBER"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_invite_an_existing_member(api_client, workspace_with_owner_and_member):
    workspace, owner, member = workspace_with_owner_and_member
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": member.email, "intended_role": "MEMBER"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "already_member"


def test_cannot_send_duplicate_pending_invitation(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)

    first = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "duplicate@example.com", "intended_role": "MEMBER"},
    )
    second = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "duplicate@example.com", "intended_role": "MEMBER"},
    )

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.data["code"] == "invitation_pending"


def test_invitation_preview_does_not_require_authentication(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "previewer@example.com", "intended_role": "ADMIN"},
    )
    raw_token = _extract_token_from_mailbox()

    api_client.credentials()  # drop auth entirely
    response = api_client.get(reverse("workspaces:invitation-preview", args=[raw_token]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["workspace_name"] == workspace.name
    assert response.data["intended_role"] == "ADMIN"
    assert response.data["is_valid"] is True


def test_accept_requires_matching_email(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "onlyfor@example.com", "intended_role": "MEMBER"},
    )
    raw_token = _extract_token_from_mailbox()

    wrong_person = _make_user("wrongperson@example.com", "Wrong Person")
    api_client.credentials()
    _authenticate(api_client, wrong_person)

    response = api_client.post(reverse("workspaces:invitation-accept", args=[raw_token]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=wrong_person).exists() is False


def test_accept_creates_membership_with_intended_role(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "accepted@example.com", "intended_role": "ADMIN"},
    )
    raw_token = _extract_token_from_mailbox()

    invitee = _make_user("accepted@example.com", "Invitee")
    api_client.credentials()
    _authenticate(api_client, invitee)

    response = api_client.post(reverse("workspaces:invitation-accept", args=[raw_token]))

    assert response.status_code == status.HTTP_200_OK
    membership = WorkspaceMembership.objects.get(workspace=workspace, user=invitee)
    assert membership.role == WorkspaceRole.ADMIN

    invitation = WorkspaceInvitation.objects.get(workspace=workspace, email="accepted@example.com")
    assert invitation.status == InvitationStatus.ACCEPTED
    assert invitation.responded_at is not None


def test_owner_can_revoke_a_pending_invitation(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "revokeme@example.com", "intended_role": "MEMBER"},
    )
    invitation_id = created.data["id"]

    response = api_client.delete(
        reverse("workspaces:invitation-revoke", args=[workspace.id, invitation_id])
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    invitation = WorkspaceInvitation.objects.get(id=invitation_id)
    assert invitation.status == InvitationStatus.REVOKED


def test_revoked_invitation_cannot_be_accepted(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "revokedaccept@example.com", "intended_role": "MEMBER"},
    )
    raw_token = _extract_token_from_mailbox()
    api_client.delete(reverse("workspaces:invitation-revoke", args=[workspace.id, created.data["id"]]))

    invitee = _make_user("revokedaccept@example.com", "Invitee")
    api_client.credentials()
    _authenticate(api_client, invitee)
    response = api_client.post(reverse("workspaces:invitation-accept", args=[raw_token]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_expired_invitation_cannot_be_resolved(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    invitation = WorkspaceInvitation(
        workspace=workspace,
        email="expired@example.com",
        invited_by=owner,
        intended_role="MEMBER",
        expires_at=timezone.now() - timedelta(days=1),
    )
    invitation.set_token("some-raw-token")
    invitation.save()

    invitee = _make_user("expired@example.com", "Invitee")
    _authenticate(api_client, invitee)
    response = api_client.post(reverse("workspaces:invitation-accept", args=["some-raw-token"]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_admin_can_invite_member(api_client, workspace_with_owner_admin_member):
    workspace, _owner, admin, _member = workspace_with_owner_admin_member
    _authenticate(api_client, admin)

    response = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "adminsinvitee@example.com", "intended_role": "MEMBER"},
    )

    assert response.status_code == status.HTTP_201_CREATED


def test_admin_cannot_invite_admin(api_client, workspace_with_owner_admin_member):
    workspace, _owner, admin, _member = workspace_with_owner_admin_member
    _authenticate(api_client, admin)

    response = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "shouldnotbeinvited@example.com", "intended_role": "ADMIN"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "only_owner_can_invite_admin"
    assert WorkspaceInvitation.objects.filter(email="shouldnotbeinvited@example.com").exists() is False


def test_owner_can_invite_admin(api_client, workspace_with_owner_admin_member):
    workspace, owner, _admin, _member = workspace_with_owner_admin_member
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "newadmin@example.com", "intended_role": "ADMIN"},
    )

    assert response.status_code == status.HTTP_201_CREATED


def test_admin_cannot_revoke_admin_invitation(api_client, workspace_with_owner_admin_member):
    workspace, owner, admin, _member = workspace_with_owner_admin_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "adminrevoketarget@example.com", "intended_role": "ADMIN"},
    )
    invitation_id = created.data["id"]

    api_client.credentials()
    _authenticate(api_client, admin)
    response = api_client.delete(reverse("workspaces:invitation-revoke", args=[workspace.id, invitation_id]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "only_owner_can_revoke_admin_invitation"
    assert WorkspaceInvitation.objects.get(id=invitation_id).status == InvitationStatus.PENDING


def test_owner_can_revoke_admin_invitation(api_client, workspace_with_owner_admin_member):
    workspace, owner, _admin, _member = workspace_with_owner_admin_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "ownerrevoketarget@example.com", "intended_role": "ADMIN"},
    )
    invitation_id = created.data["id"]

    response = api_client.delete(reverse("workspaces:invitation-revoke", args=[workspace.id, invitation_id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert WorkspaceInvitation.objects.get(id=invitation_id).status == InvitationStatus.REVOKED


def test_member_cannot_revoke_invitation(api_client, workspace_with_owner_admin_member):
    workspace, owner, _admin, member = workspace_with_owner_admin_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "memberrevoketarget@example.com", "intended_role": "MEMBER"},
    )
    invitation_id = created.data["id"]

    api_client.credentials()
    _authenticate(api_client, member)
    response = api_client.delete(reverse("workspaces:invitation-revoke", args=[workspace.id, invitation_id]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert WorkspaceInvitation.objects.get(id=invitation_id).status == InvitationStatus.PENDING


def test_cannot_revoke_an_already_accepted_invitation(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "alreadyaccepted@example.com", "intended_role": "MEMBER"},
    )
    raw_token = _extract_token_from_mailbox()
    invitee = _make_user("alreadyaccepted@example.com", "Invitee")
    api_client.credentials()
    _authenticate(api_client, invitee)
    api_client.post(reverse("workspaces:invitation-accept", args=[raw_token]))

    api_client.credentials()
    _authenticate(api_client, owner)
    response = api_client.delete(
        reverse("workspaces:invitation-revoke", args=[workspace.id, created.data["id"]])
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "not_pending"
    # the already-accepted membership must survive an attempted revoke untouched
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=invitee).exists()


def test_cannot_revoke_an_already_revoked_invitation(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "doublerevoke@example.com", "intended_role": "MEMBER"},
    )
    invitation_id = created.data["id"]
    first = api_client.delete(reverse("workspaces:invitation-revoke", args=[workspace.id, invitation_id]))
    assert first.status_code == status.HTTP_204_NO_CONTENT

    second = api_client.delete(reverse("workspaces:invitation-revoke", args=[workspace.id, invitation_id]))

    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.data["code"] == "not_pending"
    assert WorkspaceInvitation.objects.get(id=invitation_id).status == InvitationStatus.REVOKED


def test_cannot_accept_an_already_accepted_invitation(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "doubleaccept@example.com", "intended_role": "MEMBER"},
    )
    raw_token = _extract_token_from_mailbox()

    invitee = _make_user("doubleaccept@example.com", "Invitee")
    api_client.credentials()
    _authenticate(api_client, invitee)
    first = api_client.post(reverse("workspaces:invitation-accept", args=[raw_token]))
    assert first.status_code == status.HTTP_200_OK

    second = api_client.post(reverse("workspaces:invitation-accept", args=[raw_token]))

    # already ACCEPTED, so no longer resolvable by token — rejected safely,
    # not a crash, and no duplicate membership
    assert second.status_code == status.HTTP_404_NOT_FOUND
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=invitee).count() == 1


def test_expired_invitation_flips_to_expired_and_unblocks_reinvite(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member

    stale = WorkspaceInvitation(
        workspace=workspace,
        email="comeback@example.com",
        invited_by=owner,
        intended_role="MEMBER",
        expires_at=timezone.now() - timedelta(days=1),
    )
    stale.set_token("stale-token-comeback")
    stale.save()
    assert stale.status == InvitationStatus.PENDING  # still PENDING at rest, just past its expiry

    _authenticate(api_client, owner)
    response = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "comeback@example.com", "intended_role": "MEMBER"},
    )

    # the stale PENDING row must NOT block a fresh invite to the same email
    assert response.status_code == status.HTTP_201_CREATED

    stale.refresh_from_db()
    assert stale.status == InvitationStatus.EXPIRED  # swept as a side effect of the re-invite check

    fresh = WorkspaceInvitation.objects.get(
        workspace=workspace, email="comeback@example.com", status=InvitationStatus.PENDING
    )
    assert fresh.id != stale.id


def test_resolving_a_token_does_not_scan_every_pending_invitation(
    api_client, workspace_with_owner_and_member, django_assert_max_num_queries
):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)

    # a pile of unrelated pending invitations the old O(n) scan-and-compare
    # approach would have had to iterate through one at a time
    for i in range(20):
        api_client.post(
            reverse("workspaces:invitations", args=[workspace.id]),
            {"email": f"decoy{i}@example.com", "intended_role": "MEMBER"},
        )

    created = api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "findme@example.com", "intended_role": "MEMBER"},
    )
    assert created.status_code == status.HTTP_201_CREATED
    raw_token = _extract_token_from_mailbox()

    api_client.credentials()  # preview is unauthenticated
    with django_assert_max_num_queries(3):
        response = api_client.get(reverse("workspaces:invitation-preview", args=[raw_token]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["workspace_name"] == workspace.name


def test_unverified_invitee_cannot_accept(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)
    api_client.post(
        reverse("workspaces:invitations", args=[workspace.id]),
        {"email": "unverifiedinvitee@example.com", "intended_role": "MEMBER"},
    )
    raw_token = _extract_token_from_mailbox()

    invitee = _make_user("unverifiedinvitee@example.com", "Unverified Invitee", verified=False)
    api_client.credentials()
    _authenticate(api_client, invitee)

    response = api_client.post(reverse("workspaces:invitation-accept", args=[raw_token]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=invitee).exists() is False


def _extract_token_from_mailbox() -> str:
    from django.core import mail

    body = mail.outbox[-1].body
    # links look like ".../invitations/<token>" with no trailing slash
    line = [l for l in body.splitlines() if "/invitations/" in l][0]
    return line.strip().rsplit("/invitations/", 1)[-1]
