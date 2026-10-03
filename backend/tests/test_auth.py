import pytest
from fastapi.testclient import TestClient

from app.security import verify_password


def credentials(email: str = "student@example.com") -> dict[str, str]:
    return {"email": email, "password": "Long-password-123!"}


def test_register_creates_student_and_returns_tokens(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = auth_client
    response = client.post("/api/auth/register", json=credentials("STUDENT@example.com"))

    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"] == "student@example.com"
    assert payload["user"]["role"] == "student"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert "hashed_password" not in payload["user"]
    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert profile.json() == payload["user"]


def test_login_checks_password_hash(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = auth_client
    client.post("/api/auth/register", json=credentials())

    response = client.post("/api/auth/login", json=credentials())
    invalid = client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "Incorrect-password-1"},
    )

    assert response.status_code == 200
    assert verify_password("Long-password-123!", "invalid") is False
    assert invalid.status_code == 401


def test_refresh_rotates_and_revokes_previous_token(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = auth_client
    original = client.post("/api/auth/register", json=credentials()).json()

    rotated = client.post("/api/auth/refresh", json={"refresh_token": original["refresh_token"]})
    reused = client.post("/api/auth/refresh", json={"refresh_token": original["refresh_token"]})

    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != original["refresh_token"]
    assert reused.status_code == 401


def test_logout_revokes_refresh_token(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = auth_client
    tokens = client.post("/api/auth/register", json=credentials()).json()
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 200
    revoked = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert revoked.status_code == 401


def test_user_settings_are_persisted_and_merged(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = auth_client
    tokens = client.post("/api/auth/register", json=credentials()).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    initial = client.get("/api/auth/settings", headers=headers)
    first_update = client.put(
        "/api/auth/settings",
        headers=headers,
        json={
            "settings": {
                "full_name": "Aisha Khan",
                "department": "English",
                "notifications": {"weekly_curriculum_summaries": True},
                "admin_only_flag": "ignore-me",
            }
        },
    )
    second_update = client.put(
        "/api/auth/settings",
        headers=headers,
        json={
            "settings": {
                "phone": "+92 300 1112223",
                "interface_language": "Urdu",
            }
        },
    )
    refreshed = client.get("/api/auth/settings", headers=headers)

    assert initial.status_code == 200
    assert initial.json() == {}
    assert first_update.status_code == 200
    assert first_update.json()["full_name"] == "Aisha Khan"
    assert "admin_only_flag" not in first_update.json()
    assert second_update.status_code == 200
    assert refreshed.json()["department"] == "English"
    assert refreshed.json()["phone"] == "+92 300 1112223"
    assert refreshed.json()["interface_language"] == "Urdu"
    assert refreshed.json()["notifications"]["weekly_curriculum_summaries"] is True


def test_settings_reject_missing_valid_payload(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = auth_client
    tokens = client.post("/api/auth/register", json=credentials()).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client.put(
        "/api/auth/settings",
        headers=headers,
        json={"settings": {"not_allowed": "value", "another_invalid_key": 42}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No valid settings provided"


def test_students_cannot_access_teacher_or_admin_routes(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = auth_client
    student = client.post("/api/auth/register", json=credentials()).json()
    headers = {"Authorization": f"Bearer {student['access_token']}"}

    teacher_response = client.get("/api/teacher/assessments", headers=headers)
    admin_response = client.get("/api/auth/admin/users", headers=headers)

    assert teacher_response.status_code == 403
    assert admin_response.status_code == 403


def test_teacher_and_admin_permissions_are_scoped(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    teacher_headers = {"Authorization": f"Bearer {tokens['teacher']}"}
    admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}

    teacher_assessments = client.get("/api/teacher/assessments", headers=teacher_headers)
    teacher_user_list = client.get("/api/auth/admin/users", headers=teacher_headers)
    admin_user_list = client.get("/api/auth/admin/users", headers=admin_headers)

    assert teacher_assessments.status_code == 200
    assert teacher_user_list.status_code == 403
    assert admin_user_list.status_code == 200
    assert {user["role"] for user in admin_user_list.json()["users"]} == {"admin", "teacher"}


def test_admin_can_create_a_privileged_user(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    response = client.post(
        "/api/auth/admin/users",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        json={**credentials("new-teacher@example.com"), "role": "teacher"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "teacher"
    assert "hashed_password" not in response.json()


def test_auth_validates_email_and_password_length(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = auth_client
    invalid_email = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "Long-password-123!"},
    )
    short_password = client.post(
        "/api/auth/register",
        json={"email": "student@example.com", "password": "short"},
    )

    assert invalid_email.status_code == 422
    assert short_password.status_code == 422


def test_auth_endpoints_are_rate_limited(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = auth_client
    responses = [
        client.post("/api/auth/login", json=credentials("absent@example.com")) for _ in range(13)
    ]

    assert all(response.status_code == 401 for response in responses[:12])
    assert responses[12].status_code == 429


def test_missing_signing_secret_fails_closed(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = auth_client
    monkeypatch.delenv("JWT_SECRET_KEY")
    response = client.post("/api/auth/register", json=credentials())

    assert response.status_code == 503
