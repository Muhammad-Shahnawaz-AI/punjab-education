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

## GitHub Pages static preview

The standalone, API-free demonstration is in [`static-version/`](static-version/). It is separate
from the Next.js frontend and FastAPI backend; account access, live curriculum, generation,
assessments, and analytics are not available in this preview. The `Deploy GitHub Pages` workflow
publishes this directory on pushes to `main`. In the repository settings, set **Pages → Build and
deployment → Source** to **GitHub Actions**. The project site is
`https://muhammad-shahnawaz-ai.github.io/punjab-education/`.

## Deploy the application on Render with Neon

The GitHub Pages site is only a static preview. The interactive Next.js frontend and FastAPI
backend can be deployed together on Render; the backend uses Neon PostgreSQL. The root
[`render.yaml`](render.yaml) defines both Render services and their connection.

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
4. In the Render dashboard, open the API service's **Shell** and run
   `python -m app.bootstrap_admin` once to create the initial admin account. After it succeeds,
   remove `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` from the API service's environment
   variables.
5. Verify the API at `<API service URL>/health`, then open the frontend and sign in with the
   bootstrap administrator account. Set the public GitHub Pages source independently if you want
   to keep the static preview online.

The API applies Alembic migrations on startup. The Render free web service may spin down when
inactive, so its first request after a quiet period can take longer. This project currently includes
the application screens, authentication, curriculum endpoints, and database schema, but AI
generation is still a placeholder and some dashboard/analytics values are illustrative.

## Run backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Database and sample catalog

The backend defaults to local SQLite. Set `DATABASE_URL` to a PostgreSQL URL for a hosted database.
Create the schema and optionally load the explicitly non-official placeholder catalog:

```bash
cd backend
alembic upgrade head
python -m app.seed_sample
```

The seed is safe to rerun and contains only generic `Sample ...` labels, marked as placeholder data.
It is not Punjab curriculum content. Catalog endpoints start at `/api/curriculum`, then follow
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

## Next implementation layer
1. Import the complete Figma screen set and reproduce each screen/component.
2. Add PostgreSQL models for curriculum, users, assessments, attempts and analytics.
3. Add RAG ingestion for approved Punjab curriculum material.
4. Connect an LLM with structured JSON output + validation.
5. Connect frontend API queries and authentication.
6. Add student/teacher/admin workflows and production tests.
