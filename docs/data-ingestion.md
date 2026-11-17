# Movie catalog ingestion

CineAtlas includes a reproducible, insert-only ETL pipeline for loading film metadata. Its source is [Wikidata](https://www.wikidata.org/wiki/Wikidata:Data_access), whose structured data is dedicated to the public domain under CC0. The pipeline uses a curated list of 60 IMDb title identifiers as lookup keys **in Wikidata**, not IMDb scraping or IMDb data files. It requests English labels with language-independent fallback labels, publication years, genres and durations measured in minutes.

## Run with Docker

Start the application and apply the schema migrations by rebuilding the backend:

```sh
docker compose up -d --build api
docker compose exec api alembic current
```

The head revision should be `0002_movie_sources`. This additive migration creates a provenance table and keeps existing movie IDs, users, ratings and reviews. As with any database migration, back up important data first.

Fetch a CSV snapshot (internet access to `query.wikidata.org` required):

```sh
docker compose exec api python ingest_movies.py fetch --output /tmp/wikidata-films.csv --contact https://github.com/sShahriyaryG/cineatlas-web
```

The contact URL identifies this project in the User-Agent per Wikimedia's access policy. If running a fork, substitute its own repository/contact URL. Fetching does not write to the database. The command refuses to overwrite an existing file; use a new snapshot filename for later fetches. A failed HTTP request is not retried automatically.

Review the import before writing:

```sh
docker compose exec api python ingest_movies.py import /tmp/wikidata-films.csv --dry-run --strict
docker compose exec api python ingest_movies.py import /tmp/wikidata-films.csv --strict
```

In a dry run, `inserted` means **would insert**. Inspect the report and only run the second command once satisfied. If invalid rows are present, strict mode aborts the entire transaction; omit `--strict` only if skipping those rows is intentional. Title/year conflicts are skipped even in strict mode and should be reviewed manually. Repeat the import to verify that `inserted` is now zero. Refresh Discover to see the new records. Actual results depend on Wikidata's coverage and the existing database.

Raw snapshots are useful for reproducibility: retain a copy outside version control (for example, in a locally ignored `legacy/` directory). The container's `/tmp` is not durable when the container is removed. Use `docker compose cp` to save or restore a snapshot.

### Alternative: browser export

If the fetch endpoint is blocked or unavailable, open <https://query.wikidata.org/>, paste the contents of `backend/data/wikidata_films.sparql`, run the query, and export the results as CSV. Copy the downloaded CSV into the API container:

```sh
docker compose cp path/to/wikidata-films.csv api:/tmp/wikidata-films.csv
```

Then run the same dry-run/import commands. If the endpoint cannot be accessed from either environment, postpone the live import; offline tests do not require network access.

## Pipeline design

1. **Extract** — Version-controlled SPARQL query produces a CSV snapshot with headers `film,title,year,genres,runtime,imdb`. The query chooses the earliest reported publication year, groups distinct English genre labels, and uses the minimum valid duration in minutes when several are available.
2. **Transform** — Normalize Unicode and whitespace, validate Wikidata QIDs and field lengths, validate year and runtime ranges, deduplicate genre labels, map common genre names, and fit the current comma-separated genre field. Missing genres/runtime remain empty/NULL. Genre labels that do not fit the 255-character limit are omitted, never split.
3. **Load** — Insert new movie records and their source identifiers in one transaction. A composite primary key on `movie_sources(source, external_id)` enforces source identity uniqueness. Existing source identifiers, repeated input IDs, and matching normalized title/year pairs are skipped. The title/year comparison is a conservative heuristic, not an identity guarantee. No existing row is automatically overwritten, linked, or deleted.
4. **Observe** — JSON reports track input rows, inserts, previously imported IDs, repeated input IDs, possible title/year conflicts, invalid rows, and up to 30 diagnostic messages.

Run one importer at a time. A concurrent uniqueness conflict rolls back the import; this is not a concurrent ingestion service. Importing a source record again after it has been deliberately deleted from the catalog may recreate it. The provenance records store the source and QID, not a complete source snapshot or revision history; retain the input CSV separately for an exact replay. The API and admin UI keep their existing movie representation.

## Data scope and licensing

This is a starter selection, not a comprehensive or ranked catalog. Wikidata records can be incomplete or inaccurate and can change over time. The query intentionally does not fetch posters, plot summaries, ratings, or external user data. Missing metadata stays missing instead of fabricated. Wikidata's CC0 data terms do not automatically cover images or third-party sites linked from Wikidata. Posters and richer metadata require a separate rights-aware integration.

## Tests

```sh
docker compose exec api pytest -q
```

The ingestion tests use fictional records and mocked HTTP responses so that network failures cannot make the test suite flaky. They exercise normalization, missing values, duplicate detection, source identity, dry runs, strict transaction rollback, existing data preservation, migrations, CLI behavior and catalog/API integration. The live source and PostgreSQL deployment must also be verified in a running environment.
