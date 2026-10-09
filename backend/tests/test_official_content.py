import json
import sys
from io import BytesIO
from types import ModuleType, SimpleNamespace

import pytest
from app.official_content import _extract_pages
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_text_pdf(text: str) -> bytes:
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


def upload_official_book(
    client: TestClient,
    token: str,
    *,
    rights_confirmed: str = "true",
    outline: list[dict[str, object]] | None = None,
    book_name: str = "Mathematics 9 (2026)",
) -> object:
    outline = outline or [
        {"name": "Algebra", "start_page": 1, "topics": ["Linear equations"]}
    ]
    return client.post(
        "/api/curriculum/books/import",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "curriculum_name": "Punjab Board",
            "curriculum_code": "punjab-board",
            "grade_level": "9",
            "subject_name": "Mathematics",
            "book_name": book_name,
            "source_name": "Taleem360",
            "source_url": "https://www.taleem360.com/9th-class-math-em-new-punjab-text-book-2026-pdf",
            "rights_basis": "Written permission from the copyright holder.",
            "rights_confirmed": rights_confirmed,
            "outline": json.dumps(outline),
        },
        files={
            "file": (
                "mathematics-9.pdf",
                make_text_pdf(
                    "Chapter 1 Algebra. Linear equations describe equality between expressions."
                ),
                "application/pdf",
            )
        },
    )


def test_admin_import_indexes_reviewed_book_for_catalog_and_search(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    response = upload_official_book(client, tokens["admin"])

    assert response.status_code == 201, response.text
    assert response.json()["indexed_chunks"] == 1
    assert response.json()["chapters"] == 1

    catalog = client.get("/api/curriculum/punjab-board/grades")
    assert catalog.status_code == 200
    grade_id = catalog.json()["items"][0]["id"]
    subjects = client.get(f"/api/grades/{grade_id}/subjects").json()["items"]
    book_id = client.get(f"/api/subjects/{subjects[0]['id']}/books").json()["items"][0]["id"]
    assert book_id == response.json()["book_id"]

    search = client.get(
        "/api/curriculum/search",
        params={"q": "equality"},
        headers={"Authorization": f"Bearer {tokens['teacher']}"},
    )
    assert search.status_code == 200
    assert search.json()[0]["book"] == "Mathematics 9 (2026)"
    assert search.json()[0]["chapter"] == "Algebra"
    assert search.json()[0]["page_number"] == 1
    assert search.json()[0]["source_name"] == "Taleem360"


@pytest.mark.parametrize(
    "outline",
    [
        [{"name": "   ", "start_page": 1}],
        [{"name": "Algebra", "start_page": 1, "topics": ["   "]}],
        [{"name": "Algebra", "start_page": 1, "topics": ["Linear", " linear "]}],
        [{"name": "Algebra", "start_page": 1, "topics": ["x" * 241]}],
    ],
)
def test_import_rejects_invalid_outline_metadata(
    auth_client: tuple[TestClient, dict[str, str]],
    outline: list[dict[str, object]],
) -> None:
    client, tokens = auth_client

    response = upload_official_book(client, tokens["admin"], outline=outline)

    assert response.status_code == 422


def test_import_rejects_whitespace_only_catalog_names(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client

    response = upload_official_book(client, tokens["admin"], book_name="   ")

    assert response.status_code == 422
    assert "metadata are required" in response.json()["detail"]


def test_official_import_requires_admin_and_rights_confirmation(
    auth_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, tokens = auth_client
    not_admin = upload_official_book(client, tokens["teacher"])
    no_rights_confirmation = upload_official_book(client, tokens["admin"], rights_confirmed="false")

    assert not_admin.status_code == 403
    assert no_rights_confirmation.status_code == 422
    assert "permission" in no_rights_confirmation.json()["detail"].lower()


def test_ocr_extracts_text_from_scanned_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)

    class FakePage:
        def render(self, scale: float) -> object:
            return SimpleNamespace(to_pil=lambda: object())

    class FakeDocument:
        def __getitem__(self, index: int) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    pdfium = ModuleType("pypdfium2")
    pdfium.PdfDocument = lambda pdf_data: FakeDocument()  # type: ignore[attr-defined]
    tesseract = ModuleType("pytesseract")
    tesseract.image_to_string = lambda image, lang: "Chapter 1 Algebra"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypdfium2", pdfium)
    monkeypatch.setitem(sys.modules, "pytesseract", tesseract)

    pages, ocr_used = _extract_pages(output.getvalue(), use_ocr=True)

    assert pages == ["Chapter 1 Algebra"]
    assert ocr_used


def test_ai_generation_uses_and_cites_matching_official_book_content(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, tokens = auth_client
    imported = upload_official_book(client, tokens["admin"])
    assert imported.status_code == 201
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                [
                                    {
                                        "question": "What do linear equations describe?",
                                        "options": [
                                            "Equality between expressions",
                                            "A curved graph",
                                            "An unrelated quantity",
                                            "No mathematical relationship",
                                        ],
                                        "correct_answer": "Equality between expressions",
                                        "explanation": (
                                            "The textbook defines their equality relationship."
                                        ),
                                        "difficulty": "medium",
                                        "topic": "Linear equations",
                                    }
                                ]
                            )
                        }
                    }
                ]
            }

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr("app.ai_service.httpx.post", fake_post)
    response = client.post(
        "/api/ai/generate",
        headers={"Authorization": f"Bearer {tokens['teacher']}"},
        json={
            "curriculum": "Punjab Board",
            "subject": "Mathematics",
            "book": "Mathematics 9 (2026)",
            "chapter": "Algebra",
            "topic": "Linear equations",
            "question_type": "mcq",
            "count": 1,
        },
    )

    assert response.status_code == 200, response.text
    assert (
        "Linear equations describe equality" in captured["kwargs"]["json"]["messages"][1]["content"]
    )  # type: ignore[index]
    assert response.json()["sources"] == [
        {
            "book": "Mathematics 9 (2026)",
            "chapter": "Algebra",
            "page": 1,
            "source_name": "Taleem360",
            "source_url": "https://www.taleem360.com/9th-class-math-em-new-punjab-text-book-2026-pdf",
        }
    ]


def test_official_content_needs_configured_ai_provider_for_grounded_generation(
    auth_client: tuple[TestClient, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, tokens = auth_client
    assert upload_official_book(client, tokens["admin"]).status_code == 201
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    response = client.post(
        "/api/ai/generate",
        headers={"Authorization": f"Bearer {tokens['teacher']}"},
        json={
            "curriculum": "Punjab Board",
            "subject": "Mathematics",
            "book": "Mathematics 9 (2026)",
            "chapter": "Algebra",
            "topic": "Linear equations",
            "question_type": "mcq",
            "count": 1,
        },
    )

    assert response.status_code == 503
    assert "grounded" in response.json()["detail"]
