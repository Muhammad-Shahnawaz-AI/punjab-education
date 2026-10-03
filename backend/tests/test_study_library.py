from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_pdf(text: str = "Photosynthesis uses light energy in plants.") -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode())
    page[NameObject("/Contents")] = stream
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upload(
    client: TestClient,
    token: str,
    filename: str = "biology.pdf",
    pdf: bytes | None = None,
) -> object:
    return client.post(
        "/api/study/books",
        headers=bearer(token),
        data={"title": "Grade 12 Biology"},
        files={"file": (filename, pdf or make_pdf(), "application/pdf")},
    )


def test_books_are_persisted_private_and_downloadable(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    student_tokens = client.post(
        "/api/auth/register",
        json={"email": "reader@example.com", "password": "Long-password-123!"},
    ).json()

    created = upload(client, student_tokens["access_token"])

    assert created.status_code == 201
    book_id = created.json()["id"]
    listed = client.get("/api/study/books", headers=bearer(student_tokens["access_token"]))
    other_users = client.get("/api/study/books", headers=bearer(tokens["teacher"]))
    downloaded = client.get(
        f"/api/study/books/{book_id}/file",
        headers=bearer(student_tokens["access_token"]),
    )
    other_user_download = client.get(
        f"/api/study/books/{book_id}/file",
        headers=bearer(tokens["teacher"]),
    )

    assert listed.status_code == 200
    assert [book["id"] for book in listed.json()] == [book_id]
    assert other_users.json() == []
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-")
    assert other_user_download.status_code == 404


def test_upload_rejects_invalid_or_non_text_pdfs(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    bad_pdf = upload(client, tokens["teacher"], pdf=b"not a pdf")
    image_only_writer = PdfWriter()
    image_only_writer.add_blank_page(width=612, height=792)
    image_only_buffer = BytesIO()
    image_only_writer.write(image_only_buffer)
    scanned_pdf = upload(client, tokens["teacher"], "scanned.pdf", image_only_buffer.getvalue())
    wrong_extension = upload(client, tokens["teacher"], "biology.txt")

    assert bad_pdf.status_code == 415
    assert scanned_pdf.status_code == 422
    assert "OCR" in scanned_pdf.json()["detail"]
    assert wrong_extension.status_code == 415


def test_users_cannot_delete_other_users_books(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    created = upload(client, tokens["teacher"])
    book_id = created.json()["id"]

    forbidden = client.delete(f"/api/study/books/{book_id}", headers=bearer(tokens["admin"]))
    still_there = client.get("/api/study/books", headers=bearer(tokens["teacher"]))

    assert forbidden.status_code == 404
    assert len(still_there.json()) == 1


def test_study_chat_uses_retrieved_book_text_and_cites_page(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.study_chat as study_chat

    client, tokens = auth_client
    created = upload(
        client,
        tokens["teacher"],
        pdf=make_pdf("Photosynthesis converts light energy into chemical energy in green plants."),
    )
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "Photosynthesis stores light energy as chemical energy [p. 1]."}}]}

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(study_chat.httpx, "post", fake_post)

    response = client.post(
        "/api/study/chat",
        headers=bearer(tokens["teacher"]),
        json={
            "book_ids": [created.json()["id"]],
            "prompt": "Explain photosynthesis",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"].startswith("Photosynthesis")
    assert response.json()["citations"] == [
        {"book_id": created.json()["id"], "book_title": "Grade 12 Biology", "page_number": 1}
    ]
    provider_request = captured["kwargs"]["json"]  # type: ignore[index]
    assert "Photosynthesis converts light energy" in provider_request["messages"][1]["content"]  # type: ignore[index]
    assert "English" in provider_request["messages"][0]["content"]  # type: ignore[index]


def test_study_chat_reports_missing_provider_configuration(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, tokens = auth_client
    created = upload(client, tokens["teacher"])
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    response = client.post(
        "/api/study/chat",
        headers=bearer(tokens["teacher"]),
        json={
            "book_ids": [created.json()["id"]],
            "prompt": "Explain photosynthesis",
            "language": "ur",
        },
    )

    assert response.status_code == 503
    assert "Study AI is not configured" in response.json()["detail"]
