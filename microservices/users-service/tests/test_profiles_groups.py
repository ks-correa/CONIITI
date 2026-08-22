from datetime import datetime, timedelta, timezone

from jose import jwt
from app.models.group import GroupMembership, GroupMembershipRole
from app.models.user import User
from app.clients import auth_client

from conftest import TestingSessionLocal, client


def auth_headers(user_id: str, role: str = "external") -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": user_id,
            "type": "access",
            "role": role,
            "email": f"{user_id}@example.com",
            "full_name": "Test User",
            "sv": 1,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "test-secret",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def seed_user(user_id: str, role: str, *, full_name: str, email: str) -> None:
    db = TestingSessionLocal()
    try:
        db.add(User(id=user_id, role=role, full_name=full_name, email=email, is_active=True))
        db.commit()
    finally:
        db.close()


def test_user_can_complete_optional_profile_after_registration(monkeypatch):
    monkeypatch.setattr(auth_client, "update_auth_account", lambda *_args, **_kwargs: {})
    user_id = "user-profile"
    seed_user(user_id, "external", full_name="OAuth Person", email="oauth@example.com")

    response = client.patch(
        "/me",
        headers=auth_headers(user_id),
        json={
            "first_name": "Ana",
            "last_name": "Rios",
            "career": "Ingenieria de Sistemas",
            "gender": "Mujer",
            "document": "DOC-100",
            "institutional_code": "EST-100",
            "institution": "Universidad Demo",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Ana Rios"
    assert data["profile_completed"] is True
    assert data["career"] == "Ingenieria de Sistemas"
    assert data["email"] == "oauth@example.com"


def test_admin_profiles_are_paginated_and_last_superuser_is_protected():
    admin_id = "admin-one"
    seed_user(admin_id, "superuser", full_name="Admin", email="admin@example.com")
    seed_user("user-two", "external", full_name="Second", email="second@example.com")

    listing = client.get(
        "/admin/profiles?page=1&page_size=1&search=second",
        headers=auth_headers(admin_id, "superuser"),
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == "user-two"

    protected = client.patch(
        f"/admin/profiles/{admin_id}",
        headers=auth_headers(admin_id, "superuser"),
        json={"is_active": False},
    )
    assert protected.status_code == 409


def test_role_change_suspends_auth_before_commit_and_reactivates_with_new_version(monkeypatch):
    actor_id = "admin-actor"
    target_id = "admin-target"
    seed_user(actor_id, "superuser", full_name="Actor", email="actor@example.com")
    seed_user(target_id, "superuser", full_name="Target", email="target@example.com")
    calls = []
    monkeypatch.setattr(
        auth_client,
        "revoke_auth_sessions",
        lambda user_id, **kwargs: calls.append((user_id, kwargs.get("is_active"))) or {},
    )

    response = client.patch(
        f"/admin/profiles/{target_id}",
        headers=auth_headers(actor_id, "superuser"),
        json={"role": "external"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "external"
    assert calls == [(target_id, False), (target_id, True)]


def test_internal_profile_summaries_return_no_extra_pii():
    seed_user("winner", "external", full_name="Winner Name", email="private@example.com")
    response = client.post(
        "/internal/profile-summaries",
        headers={"X-Internal-Service-Token": "test-internal-token"},
        json={"user_ids": ["winner", "missing"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"id": "winner", "full_name": "Winner Name"}],
        "missing_ids": ["missing"],
    }


def test_group_admin_is_scoped_and_cannot_grant_group_admin_role():
    super_id = "super"
    group_admin_id = "group-admin"
    member_id = "member"
    outsider_id = "outsider"
    seed_user(super_id, "superuser", full_name="Super", email="super@example.com")
    seed_user(group_admin_id, "external", full_name="Group Admin", email="ga@example.com")
    seed_user(member_id, "external", full_name="Member", email="member@example.com")
    seed_user(outsider_id, "external", full_name="Outsider", email="out@example.com")

    created = client.post(
        "/groups",
        headers=auth_headers(super_id, "superuser"),
        json={"name": "Semillero IA", "description": "Grupo de participantes"},
    )
    assert created.status_code == 201
    group_id = created.json()["id"]

    promoted = client.post(
        f"/groups/{group_id}/members",
        headers=auth_headers(super_id, "superuser"),
        json={"user_id": group_admin_id, "membership_role": "group_admin"},
    )
    assert promoted.status_code == 201

    added = client.post(
        f"/groups/{group_id}/members",
        headers=auth_headers(group_admin_id),
        json={"user_id": member_id, "membership_role": "member"},
    )
    assert added.status_code == 201

    forbidden_promotion = client.post(
        f"/groups/{group_id}/members",
        headers=auth_headers(group_admin_id),
        json={"user_id": outsider_id, "membership_role": "group_admin"},
    )
    assert forbidden_promotion.status_code == 403

    outsider_read = client.get(f"/groups/{group_id}", headers=auth_headers(outsider_id))
    assert outsider_read.status_code == 403

    my_groups = client.get("/me/groups", headers=auth_headers(group_admin_id))
    assert my_groups.status_code == 200
    assert my_groups.json()[0]["current_membership_role"] == "group_admin"

    db = TestingSessionLocal()
    try:
        membership = db.query(GroupMembership).filter_by(
            group_id=group_id,
            user_id=group_admin_id,
        ).one()
        assert membership.membership_role == GroupMembershipRole.GROUP_ADMIN
    finally:
        db.close()
