# Punjab Education Intelligence Platform — First Cut

## Included
- Responsive Next.js + TypeScript frontend inspired by the supplied visual direction: rounded cards, pastel academic palette, compact navigation, dashboard-first UX.
- FastAPI backend scaffold with curriculum and AI-generation contracts.
- Clear separation for future PostgreSQL, vector/RAG and LLM integrations.

## Run frontend
```bash
cd frontend
npm install
npm run dev
```

## Deploy the application on Render with Neon

The interactive Next.js frontend and FastAPI backend can be deployed together on Render; the
backend uses Neon PostgreSQL. The root [`render.yaml`](render.yaml) defines both Render services
and their connection.

1. In Neon, rotate the database password if the connection string has been shared, then copy a
   fresh PostgreSQL connection string from **Connect**. Keep it private.
2. In Render, choose **New → Blueprint**, connect this GitHub repository, and deploy the Blueprint.
   When prompted for `DATABASE_URL`, provide the new Neon connection string. Also provide a
   bootstrap administrator email and a strong password of at least 12 characters. Render generates
   the JWT signing key for you.
3. Wait for both services to deploy. The frontend is served at
   `https://punjab-education-web.onrender.com`; the API is at the URL Render assigns to
   `punjab-education-api`. If Render requires different service names because those names are
   already in use, update the frontend URL in the API service's `CORS_ORIGINS` setting to match.
4. To initialize the database on Render's free plan (which does not provide Shell access), add
   `DATABASE_URL`, `BOOTSTRAP_ADMIN_EMAIL`, and `BOOTSTRAP_ADMIN_PASSWORD` as GitHub Actions
   repository secrets, then run **Actions → Initialize production database → Run workflow** on
   `main`. Use the Neon PostgreSQL connection string for `DATABASE_URL`. After the workflow
   succeeds, remove all three GitHub secrets and remove the two `BOOTSTRAP_ADMIN_*` variables from
   the API service's environment.
5. Verify the API at `<API service URL>/health`, then open the frontend and sign in with the
   bootstrap administrator account.

The API applies Alembic migrations on startup. The Render free web service may spin down when
inactive, so its first request after a quiet period can take longer. The unauthenticated landing
page is a read-only preview: it shows live curriculum catalog counts only. Management operations and
private data remain behind authentication.

## Run backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Database and curriculum catalog

The backend defaults to local SQLite. Set `DATABASE_URL` to a PostgreSQL URL for a hosted database.
Create the schema:

```bash
cd backend
alembic upgrade head
```

Sample fixtures are used only in isolated tests; sample-marked curriculum rows are hidden from the
catalog and dashboard. The repository does not bundle official textbook data. Import approved,
rights-cleared books through the admin curriculum importer. Catalog endpoints start at
`/api/curriculum`, then follow
`/api/curriculum/{code}/grades`, `/api/grades/{id}/subjects`, `/api/subjects/{id}/books`,
`/api/books/{id}/chapters`, and `/api/chapters/{id}/topics`.

## Authentication setup

Configure a signing key of at least 32 characters before using authentication. Create the first
administrator from environment variables; public registration creates student accounts only.

```bash
cd backend
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export BOOTSTRAP_ADMIN_EMAIL="admin@example.org"
export BOOTSTRAP_ADMIN_PASSWORD="<choose-a-strong-password>"
python -m app.bootstrap_admin
```

The password above is a value you provide at runtime, not a repository default. Keep the signing
key and bootstrap password out of source control.

## Public test preview

The homepage and curriculum catalog can be opened without signing in to allow safe link-based
testing. The preview is read-only and does not grant an administrator session. User management,
textbook imports, personal study books, question generation, and other protected APIs still require
an authenticated account with the appropriate role. Do not disable API authorization for public
testing.

The public curriculum page links to Literaria Education Foundation's PCTB e-book directory.
Those linked PDFs remain hosted by their source and are not copied into this project; only import
textbooks after confirming permission or an appropriate open license.

## Personal PDF study library

Signed-in students, teachers, and administrators can open **My Study Books** to upload PDFs, keep
them in a private library, preview or remove them, and ask study questions grounded in their selected
books. PDFs and page-numbered extracted text chunks are stored in the configured database, so the
library survives service restarts and is scoped to the uploading user. Uploads are limited to
text-based PDFs up to 20 MB and 1,000 pages; scanned/image-only PDFs need OCR before upload.

To enable AI answers, configure these variables on the backend service (for Render, use the API
service environment settings):

```text
LLM_PROVIDER=openai
LLM_MODEL=<provider-supported-model>
LLM_API_KEY=<secret-configured-out-of-band>
LLM_BASE_URL=https://api.openai.com/v1
```

`LLM_BASE_URL` is optional for the default OpenAI API and may point to an OpenAI-compatible HTTPS
provider. Keys remain server-side. If the provider is unconfigured or unavailable, the study chat
returns an explicit error instead of fabricating an answer. The retriever passes selected-book
excerpts to the provider and includes book/page citations in the response.

## Importing approved curriculum textbooks

Administrators can import a PDF into the shared Punjab curriculum catalog at
`POST /api/curriculum/books/import` using multipart form fields for curriculum, grade, subject,
book, source name and HTTPS source URL, a documented `rights_basis`, and
`rights_confirmed=true`. Attach the PDF as `file`. The endpoint does not scrape or download
third-party links: first check the publisher's rights/terms and obtain permission or confirm an
appropriate open license before uploading. Recording a source URL is attribution, not a license.

Provide a reviewed `outline` JSON array to map the book into chapters and topics, for example:

```json
[{"name":"Algebra","start_page":1,"topics":["Linear equations"]}]
```

If omitted, the importer detects English/Urdu `Chapter`/`Unit` headings and numbered section
headings where possible; ambiguous layouts require a human-reviewed outline. Imported page text
is stored as searchable chunks and can be queried via authenticated
`GET /api/curriculum/search?q=...`. AI question generation includes matching approved book,
chapter, and topic excerpts and returns source-page references. Real-book generation requires a
configured LLM provider; it fails explicitly rather than describing the local sample generator as
textbook-grounded.

Text-based PDFs are extracted directly. For image-only pages, enable `use_ocr=true`; the backend
also requires the Tesseract executable in the service runtime. Choose `eng`, `urd`, or `eng+urd`
for OCR language; install the matching trained-data packages (such as `tesseract-ocr` and
`tesseract-ocr-urd`) in the deployment image. The Python dependencies are listed in
`backend/requirements.txt`. Imported PDFs are limited to 50 MB and 1,000 pages.

## Next implementation layer
1. Connect generated questions to end-to-end assessment and student-attempt workflows.
2. Build student and teacher modules on the approved curriculum catalog.
3. Replace illustrative dashboard analytics with live assessment and attempt aggregates.
