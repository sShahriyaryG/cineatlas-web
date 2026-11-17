# Movie metadata enrichment

The optional TMDB integration complements the CC0 Wikidata ingestion pipeline with movie synopses, poster URLs, missing runtimes, and cast/crew. It uses the official API, not IMDb scraping, and does not include bundled TMDB movie data or credentials.

## Before using the integration

- Register for a developer API credential in [TMDB account settings](https://www.themoviedb.org/settings/api). Read and accept the current terms only if they suit the intended use. TMDB's developer API is for noncommercial use with attribution; commercial use needs appropriate licensing. Consult the [official FAQ](https://developer.themoviedb.org/docs/faq).
- Download an approved **SVG** TMDB logo from the logos and attribution page linked by that FAQ ([official logos page](https://www.themoviedb.org/about/logos-attribution)). Place the unmodified asset at `frontend/public/tmdb-logo.svg` (create `public` if needed). The footer displays it at a small size alongside the required notice and links. The logo itself is not bundled. A text fallback is shown if the asset is missing, but the approved logo is required before using the live integration. Keep the asset out of the repository unless its terms permit redistribution.
- Never commit your read token, raw TMDB payloads, local database dumps or poster files. The application only stores image URLs, not the artwork binaries. Do not redistribute enriched database snapshots; review applicable terms before public hosting or sharing data. The API token is only used by the backend CLI, not by the React app.

## Run locally

Start with a database backup. Rebuild to apply migration `0004_enrichment_sources` (or a later revision), then check the backend:

```sh
docker compose up -d --build api web
docker compose exec api alembic current
docker compose exec api pytest -q
docker compose exec web npm run build
```

Use a corrected Wikidata CSV with `film` and `imdb` columns. If the previous snapshot is gone, extract a fresh one using the [Wikidata ingestion instructions](data-ingestion.md). A new filename avoids overwriting an existing snapshot. The CSV is only used to map existing Wikidata entities to IMDb identifiers: the enrichment command does not create movies. If the live snapshot has changed, review any unmatched local IDs and snapshot-only IDs before proceeding.

```sh
docker compose exec api python ingest_movies.py fetch --output /tmp/wikidata-for-enrichment.csv --contact https://github.com/sShahriyaryG/cineatlas-web
docker compose exec api python enrich_movies.py /tmp/wikidata-for-enrichment.csv --limit 3 --dry-run
```

At the prompt, paste your **API Read Access Token**, not your account password. Input is hidden in a supported terminal. For noninteractive execution, provide `TMDB_READ_TOKEN` through a secure local secret injection mechanism; never put it into a Git-tracked file or CLI argument. No Docker configuration change is needed for the interactive workflow.

Inspect the JSON report. When satisfied, preview the full catalog; then explicitly apply it:

```sh
docker compose exec api python enrich_movies.py /tmp/wikidata-for-enrichment.csv --dry-run
docker compose exec api python enrich_movies.py /tmp/wikidata-for-enrichment.csv --apply
```

Dry runs fetch live data and simulate the same writes in a transaction that is rolled back. PostgreSQL sequence values can advance even when rows are rolled back. Apply commits once after all selected movies finish; provider/database errors roll back the full batch. Missing/ambiguous/conflicting identities are skipped and included in `issues`. Counts report additions, not total database rows. Repeat the apply command to verify idempotency; new provider data for previously empty fields/roles may cause additional fills in a later run. The default actor limit is 12 per film (`--cast-limit`, 1–50). Crew roles are limited to Director, Writer, Screenplay, Story, and Producer.

Run a single importer at a time without concurrent catalog edits. Calls are sequential, with bounded retry on temporary network errors/HTTP 429 and selected server errors. No automated refresh is scheduled. TMDB payloads are not written to disk. If the API is unavailable or access cannot be obtained, do not circumvent provider restrictions; the base Wikidata catalog remains usable.

## Identity and preservation policy

1. Existing local movie → stored Wikidata QID → CSV IMDb identifier → TMDB `/find` with `external_source=imdb_id`. Reject zero or multiple movie results and require `/movie/{id}` details to agree with both IDs. Skip release-year differences greater than one year, external identity conflicts, and local movies without a Wikidata mapping. No fuzzy title matching.
2. Validate the provider's image configuration and poster path; store only an HTTPS CDN URL at width `w500`. Fill synopsis, poster URL and runtime only when absent. The existing title, year, genres, rating, review, watchlist and manually populated metadata are not overwritten.
3. Map people by TMDB person ID in `person_sources`. Reuse the same external person on different movies. Skip possible clashes with manually created unmapped people rather than guessing identity by name. Preserve existing credit roles as a group. Missing credits can therefore remain if a role is partial or already manually populated. No automatic merge of existing people or changes to biographies.
4. Track external movie IDs in `movie_sources` and imported field/role history in `movie_enrichment_fields`. History denotes the original fill, not the current value after manual edits. Previously enriched then manually cleared fields/roles are not re-created automatically. This is not an audit trail of every edit. No upstream deletion synchronization is implemented.

The existing movie details and credit endpoints expose enriched data. The UI displays posters, synopsis, and grouped cast/crew, with loading/error/empty states for credits. Person pages and dedicated movie routes are future improvements. Imported external ratings are deliberately excluded; CineAtlas ratings remain user-generated.

## Testing

Automated tests use fictional metadata and mocked HTTP responses, covering identity rejection, validation, shared people, transactional rollback, repeat imports, manual edits and additive migrations. No credentials or network access are required for `pytest`. Live provider behavior, PostgreSQL migration, full frontend build, image loading and browser behavior should be verified separately before merging this feature.
