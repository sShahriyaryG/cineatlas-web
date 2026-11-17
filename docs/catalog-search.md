# Catalog search

The public `GET /api/movies` endpoint defaults to title search. Previously,
a search such as `twi` could match a synopsis containing `twist`. Select the
Synopsis or All fields scope to intentionally include such results.

## API contract

All filters combine with AND except the explicitly selected genre matching mode.

| Parameter | Values / behavior |
|---|---|
| `q` | Literal text, up to 200 characters; whitespace-separated terms must all match |
| `mode` | `title` (default), `synopsis`, `actor`, `director`, `all` (titles, synopses, actors and directors) |
| `genre` | Single genre, retained for existing API callers |
| `genres` | Repeated query parameter (up to 20 selected labels), e.g. `genres=Drama&genres=Science%20Fiction` |
| `genre_mode` | `and` (default; every selected genre) or `or` (any selected genre) |
| `year` | Exact release year, retained for existing clients |
| `year_min`, `year_max` | Inclusive release-year bounds (1888–2200) |
| `rating_min`, `rating_max` | Inclusive community average bounds (1–10); unrated movies excluded if either is set |
| `sort` | `relevance` (default), `title`, `newest`, `oldest`, `rating`, `most_rated` |
| `page`, `size` | One-based page (1–100000), page size (1–50; default 12) |

Examples:

```text
/api/movies?q=interstellar
/api/movies?q=christopher%20nolan&mode=director
/api/movies?genres=Drama&genres=Science%20Fiction&genre_mode=and&year_min=2000
/api/movies?rating_min=8&sort=rating
```

Search uses parameterized SQLAlchemy queries with escaped LIKE wildcards (`%`, `_`, `!`).
Genre aliases resolve through the canonical genre vocabulary. Person matching uses
role-scoped relationship existence, so multiple credits cannot duplicate movie cards.
Each text token can match a different allowed field or credited person; this is not
an exact person-identity lookup. `all` does not include writers, producers or character names.

Relevance for title/all search ranks exact title, title prefix, contiguous title
phrase, all tokens in title, and other matching fields. Synopsis search prioritizes
contiguous phrases; actor/director search prioritizes exact names, prefixes and
contiguous name matches. Explicit sort overrides relevance. Alphabetical title
and movie ID break ties. Without a query, relevance falls back to title order.
Rating sorting places unrated films last; rating comparisons use the unrounded
average, whereas displayed ratings retain the existing one-decimal format.

The listing aggregates rating counts and averages once in SQL instead of issuing
an individual rating query for every movie. No schema changes are needed.

## Frontend

Discover has a search scope selector, sort selector, expandable genre/year/rating
filters, removable genre chips, clear search, and reset controls. Changes reset
pagination, and invalid ranges prevent requests until corrected. A 250 ms debounce,
AbortController and stale-response guard prevent old results replacing newer ones.

## Tests and limitations

`docker compose exec api pytest -q` covers title-only regression, scope and
relevance, literal wildcard matching, genre aliases and AND/OR, rating and year
bounds, deterministic pagination, and invalid parameters. The existing suite uses
an isolated SQLite database. Verify live PostgreSQL and browser behavior separately.
Search is a case-insensitive substring/token search, not fuzzy matching or a full-text
index. Unicode case handling depends on database collation; no accent folding is
promised. Large catalogs will require query-plan measurements and appropriate
indexes or full-text search. This feature does not change the movie details layout.
