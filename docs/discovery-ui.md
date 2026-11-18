# Discovery UI and navigation

## Routes

CineAtlas uses the browser History API with ordinary anchor links and client-side navigation. The following paths are public unless noted:

| Path | View |
| --- | --- |
| `/` or `/discover` | Discovery, search and filters |
| `/movies/:id` | Movie details, cast/crew, ratings, watchlist and reviews |
| `/people/:id` | Person details and catalog filmography |
| `/watchlist` | Personal saved films (sign-in required for data) |
| `/for-you` | Recommendations (sign-in required for data) |
| `/editor` | Editor Workspace (editor/admin) |
| `/admin` | Admin Studio (admin) |

IDs are positive PostgreSQL integer primary keys. Invalid routes display a not-found view. Existing backend role checks remain authoritative. Movie/person links support normal browser behavior such as opening a new tab, refresh, and back/forward. Vite's development server handles direct route refreshes. Production hosting must serve `index.html` for unknown frontend paths while keeping API and static asset routes separate. Frontend paths assume deployment at the origin root.

Search, filter expansion and pagination state survive navigation within the same in-memory session. The detail-page Back action follows same-session history, with a Discover fallback for direct links. Back/forward scroll restoration is best-effort, especially when a detail page needs to reload. Search state is not encoded in the URL and is reset by a full reload or authentication transition. See [Navigation and session isolation](navigation-session.md) for history boundaries and session behavior.

## Data and interface

Discovery includes up to three recent catalog picks, preferring entries with poster URLs among the newest twelve films. This is not an external popularity ranking. Posters use a consistent 2:3 aspect ratio, with a local initial fallback if an image is missing or fails. Movie details load by ID independently of the previous search results. Rating controls require explicit submission; community review publishing, spoiler disclosure, reporting and watchlist operations retain their existing API endpoints.

Person profiles use existing `persons` and `movie_credits` data. The public `GET /api/persons/{id}` response adds `poster_url` to each credit, without removing existing fields. Filmography entries group credits by movie ID, retain all roles/characters, and preserve the backend's newest-year-first ordering. A person may have no biography or film credits. There are no new external person images, generated biographies, or requests to the TMDB API. Filmographies represent the local catalog and are not exhaustive career histories.

The new view assets are React components and CSS only. No external package or database schema changes are required. Existing admin/editor workspaces keep their functional layout; shared surfaces, typography and navigation are used. The authentication dialog now has Escape handling, a focus loop, focus restoration when possible, and scroll locking.

## Verification

From the project root with Docker running:

```powershell
docker compose up -d --build api web
docker compose exec api alembic current
docker compose exec api pytest -q
docker compose exec web node --experimental-strip-types --test tests/*.test.mjs
docker compose exec web npm run build
```

Expected schema head: `0004_enrichment_sources`. Expected backend suite: 59 passing tests, including two new tests for person filmography data, public linked movie lookup, and missing/empty records. Node 22 runs the frontend logic suite, including three original tests for route parsing and grouping credits (no extra dependency). These tests are not browser end-to-end tests.

Manual verification: open Discovery, search and paginate, open a movie, refresh the deep URL and use the browser back/forward buttons. Open a cast member and navigate from their filmography back to a movie. Test nonexistent movie/person and unsupported routes, poster fallback, sign-in, saving/removing a movie, rating, posting a review, revealing spoilers, and reporting a review. Verify admin and editor access and workflows, attribution, keyboard focus, and narrow-screen layout. Use a test account and a disposable review for write tests; avoid reporting genuine reviews merely for testing. A browser/network devtools offline mode can test error UI; restore it afterward.

## Known limitations

This iteration does not ingest profile photos/biographies, expose a people directory, add URL-based filter state, add frontend dependencies or introduce server rendering. Filmography API results are not paginated; review and cast lists retain their prior backend limits. Person and movie identifiers are local rather than globally stable. Browser visual and accessibility checks remain necessary.
