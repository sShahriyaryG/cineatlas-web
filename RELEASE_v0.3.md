# CineAtlas v0.3 — review reporting and release checks

Apply this patch on top of the previous v0.3 Admin Studio upgrade, which you have already browser-tested. It adds the missing reporting UI, trims report reasons on the server, adds API regression coverage and includes the Vite environment type declaration. It does not modify the database schema, Docker configuration, dependencies, or package metadata (the frontend npm package still displays 0.2.0 to avoid invalidating the dependency-install layer). The Git release tag will be v0.3.0.

## Install (Windows PowerShell)

1. Back up any uncommitted local source changes. Extract the ZIP into the existing `W:\uni\github\cineatlas-web` folder (where `compose.yaml` is), replacing matching files. Do not overwrite custom edits without comparing them first.
2. Start Docker Desktop, then run:

```powershell
docker compose up -d --build api web
docker compose exec api pytest -q
docker compose exec web npm run build
docker compose ps
```

Expect seven passing backend tests and a successful TypeScript/Vite build. No migration is required. Existing sessions may expire on backend restart; sign in again. Do not run `docker compose down -v`.

## Browser acceptance checks

1. As a guest, open a movie with a visible review. Click **Sign in to report** and verify the login prompt opens. Sign in with a regular test user or editor.
2. Open **Report review** under a visible test review. The inline form should open and focus the reason. Confirm that a reason shorter than five characters (or whitespace only) cannot be submitted; try Cancel, then reopen.
3. Enter a valid reason, e.g. `Browser test: unmarked spoiler`, and submit. Confirm a success message appears and the review remains publicly visible. The same open review view will not allow a second submission after success.
4. In an administrator session, open **Admin → Reports** (refresh if necessary). Verify the new pending report contains the expected reporter, review and reason. Dismiss it and verify the review remains visible.
5. Report a different test review, hide it as admin and confirm it disappears after refreshing the public movie details.

A persistent duplicate-report constraint, review restoration and a moderation audit log remain future work. The patch's backend tests passed using SQLite; full frontend compilation and browser checks must be performed locally. v0.3 remains a development MVP rather than a public production deployment.

## Publish after all checks pass

Inspect the working tree and staged diff; don't publish legacy archives, private data, or secrets. If you've already committed some of these files, Git will simply stage any new changes. Run:

```powershell
git status --short
git diff --check
git add README.md UPGRADE_v0.3.md RELEASE_v0.3.md backend/app/main.py backend/app/models.py backend/tests/test_api.py frontend/src/main.tsx frontend/src/Console.tsx frontend/src/ReviewReport.tsx frontend/src/style.css frontend/src/vite-env.d.ts
git diff --cached --check
git diff --cached --stat
git status --short
```

Inspect `git diff --cached` before committing. Verify only intended changes are staged. Then:

```powershell
git commit -m "Complete v0.3 admin, editor and review reporting workflows"
git push origin main
```

If successful, optionally create a release tag (only if it does not already exist):

```powershell
git tag -a v0.3.0 -m "CineAtlas v0.3.0"
git push origin v0.3.0
```
