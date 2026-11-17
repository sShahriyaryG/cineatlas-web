# CineAtlas v0.3 — upgrade instructions (Windows PowerShell)

This patch upgrades the *existing* CineAtlas `cineatlas-web` repository. It is not a complete replacement project.

**Changes included:**
- New movie-management dashboard (`Admin`) with create, update, delete and search.
- Editor workspace for synopsis corrections, status tracking and reasons.
- Moderation queues with the content being reviewed.
- Member-to-editor role management and additional server-side permission checks.
- Backend API tests for these workflows.

## Installation

1. Commit or back up any local edits, then open your existing project folder (the one containing `compose.yaml`) in VS Code.
2. Extract **CineAtlas_v0.3_Upgrade.zip** directly **into that folder**, choosing to replace files with the same name. (The archive contains `backend/`, `frontend/`, `README.md` and this guide.) It **does not contain** `backend/Dockerfile`, `compose.yaml`, your secrets or any database files.
3. From PowerShell inside `W:\uni\github\cineatlas-web`, run:

```powershell
docker compose up -d --build api web
docker compose exec api pytest -q
docker compose ps
```

4. Refresh `http://localhost:5173` (Ctrl+Shift+R).
5. If you have not promoted an admin account yet, run the command below using the username of an already registered account:

```powershell
docker compose exec api python create_admin.py YOUR_USERNAME
```

Sign out and sign back in. The navigation should show **Admin** and **Editor**.

## Manual acceptance checklist

- In **Admin > Movies**, create a test movie and find it in **Discover**.
- Edit it and confirm the new synopsis appears in the movie details.
- In **Admin > Members**, promote a second test account to editor.
- Sign into that account and submit a synopsis correction from **Editor**.
- As admin, approve the correction under **Editor proposals** and check Discover.
- Report a review using the API (`POST /api/reviews/{id}/reports`), then verify the **Reports** queue can hide or dismiss it.
- Only after verifying, delete the *test* movie. Deletion removes all its ratings, reviews and watchlist entries permanently.

**Do not run `docker compose down -v`.** That deletes the database volume. The patch makes no database schema changes, so no migration is needed.

## Publish the update

```powershell
git status --short
git diff --check
git add README.md UPGRADE_v0.3.md backend/app/main.py backend/app/models.py backend/tests/test_api.py frontend/src/Console.tsx frontend/src/main.tsx frontend/src/style.css
git commit -m "Add admin studio and editor workflow"
git push origin main
```

## Limits

- This patch is based on the original CineAtlas project you downloaded in this chat. If you subsequently changed `main.tsx`, `main.py`, `models.py` or `style.css`, review or back up your changes before extracting.
- Backend tests passed in the development container used to prepare this patch. The npm dependencies needed for a full frontend build were unavailable here. **Run your Docker frontend build and inspect browser behavior before committing.**
- Admin functionality is for local development; the application is not yet safe for public internet deployment.
