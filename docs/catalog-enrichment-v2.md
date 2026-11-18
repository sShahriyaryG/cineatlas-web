# Metadata enrichment 2.0

The second enrichment pipeline builds on [movie enrichment](movie-enrichment.md) and [catalog metadata](catalog-metadata.md). It enriches existing linked movies and their credited people, without creating movies, refreshing existing values, changing community ratings or importing provider rating scores. The previous `enrich_movies.py` command remains available for linking an unlinked Wikidata catalog.

## Requirements and installation

- Follow the TMDB noncommercial API and attribution requirements in [movie enrichment](movie-enrichment.md). Keep the approved logo installed; images are stored as CDN URLs rather than downloaded binaries. Do not redistribute provider data or database dumps. Review terms before deploying publicly.
- Back up PostgreSQL before installing migration `0007_person_enrichment` or applying enrichment. Keep the dump outside Git. Rebuild the backend and verify `alembic current` reports the new head.
- Use a single importer process and avoid catalog edits until the batch finishes. A batch holds its database transaction open during sequential API calls. Use small batches if connectivity is unreliable. For maintenance, keep the API stopped and run the CLI using `docker compose run --rm api python ...` (this overrides the service's startup command; ensure migrations were already applied). Alternatively use `docker compose exec api` while the service is running and explicitly avoid other catalog changes.
- No CSV snapshot is required for this command. Existing `movie_sources` TMDB and IMDb links are used; unlinked films need the first-generation importer before this step.

## Commands

From the repository root, in an interactive terminal:

```powershell
docker compose up -d --build api web
docker compose exec api alembic current
docker compose exec api pytest -q
docker compose exec api python enrich_catalog.py --limit 2 --dry-run
```

The token prompt accepts the **TMDB API Read Access Token** with input hidden in a supported terminal. Never put the token in a command argument, repository, screenshots, or chat. Noninteractive use may supply `TMDB_READ_TOKEN` through a secure secret injection mechanism. Reports contain counters and local IDs, not raw provider payloads. Progress goes to stderr.

Inspect the dry-run report. If satisfied, apply the same scope:

```powershell
docker compose exec api python enrich_catalog.py --limit 2 --apply
```

Repeat the same scope as a dry run for idempotency. After verification, process the rest of the catalog in batches, using the `last_movie_id` from the last **successful apply**, not from an interrupted run. For example, if the reported last ID was 37:

```powershell
docker compose exec api python enrich_catalog.py --after-movie-id 37 --limit 5 --dry-run
docker compose exec api python enrich_catalog.py --after-movie-id 37 --limit 5 --apply
```

Replace 37 with your actual checkpoint. Omit `--limit` to select all remaining linked movies. `--cast-limit` accepts 1–50 (default 12) and affects only actor roles not already populated or protected. A repeat import may fill previously unavailable information if the provider changes. Skipped identities may need later review; the next batch's cursor does not automatically retry earlier skips.

Dry runs simulate the import and then roll back all rows (PostgreSQL sequences may advance). On a provider/network/database failure or interruption the whole selected batch rolls back. Successful apply commits once. The preview and apply fetch live data independently and may differ if the upstream records change between runs. Temporary network errors and HTTP 429/selected 5xx responses use the existing bounded retry policy. Requests are sequential with a minimum 200 ms interval between normal request starts. An identity-specific 404 is skipped; authentication errors abort the batch.

## Fields and preservation rules

| Entity | Imported if missing and unprotected |
| --- | --- |
| Film | Synopsis, poster URL, runtime, original title, alternative titles, original and spoken languages, production countries, release date, supported status, keywords as tags, country-specific certifications, official YouTube trailer URL |
| People | Biography, profile URL, birthday, death date, birthplace, alternative names |
| Credits | Actor, director, writer, producer and explicitly mapped composer, cinematographer and editor jobs |

Film identity is checked against both stored TMDB and IMDb IDs. A release year difference over one year is rejected. People use existing TMDB person IDs or new IDs obtained from verified film credits; shared people are queried once per batch. No title/name guessing, automatic person merges or unsupported crew job inference. A name collision with an unlinked manual person is skipped. Existing credit roles are preserved as groups: this importer does not fill a partially populated actor or crew role. Dates must be valid and person birth/death dates consistent and not in the future. Unrecognized status values stay missing. Image paths and trailer keys are validated; trailers are links only.

Language and country names and codes are taken from TMDB's configuration data. Existing normalized names are reconciled by exact case-folded label or existing code. Conflicting code/name associations are not merged; that field is skipped and reported. Existing populated countries and collections are not expanded or overwritten. Compatible legacy unspecified languages can be promoted into qualified classifications when the provider confirms the label; conflicting or explicitly overridden legacy values remain unchanged. The original nonempty legacy language string is retained. Only classifications needed for new fields are reconciled; this is not a global alias or taxonomy cleanup. No country is inferred from filming location or nationality from birthplace.

An explicit override or prior TMDB import-history marker protects a field even when it is empty; nonempty values are also protected. The original importer now respects override markers for core fields and credit roles. Administrator base-film edits, changes to biography, accepted synopsis proposals, and manual credit additions/removals record overrides as appropriate. As before, structured metadata PATCH records all explicitly submitted fields, including empty values. Old full-record PUT forms record changes rather than all submitted empty defaults, so an unchanged already-empty base field cannot be distinguished from an intentional clear. Manual changes made before markers existed cannot always be reconstructed. Neither version automatically refreshes or deletes imported fields.

Person display names are not treated as verified full names. Nationality, full name, soundtracks and quotes are not automatically imported. No external data providers beyond TMDB are introduced. Additional metadata UI (images, biography layout, certifications, tags, etc.) is planned for discovery-directory work; data can already be examined with metadata GET APIs and existing person biography and film pages.

## Report and verification

- `candidates`, `matched`, `skipped`, `unlinked_movies`, `last_movie_id`: movie scope, matching and checkpoint. `unlinked_movies` counts the entire catalog without a TMDB link.
- `fields_filled`: movie core and extended fields newly populated (one collection counts as one field). `person_fields_filled`: newly populated person fields. `people_created`, `credits_created`: new rows from previously empty credit roles. `links_created` is inherited from the original importer; v2 uses existing movie links and reports new people separately.
- `person_candidates`, `persons_matched`, `persons_skipped`: distinct credited people for matched movies. `classification_codes_added`: new code assignments. `protected_fields` and `unavailable_fields` count evaluated extended fields; they do not account for every original core field/credit role. `issues` lists detected identity, classification and validation conflicts without raw payloads.
- `movie_enrichment_fields` tracks movie field import history. New `person_enrichment_fields` tracks the original person-field fill using the same source/external-ID scheme. These histories do not assert that a later manually edited value is still from TMDB.

Read-only verification:

```powershell
docker compose exec db psql -U cineatlas -d cineatlas -c "SELECT COUNT(*) AS movies FROM movies;"
docker compose exec db psql -U cineatlas -d cineatlas -c "SELECT field, COUNT(*) FROM movie_enrichment_fields GROUP BY field ORDER BY field;"
docker compose exec db psql -U cineatlas -d cineatlas -c "SELECT field, COUNT(*) FROM person_enrichment_fields GROUP BY field ORDER BY field;"
docker compose exec db psql -U cineatlas -d cineatlas -c "SELECT name, code FROM languages ORDER BY name;"
docker compose exec db psql -U cineatlas -d cineatlas -c "SELECT name, code FROM countries ORDER BY name;"
```

Swagger (`http://localhost:8000/docs`): `GET /api/movies/{movie_id}/metadata`, `GET /api/persons/{person_id}/metadata`, `GET /api/persons/{person_id}`, and `GET /api/movies/{movie_id}/credits`. Verify existing ratings, watchlists, accounts, movie IDs, and manual data remain intact. Missing profile pictures and data are normal; no guarantee of completeness.

## Tests

`pytest` uses mocked TMDB responses and disposable SQLite databases. The migration smoke test also simulates enrichment, rollback, provenance and repetition using a synthetic provider on the migrated database. CI runs the smoke test on PostgreSQL. No live token is used by tests. Live service availability, licensing, exact record coverage and final PostgreSQL verification require a local run.

## Provider documentation

- [Movie details](https://developer.themoviedb.org/reference/movie-details)
- [Person details](https://developer.themoviedb.org/reference/person-details)
- [Appending subresources](https://developer.themoviedb.org/docs/append-to-response)
- [Languages](https://developer.themoviedb.org/reference/configuration-languages) and [countries](https://developer.themoviedb.org/reference/configuration-countries)
