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

## Run backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Next implementation layer
1. Import the complete Figma screen set and reproduce each screen/component.
2. Add PostgreSQL models for curriculum, users, assessments, attempts and analytics.
3. Add RAG ingestion for approved Punjab curriculum material.
4. Connect an LLM with structured JSON output + validation.
5. Connect frontend API queries and authentication.
6. Add student/teacher/admin workflows and production tests.
