from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_generation_request() -> dict[str, object]:
    return {
        'curriculum': 'Punjab',
        'subject': 'Mathematics',
        'book': 'Mathematics 9',
        'chapter': 'Algebra',
        'topic': 'Linear equations',
        'question_type': 'mcq',
    }


def test_health_returns_ok() -> None:
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_curriculum_returns_available_curricula() -> None:
    response = client.get('/api/curriculum')

    assert response.status_code == 200
    assert response.json()['curricula'][0]['id'] == 'punjab-2025'


def test_generate_returns_request_and_pending_status() -> None:
    response = client.post('/api/ai/generate', json=valid_generation_request())

    assert response.status_code == 200
    assert response.json()['status'] == 'queued'
    assert response.json()['request']['count'] == 10
    assert response.json()['items'] == []


def test_generate_accepts_count_boundaries() -> None:
    for count in (1, 50):
        response = client.post(
            '/api/ai/generate',
            json={**valid_generation_request(), 'count': count},
        )

        assert response.status_code == 200


def test_generate_rejects_count_outside_bounds() -> None:
    for count in (0, -5, 51, 100000):
        response = client.post(
            '/api/ai/generate',
            json={**valid_generation_request(), 'count': count},
        )

        assert response.status_code == 422


def test_generate_rejects_blank_fields() -> None:
    for field in ('curriculum', 'subject', 'book', 'chapter', 'topic'):
        response = client.post(
            '/api/ai/generate',
            json={**valid_generation_request(), field: '   '},
        )

        assert response.status_code == 422


def test_generate_rejects_fields_over_max_length() -> None:
    response = client.post(
        '/api/ai/generate',
        json={**valid_generation_request(), 'topic': 't' * 201},
    )

    assert response.status_code == 422


def test_health_allows_default_frontend_origin() -> None:
    response = client.get(
        '/health',
        headers={'Origin': 'http://localhost:3000'},
    )

    assert response.headers['access-control-allow-origin'] == 'http://localhost:3000'