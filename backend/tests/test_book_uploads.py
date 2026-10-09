import hashlib
import tracemalloc
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import func, select

from app.models import BookUploadSession, OfficialBookChunk, OfficialBookSource


def make_pdf(text: str = "Chapter 1 Algebra. 1.1 Linear equations are equalities.") -> bytes:
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
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upload_metadata(client: TestClient) -> dict[str, object]:
    grade = client.get("/api/curriculum/upload-test-curriculum/grades").json()["items"][0]
    subject = client.get(f"/api/grades/{grade['id']}/subjects").json()["items"][0]
    return {
        "filename": "Grade 9 Mathematics.pdf",
        "content_type": "application/pdf",
        "file_size": len(make_pdf()),
        "title": "Grade 9 Mathematics Upload",
        "author": "Test Author",
        "grade_id": grade["id"],
        "subject_id": subject["id"],
        "source_name": "Test publisher",
        "source_url": "https://books.example.org/math.pdf",
        "rights_basis": "Written permission granted by the copyright holder.",
        "rights_confirmed": True,
        "language": "English",
        "edition": "2026",
        "description": "Upload test PDF",
        "use_ocr": False,
        "ocr_language": "eng",
    }


def create_upload(
    client: TestClient, token: str, metadata: dict[str, object] | None = None
) -> dict[str, object]:
    response = client.post(
        "/api/admin/books/uploads",
        headers=auth(token),
        json=metadata or upload_metadata(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def transfer_single_part(
    client: TestClient, token: str, session: dict[str, object], data: bytes
) -> None:
    checksum = hashlib.sha256(data).hexdigest()
    response = client.post(
        f"/api/admin/books/uploads/{session['id']}/parts/1/authorize",
        headers=auth(token),
        json={"sha256": checksum},
    )
    assert response.status_code == 200, response.text
    path = response.json()["url"]
    response = client.put(
        path,
        headers={**auth(token), "X-Part-SHA256": checksum},
        content=data,
    )
    assert response.status_code == 204, response.text


def test_upload_sessions_are_admin_only_and_validate_pdf_metadata(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    request = upload_metadata(client)

    assert client.post("/api/admin/books/uploads", json=request).status_code == 401
    assert (
        client.post(
            "/api/admin/books/uploads", headers=auth(tokens["teacher"]), json=request
        ).status_code
        == 403
    )
    invalid_extension = {**request, "filename": "book.txt"}
    assert (
        client.post(
            "/api/admin/books/uploads",
            headers=auth(tokens["admin"]),
            json=invalid_extension,
        ).status_code
        == 415
    )
    no_rights = {**request, "rights_confirmed": False}
    assert (
        client.post(
            "/api/admin/books/uploads", headers=auth(tokens["admin"]), json=no_rights
        ).status_code
        == 422
    )
    session = create_upload(client, tokens["admin"], request)
    assert session["status"] == "initiated"
    assert session["part_count"] == 1


def test_upload_can_resume_and_completion_is_idempotent(
    auth_client: tuple[TestClient, dict[str, str]], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    client, tokens = auth_client
    monkeypatch.setenv("TEMPORARY_UPLOAD_DIRECTORY", str(tmp_path))
    data = make_pdf()
    metadata = {**upload_metadata(client), "file_size": len(data)}
    session = create_upload(client, tokens["admin"], metadata)
    transfer_single_part(client, tokens["admin"], session, data)

    resumed = client.get(f"/api/admin/books/uploads/{session['id']}", headers=auth(tokens["admin"]))
    assert resumed.status_code == 200
    assert resumed.json()["uploaded_bytes"] == len(data)
    assert resumed.json()["uploaded_parts"] == {"1": len(data)}
    assert (
        client.get(
            f"/api/admin/books/uploads/{session['id']}", headers=auth(tokens["teacher"])
        ).status_code
        == 403
    )

    completed = client.post(
        f"/api/admin/books/uploads/{session['id']}/complete", headers=auth(tokens["admin"])
    )
    assert completed.status_code == 200, completed.text
    payload = completed.json()
    assert payload["status"] == "completed"
    assert payload["uploaded_bytes"] == len(data)
    book = client.get(f"/api/admin/books/{payload['book_id']}", headers=auth(tokens["admin"]))
    assert book.status_code == 200
    assert book.json()["processing_status"] == "queued"
    assert book.json()["checksum_sha256"] == hashlib.sha256(data).hexdigest()

    repeated = client.post(
        f"/api/admin/books/uploads/{session['id']}/complete",
        headers=auth(tokens["admin"]),
    )
    assert repeated.status_code == 200
    assert repeated.json()["book_id"] == payload["book_id"]
    assert (
        client.get(
            "/api/curriculum/search",
            params={"q": "equalities"},
            headers=auth(tokens["teacher"]),
        ).json()
        == []
    )


def test_part_checksum_mismatch_and_expired_session_are_rejected(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    client, tokens = auth_client
    monkeypatch.setenv("TEMPORARY_UPLOAD_DIRECTORY", str(tmp_path))
    data = make_pdf()
    session = create_upload(
        client, tokens["admin"], {**upload_metadata(client), "file_size": len(data)}
    )
    wrong_digest = hashlib.sha256(b"not-the-file").hexdigest()
    authorized = client.post(
        f"/api/admin/books/uploads/{session['id']}/parts/1/authorize",
        headers=auth(tokens["admin"]),
        json={"sha256": wrong_digest},
    )
    assert authorized.status_code == 200
    mismatch = client.put(
        authorized.json()["url"],
        headers={**auth(tokens["admin"]), "X-Part-SHA256": wrong_digest},
        content=data,
    )
    assert mismatch.status_code == 400

    sessions = client.app.state.test_sessions
    with sessions.begin() as db:
        upload = db.get(BookUploadSession, session["id"])
        assert upload is not None
        upload.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    expired = client.get(f"/api/admin/books/uploads/{session['id']}", headers=auth(tokens["admin"]))
    assert expired.status_code == 410


def test_completed_pdf_is_processed_and_retry_does_not_duplicate_chunks(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app import book_worker

    client, tokens = auth_client
    monkeypatch.setenv("TEMPORARY_UPLOAD_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(book_worker, "SessionLocal", client.app.state.test_sessions)
    monkeypatch.setenv("OCR_ENABLED", "false")
    data = make_pdf()
    session = create_upload(
        client, tokens["admin"], {**upload_metadata(client), "file_size": len(data)}
    )
    transfer_single_part(client, tokens["admin"], session, data)
    completed = client.post(
        f"/api/admin/books/uploads/{session['id']}/complete", headers=auth(tokens["admin"])
    )
    book_id = completed.json()["book_id"]

    assert book_worker.process_next_job()
    book = client.get(f"/api/admin/books/{book_id}", headers=auth(tokens["admin"])).json()
    assert book["processing_status"] == "ready"
    assert book["page_count"] == 1
    assert book["processing_progress"] == 100
    results = client.get(
        "/api/curriculum/search",
        params={"q": "equalities"},
        headers=auth(tokens["teacher"]),
    )
    assert results.status_code == 200
    assert results.json()[0]["page_number"] == 1

    sessions = client.app.state.test_sessions
    with sessions() as db:
        source = db.scalar(select(OfficialBookSource).where(OfficialBookSource.book_id == book_id))
        assert source is not None
        source_id = source.id
        chunk_count = db.scalar(
            select(func.count())
            .select_from(OfficialBookChunk)
            .where(OfficialBookChunk.source_id == source.id)
        )
        assert chunk_count and chunk_count > 0
    retried = client.post(
        f"/api/admin/books/{book_id}/retry",
        headers=auth(tokens["admin"]),
        json={"use_ocr": False, "ocr_language": "eng"},
    )
    assert retried.status_code == 200
    assert book_worker.process_next_job()
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(OfficialBookChunk)
                .where(OfficialBookChunk.source_id == source_id)
            )
            == chunk_count
        )
        source = db.scalar(select(OfficialBookSource).where(OfficialBookSource.book_id == book_id))
        assert source is not None
        storage_path = tmp_path / source.storage_key
    deleted = client.delete(f"/api/admin/books/{book_id}", headers=auth(tokens["admin"]))
    assert deleted.status_code == 204
    assert not storage_path.exists()
    assert (
        client.get(
            "/api/curriculum/search",
            params={"q": "equalities"},
            headers=auth(tokens["teacher"]),
        ).json()
        == []
    )


def test_configured_maximum_size_is_enforced(
    auth_client: tuple[TestClient, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, tokens = auth_client
    monkeypatch.setenv("MAX_PDF_SIZE_BYTES", "10")
    request = {**upload_metadata(client), "file_size": 11}

    response = client.post("/api/admin/books/uploads", headers=auth(tokens["admin"]), json=request)

    assert response.status_code == 413


def test_malformed_signature_is_rejected_at_completion(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    client, tokens = auth_client
    monkeypatch.setenv("TEMPORARY_UPLOAD_DIRECTORY", str(tmp_path))
    malformed = b"not a PDF"
    session = create_upload(
        client,
        tokens["admin"],
        {**upload_metadata(client), "file_size": len(malformed)},
    )
    transfer_single_part(client, tokens["admin"], session, malformed)

    response = client.post(
        f"/api/admin/books/uploads/{session['id']}/complete",
        headers=auth(tokens["admin"]),
    )

    assert response.status_code == 415


def test_ocr_failure_is_reported_as_recoverable_processing_error(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app import book_worker

    client, tokens = auth_client
    monkeypatch.setenv("TEMPORARY_UPLOAD_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("OCR_ENABLED", "false")
    monkeypatch.setattr(book_worker, "SessionLocal", client.app.state.test_sessions)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    scanned = output.getvalue()
    session = create_upload(
        client,
        tokens["admin"],
        {
            **upload_metadata(client),
            "title": "Scanned mathematics",
            "file_size": len(scanned),
            "use_ocr": True,
        },
    )
    transfer_single_part(client, tokens["admin"], session, scanned)
    completed = client.post(
        f"/api/admin/books/uploads/{session['id']}/complete",
        headers=auth(tokens["admin"]),
    )
    assert completed.status_code == 200
    assert book_worker.process_next_job()
    book = client.get(
        f"/api/admin/books/{completed.json()['book_id']}", headers=auth(tokens["admin"])
    ).json()
    assert book["processing_status"] == "failed"
    assert "OCR is disabled" in book["last_error"]


def test_truncated_pdf_fails_processing_and_is_not_searchable(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app import book_worker

    client, tokens = auth_client
    monkeypatch.setenv("TEMPORARY_UPLOAD_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(book_worker, "SessionLocal", client.app.state.test_sessions)
    truncated = b"%PDF-1.4\nnot a valid document"
    session = create_upload(
        client,
        tokens["admin"],
        {**upload_metadata(client), "file_size": len(truncated)},
    )
    transfer_single_part(client, tokens["admin"], session, truncated)
    completed = client.post(
        f"/api/admin/books/uploads/{session['id']}/complete", headers=auth(tokens["admin"])
    )
    assert completed.status_code == 200
    assert book_worker.process_next_job()
    book = client.get(
        f"/api/admin/books/{completed.json()['book_id']}", headers=auth(tokens["admin"])
    ).json()
    assert book["processing_status"] == "failed"
    assert book["last_error"]
    assert (
        client.get(
            "/api/curriculum/search",
            params={"q": "document"},
            headers=auth(tokens["teacher"]),
        ).json()
        == []
    )


def test_local_multipart_assembly_uses_bounded_reads(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from app import book_storage

    monkeypatch.setenv("TEMPORARY_UPLOAD_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(book_storage, "STREAM_BUFFER_SIZE", 64 * 1024)
    storage = book_storage.LocalBookStorage()
    key = "official-books/streaming-memory.pdf"
    data_size = 12 * 1024 * 1024
    part_path = storage._part_dir(key) / "00001.part"
    with part_path.open("wb") as output:
        block = b"x" * (64 * 1024)
        for _ in range(data_size // len(block)):
            output.write(block)
    digest = hashlib.sha256()
    with part_path.open("rb") as part:
        while chunk := part.read(64 * 1024):
            digest.update(chunk)
    manifest = {"1": {"size": data_size, "sha256": digest.hexdigest()}}

    tracemalloc.start()
    size, checksum = storage.complete(key, None, manifest, data_size)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert size == data_size
    assert checksum == digest.hexdigest()
    assert peak < 2 * 1024 * 1024
