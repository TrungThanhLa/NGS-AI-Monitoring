import uuid

from backend.models import Permission, Role, RolePermission, User, UserRole


def test_user_role_permission_roundtrip(db_session):
    role = Role(code=f"TESTROLE-{uuid.uuid4()}", name="Test Role")
    permission = Permission(code=f"test.view-{uuid.uuid4()}", resource="test", action="view")
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash")
    db_session.add_all([role, permission, user])
    db_session.flush()

    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    db_session.commit()

    linked_role = (
        db_session.query(Role)
        .join(UserRole, UserRole.role_id == Role.role_id)
        .filter(UserRole.user_id == user.user_id)
        .one()
    )
    assert linked_role.role_id == role.role_id

    linked_permission = (
        db_session.query(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
        .filter(RolePermission.role_id == role.role_id)
        .one()
    )
    assert linked_permission.permission_id == permission.permission_id
