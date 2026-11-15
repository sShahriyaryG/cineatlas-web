# CineAtlas · Full-stack movie discovery (v0.2)

A modern web redevelopment of the IMDb-style Python; my university assignment.

## Stack

- React 19 + TypeScript + Vite (responsive dark-themed frontend)
- Python FastAPI, SQLAlchemy 2, Argon2id password hashing
- PostgreSQL 17 + Alembic migrations (SQLite available for no-Docker development)
- Pytest + FastAPI TestClient

## Run with Docker (recommended)

Install Docker Desktop, then from this folder:

```bash
docker compose up --build
```

Visit **http://localhost:5173**. API docs: **http://localhost:8000/docs**.

To import movie metadata from the original uploaded ZIP without copying accounts or insecure password hashes:

```bash
docker compose cp /path/to/40131849.zip api:/app/legacy.zip
docker compose exec api python import_legacy.py /app/legacy.zip
```

Refresh the web page. The importer is idempotent by legacy UUID, but _imported user-authored movie content is not verified_; review it before sharing a public deployment.

### Local development without Docker

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python import_legacy.py /path/to/40131849.zip
uvicorn app.main:app --reload
```

Default SQLite database is `backend/cineatlas.db` for fast local experimentation; Docker uses PostgreSQL. Run frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Access `http://localhost:5173`.

### First admin account

Register normally, then execute locally in `backend/`:

```bash
python create_admin.py YOUR_USERNAME
```

or `docker compose exec api python create_admin.py YOUR_USERNAME`. Sign out and sign in again if needed. Never expose this CLI to untrusted users.

## Working features in this version

- Register, login, logout; Argon2id password hashes and temporary opaque auth tokens
- Browse movies, search title/plot, genre/year filters, pagination and sorting
- Movie details and community reviews, spoiler reveal, movie ratings 1–10
- Personal watchlist, genre-based recommendations from highly rated movies
- Editor-submitted synopsis change proposals; admin approval/rejection
- Review reporting and admin hide/dismiss moderation through API
- Admin CRUD movie endpoints and statistics through API
- CSV movie importer (does **not** migrate original users, password hashes or social records)

## Tests

```bash
cd backend
pytest -q
```

## Release limitations / next steps

This is a functional **development MVP**, _not_ the full specification and _not_ production-ready.

- The frontend still needs dedicated admin/editor dashboards and multi-list management.
- Full movie/person/cast and crew relationships, follows, activity feeds, notifications, review voting, and advanced Boolean search are not yet implemented.
- Tokens are currently stored in process memory, expire after 7 days, and are invalidated on server restart. Implement durable session persistence and rate-limiting before public deployment.
- Improve CSRF/security strategy if introducing cookies; add email verification, password reset, audit logs, backup policy, image hosting, and accessibility QA.
- No third-party movie content is automatically fetched; importer retains your original movie data. Movie posters are optional external URLs.
- Alembic initial migration is present; review and create further migrations when modifying schemas. Existing app creation at lifespan is a dev convenience and should be disabled in production.
- The tests focus on API workflows and do not replace browser end-to-end, load or security tests.

## Project structure

```
backend/
  app/{db,models,security,main}.py
  alembic/versions/0001_initial.py
  tests/test_api.py
  import_legacy.py
  create_admin.py
frontend/
  src/{main.tsx,style.css}
compose.yaml
```

### API

All endpoints have an interactive schema at `http://localhost:8000/docs`.
