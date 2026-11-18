# Application shell and personal dashboard

The Modern Cinematheque layout now has a shared desktop navigation rail, a wrapping mobile navigation strip, a quiet account/appearance header, and a main content region. The interface uses the existing semantic theme tokens. Only implemented destinations are displayed; new discovery directories, community, profiles and notifications will be integrated in later milestones.

## Routes and access

| Path | View |
| --- | --- |
| `/` | Signed-in dashboard, or guest discovery with the public hero |
| `/discover` | Film index with the existing advanced search and filters |
| `/library`, `/watchlist` | Watchlist (legacy URL remains valid) |
| `/library/ratings` | Private personal ratings |
| `/for-you` | Existing genre-based recommendations |
| `/movies/:id`, `/people/:id` | Existing detail views |
| `/editor`, `/admin` | Role-restricted management workspaces |

The root waits for authentication verification if a session identifier exists. Sign-in, logout, expiry and account switching continue to reset the session scope and root route. The new views share the existing scope-bound API request wrapper. Old account data cannot populate a new session through delayed requests. The explicit detail-page fallback goes to `/discover` rather than the signed-in dashboard. History and search state remain in memory and preserve the existing best-effort scroll restoration.

The management links are displayed only for the appropriate verified roles. UI link visibility is not a security boundary: the existing server-side role and session checks remain authoritative.

## Library and dashboard data

Home displays counts from the existing watchlist and rating records, a preview of the current recommendations, and a watchlist preview. Unknown/loading/error counts use an em dash, not a fabricated zero. Preview ordering is not claimed to represent a watch history, a recently added list or a popularity ranking. The Library separates watchlist and personal ratings into shareable routes. It does not create custom collections or watched history; these remain separate upcoming features. Watchlist operations remain on the movie page.

`GET /api/me/ratings` is a new read-only, authenticated endpoint. It returns a movie array ordered by title then movie ID, with a `my_score` integer (1–10) for the authenticated account. Community rating/count fields retain their existing meanings. The query joins the user's own rating rows with a grouped community summary. The existing API no-store middleware applies; no public movie endpoint includes `my_score`. The endpoint never accepts a user ID from the caller. Existing movie rating changes already trigger a catalog revision, which reloads the private ratings, watchlist and recommendations. This release does not change how recommendations are ranked: users without qualifying ratings receive the existing fallback selection.

No database migration or new dependency is required. The backend API and frontend must both be rebuilt to enable the ratings endpoint and new shell. Existing authenticated sessions and catalog/user records should survive the rebuild because the persistent session tables are unchanged.

## Verification

From the project root:

```powershell
docker compose up -d --build api web
docker compose exec api alembic current
docker compose exec api pytest -q
docker compose exec web node --experimental-strip-types --test tests/*.test.mjs
docker compose exec web npm run build
```

Expected: `0005_session_security`, 71 backend tests, 31 frontend logic tests and a successful build. CI also exercises the new ratings endpoint through the disposable PostgreSQL smoke job. Never run that smoke script against a live/occupied database.

Development verification: all 71 backend tests passed using SQLite; all 31 frontend logic tests passed using Node 22. The isolated SQLite migration/API smoke test passed. Pure TypeScript route/shell helpers passed strict checking, and source modules passed transpilation syntax checks. 60 representative static HTML fixtures passed document-width overflow checks in Chromium (dashboard, library, discover, movie, admin at 320, 390, 768, 801, 1024 and 1440px in both themes). Those fixtures are not an integrated React build or full browser acceptance tests. React dependencies were unavailable in the patch environment; a production frontend build and live PostgreSQL verification are pending.

Manual verification: start signed out and sign in; check that Home uses the correct account and counts. Add/remove one saved film, rate and re-rate a film, and check the Library personal score and dashboard counts. Compare two accounts with different lists and ratings. Exercise legacy `/watchlist`, direct library/ratings refresh, Back from movie and person pages, search restoration, and direct-link Discover fallback. Test editor/admin links and direct restricted routes. Try both themes, keyboard focus, small mobile layouts, authentication, password changes and existing review/moderation functions.
