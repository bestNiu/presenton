from domains.platform.enums import WorkspaceRole


ROLE_RANK: dict[WorkspaceRole, int] = {
    WorkspaceRole.VIEWER: 10,
    WorkspaceRole.REVIEWER: 20,
    WorkspaceRole.EDITOR: 30,
    WorkspaceRole.ADMIN: 40,
    WorkspaceRole.OWNER: 50,
}


def role_allows(actual: WorkspaceRole | str, required: WorkspaceRole) -> bool:
    try:
        actual_role = (
            actual if isinstance(actual, WorkspaceRole) else WorkspaceRole(actual)
        )
    except ValueError:
        return False
    return ROLE_RANK[actual_role] >= ROLE_RANK[required]


def can_manage_members(role: WorkspaceRole | str) -> bool:
    return role_allows(role, WorkspaceRole.ADMIN)


def can_edit_content(role: WorkspaceRole | str) -> bool:
    return role_allows(role, WorkspaceRole.EDITOR)


def can_review_content(role: WorkspaceRole | str) -> bool:
    return role_allows(role, WorkspaceRole.REVIEWER)
