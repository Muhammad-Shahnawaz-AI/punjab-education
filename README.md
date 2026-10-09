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

## Administrator large-PDF library

Administrators can use **Curriculum Books** in the dashboard to add rights-cleared PDFs to the
shared curriculum catalog. The selected grade must belong to the selected subject, and a successful
upload is linked to that existing curriculum hierarchy. Search and AI-generation retrieval ignore
the book until background PDF validation, text extraction, and indexing all succeed.

Uploads use a resumable multipart session rather than one large multipart HTTP request. The browser
reads and hashes one bounded part at a time, retries or resumes missing parts, and reports transfer
progress independently from worker processing progress. The backend verifies each part's length and
SHA-256 digest, verifies the completed object's size and PDF signature, calculates the complete
file's SHA-256 digest, and queues persistent processing state. The worker opens the PDF from disk
and extracts/indexes one page at a time; OCR is attempted only for pages without embedded text.
Encrypted or malformed PDFs and failed OCR remain in an explicit failed state for administrator
retry. Failed retries clear and rebuild only that source's index, avoiding duplicate chunks.

### Local development

Use the local storage adapter for development. Its root is private (mode `0700` where supported),
and upload parts and final PDFs are written to disk rather than buffered into a database row or a
complete in-memory byte string. Completion temporarily needs room for both the incoming parts and
the assembled PDF. The default per-PDF maximum is 20 GiB, default part size is 8 MiB, and the
default limit is three active uploads per administrator; these are operational quotas, not unlimited
capacity. Configure lower values to match available disk, worker memory, and database capacity.

```bash
cd backend
cp .env.example .env  # load the values into your shell or local environment manager
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In a second terminal, from `backend/`, start the persistent processing worker:

```bash
python -m app.book_worker
```

When OCR is required, install the system Tesseract executable and the desired trained language data
(for example `tesseract-ocr` with `tesseract-ocr-eng` and/or `tesseract-ocr-urd` on Debian-based
systems), set `OCR_ENABLED=true`, and select OCR and the matching language in the admin form. Python
OCR/PDF dependencies are in `backend/requirements.txt`. OCR is off by default.

### Production object storage and worker

Do not use an ephemeral application filesystem as the only production book store. For Render and
other ephemeral or horizontally scaled deployments, configure a private S3 or S3-compatible bucket
and run a continuously available background worker. The static frontend does not receive storage
credentials. The API issues short-lived, object-and-part-scoped presigned upload URLs; configure
the bucket CORS policy to allow `PUT` from the exact frontend origin and the
`x-amz-checksum-sha256` request header. Keep public bucket access blocked.

Set these backend and worker environment values (the worker and API must share the same database and
storage configuration):

```text
STORAGE_BACKEND=s3
S3_BUCKET=<private-bucket-name>
S3_REGION=<bucket-region>
S3_ENDPOINT_URL=<optional-s3-compatible-endpoint>
S3_ACCESS_KEY_ID=<restricted-server-side-key>
S3_SECRET_ACCESS_KEY=<restricted-server-side-secret>
MAX_PDF_SIZE_BYTES=21474836480
MULTIPART_CHUNK_SIZE_BYTES=8388608
MAX_CONCURRENT_UPLOADS=3
MAX_CONCURRENT_PROCESSING_JOBS=1
UPLOAD_SESSION_TTL_SECONDS=86400
OCR_ENABLED=false
```

Use a server-side IAM identity where available instead of long-lived access keys. Its bucket policy
should grant only multipart create/list/complete/abort, object get/put/delete, and the required
bucket-specific actions on the application prefix. No key or presigned URL is permanent. S3
multipart parts must be at least 5 MiB except the final part, no larger than 5 GiB, and a multipart
object has at most 10,000 parts. At the 8 MiB default, the part-count ceiling is roughly 78 GiB,
while the configured 20 GiB operational default is deliberately lower. The API refuses a
maximum-size configuration that cannot fit the selected part size and provider part-count limit.
Choose a part size and book quota appropriate for your provider, available worker scratch disk,
processing timeouts, and budget.

Configure a bucket lifecycle rule to abort incomplete multipart uploads after one day (or another
chosen retention period). Also schedule the application cleanup command for expired local upload
parts and database sessions:

```bash
cd backend
python -m app.book_maintenance
```

Run `alembic upgrade head` as part of deployment before starting the API and worker. The worker
command is `python -m app.book_worker`. The repository's Render Blueprint now defines a separate
Starter Background Worker and prompts for private S3 bucket/credential environment values; this
worker plan is billable, in addition to storage/provider charges. Review the plan and provider
pricing before deploying. The worker must share the API's `DATABASE_URL`, `STORAGE_BACKEND`, `S3_*`,
and OCR configuration. `MAX_CONCURRENT_PROCESSING_JOBS` controls jobs per worker process; size
worker replicas and memory/CPU to the hosting plan. The API applies migrations at startup, and the
worker retries database/claim failures while the API is starting. The free web filesystem is not
durable book storage. A local-storage production deployment must set
`APP_ENV=production`, `LOCAL_BOOK_STORAGE_PERSISTENT=true`, and a durable volume path that is shared
by both API and worker, with enough capacity for uploaded PDFs, temporary assembly and worker
scratch space. This explicit setting is not appropriate for Render's ephemeral free filesystem.

Object storage has provider-specific storage, multipart request, data transfer, and GET costs; the
worker downloads each completed S3 PDF to bounded scratch disk for parser access, then stores
page-numbered searchable chunks in the database. Estimate storage and processing charges using
expected book retention and worker activity; apply bucket quotas and lifecycle/backup policies.
Database text-index growth and worker temporary-disk space are additional capacity limits.

Monitor `processing_status`, `processing_stage`, progress, and `last_error` in the Curriculum Books
admin table. Select **Retry** after fixing the reported cause; OCR can be enabled for a retry without
re-uploading the PDF. If a session expires, begin a new upload. An interrupted but unexpired browser
upload can resume by retrying the same queued file in that browser session; part status is persisted
by the storage provider. If the browser page is closed, reselect the same file and start a new
session. For storage failures, verify bucket CORS/IAM, quota, endpoint, worker scratch space, and
that the worker uses the same database and bucket as the API. Password-protected PDFs are not
supported.

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

This legacy one-request importer remains available for compatibility and is limited to 50 MB and
1,000 pages. For larger books, use the administrator's resumable **Curriculum Books** workflow
above. The personal **My Study Books** feature is still a separate private per-user library with its
existing 20 MB upload limit; this shared curriculum upload workflow does not change its API.

## Next implementation layer
1. Connect generated questions to end-to-end assessment and student-attempt workflows.
2. Build student and teacher modules on the approved curriculum catalog.
3. Replace illustrative dashboard analytics with live assessment and attempt aggregates.
