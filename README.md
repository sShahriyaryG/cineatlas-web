# CineAtlas · Full-stack movie discovery (v0.3)

A full-stack movie discovery and management platform evolved from an IMDb-style Python university project.

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

To import movie metadata from the original legacy ZIP without copying accounts or insecure password hashes:

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

or `docker compose exec api python create_admin.py YOUR_USERNAME`. Sign out and sign in again after promotion. Never expose this CLI to untrusted users. The **Admin** tab will then appear in the website navigation.

## Admin Studio and Editor Workspace (v0.3)

With the website running and an admin account created:

1. Sign in as that admin and open **Admin** from the navigation.
2. In **Movies**, add or edit movie metadata, including genres, runtime, language, country and an optional poster URL. Removing a movie also removes its associated ratings, reviews and watchlists; the browser requests confirmation.
3. In **Members**, promote a registered member to **Editor** (or demote an editor). The member should sign out and sign back in to see their new navigation. Administrator accounts are managed only with the local CLI, not this website panel.
4. Editors see the **Editor** tab; they can search for a movie and submit a proposed synopsis correction, with a reason. The **Your proposals** section shows statuses.
5. Admins can approve or reject editor proposals, inspect reported review content, and hide or dismiss reports. Approved descriptions become visible in the catalog.

Administrative operations are protected by server-side role checks. The admin interface is a development tool, not a substitute for production audit logs or additional hardening.

**Update from an earlier CineAtlas version:** Apply the `v0.3` patch to your existing project directory and run `docker compose up -d --build api web`. No database migration or volume reset is necessary for this update. Your local `.env`, modified `backend/Dockerfile`, and PostgreSQL data should remain intact.

## Report a review

Open any movie with community reviews, sign in, and select **Report review** below a review. Enter a reason (5–1,000 characters) and submit. The report is queued, not automatically hidden. Admins can inspect it under **Admin → Reports** and hide the review or dismiss the report. Guests are prompted to sign in.

## Working features in this version

- Register, login, logout; Argon2id password hashes and temporary opaque auth tokens
- Browse movies, search title/plot, genre/year filters, pagination and sorting
- Movie details and community reviews, spoiler reveal, movie ratings 1–10
- Personal watchlist, genre-based recommendations from highly rated movies
- Editor UI for submitting synopsis change proposals and reviewing their status; admin approval/rejection UI
- Authenticated review reporting directly from movie details, with admin hide/dismiss moderation in Admin Studio
- Admin UI for movie creation/editing/deletion, member-to-editor role changes, moderation queues, and statistics
- CSV movie importer (does **not** migrate original users, password hashes or social records)

## Tests

```bash
cd backend
pytest -q
```

Seven backend tests cover authentication, CRUD, role checks, suggestions, report validation and review moderation. With Docker running, use `docker compose exec api pytest -q` and `docker compose exec web npm run build`.

## Release limitations / next steps

This is a functional **development MVP**, _not_ the full specification and _not_ production-ready.

- Admin/editor dashboards now cover the foundational workflows, but still need better accessibility QA and fully featured user management and multi-list management.
- Full movie/person/cast and crew relationships, follows, activity feeds, notifications, review voting, and advanced Boolean search are not yet implemented.
- Tokens are currently stored in process memory, expire after 7 days, and are invalidated on server restart. Implement durable session persistence and rate-limiting before public deployment.
- Improve CSRF/security strategy if introducing cookies; add email verification, password reset, audit logs, backup policy, image hosting, and accessibility QA.
- No third-party movie content is automatically fetched; importer retains your original movie data. Movie posters are optional external URLs.
- Alembic initial migration is present; review and create further migrations when modifying schemas. Existing app creation at lifespan is a dev convenience and should be disabled in production.
- Duplicate reports are blocked only while a submission is in progress or confirmed in the current open review view; persistent duplicate prevention, restoration and moderation history are not implemented.
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
  src/{main.tsx,Console.tsx,ReviewReport.tsx,vite-env.d.ts,style.css}
compose.yaml
```

### API

All endpoints have an interactive schema at `http://localhost:8000/docs`.
