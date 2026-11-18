# Continuous integration

CineAtlas uses `.github/workflows/ci.yml` to check changes on GitHub-hosted Linux runners. The workflow runs on branch pushes, pull requests targeting `main`, and manual dispatch (available once the workflow is on the default branch). Push and pull request events may run separately for the same change. New runs cancel older runs of the same event and ref.

## Jobs

| Check                                    | Environment                  | Purpose                                                                                             |
| ---------------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------- |
| Backend tests                            | Python 3.12, isolated SQLite | Run all pytest regression tests, including mocked ingestion and enrichment requests.                |
| Frontend tests and build                 | Node.js 22                   | Run the Node logic tests, TypeScript compilation, and Vite production build.                        |
| PostgreSQL migrations and API smoke test | Python 3.12, PostgreSQL 17   | Run the real migration chain on a fresh service database; check schema, backfill, and API behavior. |

The pytest fixture explicitly selects SQLite. The PostgreSQL job therefore uses the separate `backend/ci/database_smoke.py` module instead of assuming pytest will use the service database.

## Database check

The smoke script requires an explicit `DATABASE_URL` and refuses a non-empty database. CI additionally passes `--require-postgresql` to reject SQLite. It migrates an empty database to revision `0002_movie_sources`, inserts one synthetic legacy film, upgrades to the current head, and repeats the upgrade. Before starting the API, it checks table columns, the Alembic revision and `alembic check` for model/schema drift. It then checks normalized genres, title versus synopsis matching, director search, filmography, registration, ratings, rating filtering, and watchlist behavior using FastAPI TestClient.

**Never run it against your application or production database.** It deliberately leaves synthetic test records and schema in its input database. Use a newly created disposable database for each run; GitHub automatically removes the PostgreSQL service at the end of the job. The service password in the YAML is a throwaway CI password, not a secret or a local development credential.

## Local regression checks

From the project root with Docker running:

```powershell
docker compose exec api python -m pytest -q
docker compose exec web node --experimental-strip-types --test tests/*.test.mjs
docker compose exec web npm run build
```

After pushing your branch, check the repository's **Actions** tab and inspect the logs for each of the three jobs. The PostgreSQL smoke check runs on GitHub without touching your local Docker volume. Do not run the smoke module with the normal Compose `DATABASE_URL`.

## Dependency caching and security

- pip downloads are cached using `backend/requirements.txt`.
- If a committed `frontend/package-lock.json` exists, use `npm ci` and cache npm downloads against that lockfile. Otherwise use `npm install` with no npm cache; that fallback does not guarantee reproducible dependency versions. Commit a reviewed lockfile in a follow-up to make frontend installs deterministic. Python dependency ranges remain unresolved until install time.
- Workflow permissions are read-only (`contents: read`), checkout does not persist Git credentials, and every job has a 15-minute timeout.
- The workflow uses `pull_request`, not `pull_request_target`; no repository secrets, TMDB token, local database snapshot or live Wikidata/TMDB call is required by the tests.
- Official GitHub-maintained actions use major-version tags; pinning reviewed commit SHAs is an additional supply-chain hardening step for the future.
- This workflow does not deploy anything. It checks source code and build output; it does not replace browser acceptance, full PostgreSQL regression, load or security tests.

## Status badge

Add the following Markdown immediately below the README heading if it is not already present:

```markdown
[![CI](https://github.com/sShahriyaryG/cineatlas-web/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sShahriyaryG/cineatlas-web/actions/workflows/ci.yml)
```

The badge reports CI for `main`, so it may not show a passing result until the first successful main-branch run.

## Merge policy

Wait for all three jobs to pass on the pull request before merging. CI does not automatically enforce this policy; after the workflow has run, the repository owner can configure a branch ruleset or protection rule for `main` requiring the three named status checks. Configure the policy separately from this patch to avoid blocking the first workflow merge. Do not mark checks as required until GitHub has recorded their names.
