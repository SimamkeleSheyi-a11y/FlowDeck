from .models import WorkspaceMembership


def get_membership(user, workspace):
    """
    Resolve the requesting user's WorkspaceMembership for a workspace, or
    None. This is the single place that answers "what can this user do
    here" — views branch on the returned role rather than re-deriving it.
    """
    if not user or not user.is_authenticated:
        return None
    return WorkspaceMembership.objects.filter(workspace=workspace, user=user).first()
