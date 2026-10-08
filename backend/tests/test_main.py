from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_generation_request() -> dict[str, object]:
    return {
        "curriculum": "Punjab",
        "subject": "Mathematics",
        "book": "Mathematics 9",
        "chapter": "Algebra",
        "topic": "Linear equations",
        "question_type": "mcq",
    }


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_returns_valid_ai_payload(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client_with_auth, tokens = auth_client
    response = client_with_auth.post(
        "/api/ai/generate",
        headers=auth_headers(tokens["teacher"]),
        json=valid_generation_request(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["request"]["count"] == 10
    assert len(payload["items"]) == 10
    assert payload["items"][0]["question"]


def test_curriculum_catalog_returns_database_records(catalog_client: TestClient) -> None:
    response = catalog_client.get("/api/curriculum")

    assert response.status_code == 200
    assert response.json()["curricula"] == [
        {
            "id": "sample-fixture",
            "name": "Sample Curriculum",
            "description": "Sample data only.",
            "is_sample": True,
        }
    ]


def test_curriculum_hierarchy_returns_seeded_children(catalog_client: TestClient) -> None:
    curricula = catalog_client.get("/api/curriculum").json()["curricula"]
    grades = catalog_client.get(f"/api/curriculum/{curricula[0]['id']}/grades").json()["items"]
    subjects = catalog_client.get(f"/api/grades/{grades[0]['id']}/subjects").json()["items"]
    books = catalog_client.get(f"/api/subjects/{subjects[0]['id']}/books").json()["items"]
    chapters = catalog_client.get(f"/api/books/{books[0]['id']}/chapters").json()["items"]
    topics = catalog_client.get(f"/api/chapters/{chapters[0]['id']}/topics").json()["items"]

    assert [grade["name"] for grade in grades] == ["Grade 9", "Grade 10"]
    assert subjects[0]["name"] == "Sample Subject"
    assert books[0]["name"] == "Sample Book"
    assert chapters[0]["name"] == "Sample Chapter"
    assert topics[0]["name"] == "Sample Topic"


def test_curriculum_catalog_reports_missing_parent(catalog_client: TestClient) -> None:
    response = catalog_client.get("/api/curriculum/not-a-curriculum/grades")

    assert response.status_code == 404


def test_known_grade_without_subjects_returns_empty_list(catalog_client: TestClient) -> None:
    grades = catalog_client.get("/api/curriculum/sample-fixture/grades").json()["items"]
    empty_grade = next(grade for grade in grades if grade["name"] == "Grade 10")

    response = catalog_client.get(f"/api/grades/{empty_grade['id']}/subjects")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_generate_accepts_count_boundaries(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client_with_auth, tokens = auth_client
    for count in (1, 50):
        response = client_with_auth.post(
            "/api/ai/generate",
            headers=auth_headers(tokens["teacher"]),
            json={**valid_generation_request(), "count": count},
        )

        assert response.status_code == 200


def test_generate_rejects_count_outside_bounds(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client_with_auth, tokens = auth_client
    for count in (0, -5, 51, 100000):
        response = client_with_auth.post(
            "/api/ai/generate",
            headers=auth_headers(tokens["teacher"]),
            json={**valid_generation_request(), "count": count},
        )

        assert response.status_code == 422


def test_generate_rejects_blank_fields(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client_with_auth, tokens = auth_client
    for field in ("curriculum", "subject", "book", "chapter", "topic"):
        response = client_with_auth.post(
            "/api/ai/generate",
            headers=auth_headers(tokens["teacher"]),
            json={**valid_generation_request(), field: "   "},
        )

        assert response.status_code == 422


def test_generate_rejects_fields_over_max_length(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client_with_auth, tokens = auth_client
    response = client_with_auth.post(
        "/api/ai/generate",
        headers=auth_headers(tokens["teacher"]),
        json={**valid_generation_request(), "topic": "t" * 201},
    )

    assert response.status_code == 422


def test_health_allows_default_frontend_origin() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_study_chat_rejects_non_education_queries(auth_client: tuple[TestClient, dict[str, str]]) -> None:
    client_with_auth, tokens = auth_client
    response = client_with_auth.post(
        "/api/study/chat",
        headers={"Authorization": f"Bearer {tokens['teacher']}", "Content-Type": "application/json"},
        json={"book_ids": [], "prompt": "How do I build a bomb?", "language": "en"},
    )

    assert response.status_code == 400
    assert "education" in response.json()["detail"].lower()


def test_study_chat_returns_empty_portal_message_when_no_books_are_available(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client_with_auth, tokens = auth_client
    response = client_with_auth.post(
        "/api/study/chat",
        headers={"Authorization": f"Bearer {tokens['teacher']}", "Content-Type": "application/json"},
        json={"book_ids": [], "prompt": "What is this education platform about?", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "portal" in payload["answer"].lower()
    assert "admin" in payload["answer"].lower()
    assert "books" in payload["answer"].lower()
