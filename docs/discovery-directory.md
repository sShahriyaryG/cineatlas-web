# Dedicated discovery directories

This feature exposes CineAtlas's existing enriched database through read-only
archive pages. It requires migration `0007_person_enrichment` (already present
in the previous feature), but does not introduce a migration, download metadata,
change dependencies, or add any movies.

## Navigation and interface

The signed-out homepage still has its original hero and film index; signed-in
Home remains the personalized dashboard. Explore retains the film search and
adds an archive navigation bar:

| URL | Contents |
|---|---|
| `/discover` | Existing film index, search and filters |
| `/discover/people` | Alphabetical people directory with profile photos, roles and distinct film counts |
| `/discover/genres` | Genres attached to local films |
| `/discover/countries` | Production countries attached to local films |
| `/discover/languages` | Original, spoken and unspecified catalog languages attached to local films |
| `/discover/tags` | Tags attached to local films |
| `/discover/{genres,countries,languages,tags}/{id}` | Films associated with the selected classification |
| `/people/{id}` | Expanded person page and existing filmography |
| `/movies/{id}` | Expanded film page, credits, reviews and personal actions |

All classification links use stable integer catalog IDs, not names or codes.
A person or movie card is a normal anchor with internal history navigation and
also supports opening a new tab. Directory queries and pagination are retained
per directory/classification in memory for the current application/session
boundary. Signing out or switching accounts discards that state. The existing
back-navigation and scroll-position handling is retained; exact scroll
restoration remains best effort when results/images are loaded asynchronously.
Directory page/query state is not serialized into the URL or persisted after a
reload.

People can be searched by display name or recorded alternative name and filtered
by any supported credit role. Role filtering selects people but cards still
show all their roles and total distinct films in the local catalog. The global Films index and each classification's film list share the same
search fields, sort order and filter controls. A classification page always
intersects its selected classification with the other filters; Reset all
clears only the additional filters, not that page's scope. The top-level
People and classification directories still search people and classification
names respectively. Cross-entity unified search and NOT filters are planned
separately.

Genres, languages, production countries and tags each support multiple
selections (all or any within the group); different groups combine with AND.
Language filters match all recorded language types, counting a film once.
Classification options are searchable and use stable IDs except for the
existing name-based genre filter. The API caps each group at 20 selections.

Page sizes follow the measured content width using ResizeObserver and a common
column calculation for the API limit and rendered grid: two full rows for
film lists, four for people and classification lists. For example, seven film
columns request 14 items. The final page may be partially filled; the API
never returns more than 50 entries. On a viewport resize, the new page is
computed from the prior start offset so that it still contains the previous
first item's position, when possible.

The layout uses the Modern Cinematheque theme tokens and existing breakpoints,
with a six-section navigation bar, portrait grid and simple classification
cards. Missing or failed profile images fall back to initials and a person
icon; no additional image assets are bundled. Remote profile images are loaded
on demand. Movie detail pages display original/alternative titles, a single release fact (date if known, scheduled date for future releases,
status fallback or exceptional status if relevant), separate language types, production countries, tags and
country-specific certifications. Safe HTTP(S) trailer, soundtrack and quote
source links open in a separate tab. Soundtrack and quotation sections appear
only when populated. Spoiler quotations stay collapsed by default (a UI spoiler
control, not an access control mechanism). Person profiles show available
birth/death dates, birthplace, full name, alternative names and nationalities
alongside biography and grouped filmography. Unknown optional fields remain
hidden. Calendar dates are formatted in UTC to avoid timezone-day shifts.

Movie and person metadata load independently; errors do not remove the core
film/profile page, and each failed metadata request can be retried. The
resource hook guards against out-of-date response snapshots and aborts requests
on navigation/unmount. Existing watchlist, rating, review and admin/editor
operations remain in place.

## API

Public read-only endpoints (no token required):

- `GET /api/directory/people?q=&page=1&size=24`: returns
  `{items, total, page, size}`. Each item includes `id`, `name`, `profile_url`
  (nullable), `roles` and `film_count`. `role` is optional; omit it for all
  roles. Name queries also match alternative names. Queries treat SQL wildcard
  characters literally.
- `GET /api/directory/classifications/{category}?q=&page=1&size=24`:
  category is `genres`, `languages`, `countries` or `tags`. Each result has
  `id`, `name`, `film_count`. Only vocabulary entries linked to films appear.
- `GET /api/directory/classifications/{category}/{classification_id}?page=1&size=12`:
  returns `{classification: {id, name}, items, total, page, size}`; film items
  use the existing movie response format including aggregate community ratings.
  Accepts the same search, sort and filter parameters as `/api/movies`.
  Missing IDs return 404; an existing classification with no films returns an
  empty page. Unsupported categories and invalid query parameters return 422.

- `GET /api/directory/filter-options`: returns arrays of `{id, name}` for
  `genres`, `languages`, `countries`, and `tags`, limited to classifications
  associated with films. Both movie search routes accept repeatable
  `language_ids`, `country_ids`, `tag_ids` parameters plus `language_mode`,
  `country_mode`, `tag_mode` (`and` or `or`, default `and`).

Page size is restricted to 1–50 and page number to 1–100000. Text is capped at
200 characters. Sorting is case-insensitive name/title then stable ID. Language
counts are distinct movie counts: a film linked as both original and spoken
English counts once. Similarly, several roles in one film count as one film for
that person's directory card. Country browsing is exclusively by production
country, not certifications, nationalities, or locations. Hence country and
language directory totals may differ from counts of vocabulary tables.

Existing endpoints remain compatible with additive properties:

- `GET` and `PATCH /api/movies/{movie_id}/metadata` now both include
  `classifications: {genres, languages, countries, tags}`, each an array of
  `{id, name}` (languages also include `kind`). The legacy name-based fields are
  retained; the new IDs are response-only, not additional PATCH input fields.
- `GET /api/movies/{movie_id}/credits` adds nullable `profile_url` to each credit.
  Photos are fetched in one batched SQL query rather than per card. Write
  endpoints and the original `/api/persons` endpoint retain their contracts.

The new API queries use SQL pagination, aggregation and existing foreign keys.
They do not merge vocabulary aliases or rewrite compound legacy values; those
remain scheduled for administrator vocabulary management. No automatic
nationality inference, metadata refresh or new provider requests are performed.

## Verification

From the project root:

```powershell
docker compose up -d --build api web
docker compose exec api alembic current
docker compose exec api pytest -q
docker compose exec web node --experimental-strip-types --test tests/*.test.mjs
docker compose exec web npm run build
```

Expected revision: `0007_person_enrichment (head)`. New tests exercise literal
search, alternative names, roles, distinct counts, pagination, photo projection,
classification membership, missing/empty results and invalid parameters. The
existing CI smoke test additionally exercises directory queries and community
ratings on a migrated disposable database; never point it at your live catalog.

Browser acceptance: visit each directory in guest and signed-in sessions,
search people by name/alias, filter role, paginate and follow links, use Back
from a person and classification, check valid and missing classifications,
verify movie and person metadata with both appearance modes and small viewport,
check portrait fallback and optional sections, and verify watchlists,
ratings, reviews, editor/admin routes and legacy film search. A test record may
be used for soundtrack and spoiler quotes; don't add fictional fields to real
films just to exercise the UI.

## Discovery refinements verification

Verify the shared search on a genre, country, language and tag detail page,
combine filter groups on the global film index, and confirm that resetting
filters on a classification page retains the classification. Resize the
window and check full rows on all non-final pages and correct last-page
counts. Check release dates without a duplicate Released status, future
scheduled dates and status-only records. No new migration or npm dependency
is needed.
