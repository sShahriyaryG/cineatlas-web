# Optional catalog metadata (v0.6 foundation)

Migration: `0006_catalog_metadata` (after `0005_session_security`). This is a schema and API milestone; it does not fetch provider data or implement the full discovery or editorial interfaces. The API and package version remain 0.5.0 during development.

## Schema

- `languages`, `countries`, `tags`: shared vocabulary with normalized Unicode/casefolded keys and preserved display labels. Language and country codes are nullable/unique; this branch does not guess or populate code mappings. Future enrichment must reconcile names and verified codes explicitly (casefolding does not resolve synonyms or translations).
- `movie_languages`: movie/language/kind links, with `original`, `spoken`, and `unspecified` kinds. A partial unique index permits at most one original language. The same language may be both original and spoken.
- `movie_countries`, `movie_tags`: many-to-many classifications. Country references represent production countries when explicitly supplied as such; legacy country values are preserved as supplied and may require later verification.
- `movie_metadata`: optional original title, release date, release status and trailer URL; `movie_alternative_titles`: alternative titles, deduplicated by normalized key.
- `movie_certifications`: country-specific certification labels; a film can have multiple certifications for a country. No universal numeric age or release-specific certification interpretation is implied.
- `movie_soundtracks`, `movie_quotes`: optional ordered entries, not required; links must be HTTP(S). Quotes have a speaker and spoiler flag; only submit content you have permission to use. This does not host music or source quotation text automatically.
- `person_metadata`, `person_alternative_names`, `person_nationalities`: optional full name, profile image URL, birth/death dates, birthplace, aliases and independently supplied nationalities. A birthplace is not evidence of nationality. Biography remains on `persons`.
- `movie_metadata_overrides`, `person_metadata_overrides`: record the most recent explicit manual write, including `null` and `[]`. The enrichment-v2 importer must consult these markers and existing values; these are not a comprehensive audit trail or an implementation of enrichment-v2.
- Extended credit roles: composer, cinematographer, editor and other, in addition to actor, director, writer and producer. Only actor credits can have character names.

The existing movie and person IDs, external identities, ratings, reviews, watchlists, and security data remain unchanged. Core columns are deliberately not added to `movies`/`persons`: the initial migration uses the live model definition for its original table set, so separate extension tables avoid changing the shape of that historical migration. The credit-role check is expanded in place (SQLite uses Alembic batch mode).

## Legacy compatibility

The migration keeps original `movies.language` and `movies.country` strings unchanged. Nonblank values become vocabulary/relationship entries without splitting punctuation or claiming an original/spoken distinction. Blank values produce no links. Case/whitespace variants deduplicate; synonyms and composite strings are deliberately not interpreted automatically. New movies written through the existing admin API and original archive import maintain links as well. The old Wikidata ingestion script creates no language/country values and is unchanged.

The legacy create/update API and old admin form remain available. After structured updates, the old `language`/`country` fields are compatibility previews (one whole label that fits the existing field, not an exhaustive list). On ordinary legacy edits, omitted or identical language/country values do not overwrite normalized data. Attempts to change a legacy language field for a film with qualified/multiple languages or its country field for multiple countries return 409; use the structured metadata endpoint instead. Those fields will receive full editing controls in the administration milestone. Direct SQL writes outside the application are not supported as a synchronization mechanism.

## API contract

Public reads (unknown record: 404):

- `GET /api/movies/{movie_id}/metadata`
- `GET /api/persons/{person_id}/metadata`

Existing movie responses also include `original_language`, `spoken_languages`, `unspecified_languages`, `production_countries`. The card uses a known language when available. Existing movie/person routes and filmography remain compatible.

Admin-only writes (unauthenticated: 401; non-admin: 403):

- `PATCH /api/movies/{movie_id}/metadata`
- `PATCH /api/persons/{person_id}/metadata`

Writes are transactional. Omitted fields retain existing values. Explicit `null` clears a nullable scalar; `[]` clears a collection. Unknown properties, invalid dates, invalid links, blank required labels, excessive lengths, and unsupported roles are rejected. List fields replace the supplied collection in full; soundtrack and quote order is the supplied order. Conflicts with database constraints return 409. Full editorial conflict detection and audit trails are scheduled for later branches; do not edit the same item simultaneously during this milestone.

Example movie patch for a disposable test record (fictional data):

```json
{
  "original_title": "Metadata test film",
  "original_language": "English",
  "spoken_languages": ["English", "French"],
  "production_countries": ["Canada", "France"],
  "release_date": "2020-01-01",
  "release_status": "released",
  "alternative_titles": ["Test alternate title"],
  "tags": ["Test tag"],
  "certifications": [{"country": "Canada", "rating": "PG"}],
  "soundtracks": [{"title": "Synthetic track", "artist": "Example artist"}],
  "quotes": [{"quote": "Synthetic test quotation.", "speaker": "Example character", "spoiler": true}]
}
```

Example person patch for a disposable record:

```json
{
  "full_name": "Synthetic Full Name",
  "birthday": "1980-01-01",
  "birthplace": "Example Town",
  "nationalities": ["Canada"]
}
```

From local Swagger UI (`http://localhost:8000/docs`), authenticate with `POST /api/auth/login` (default bearer transport) and use Authorize with the returned token. Keep it private, do not paste it into tickets or documentation, and revoke the test session in the account security panel when finished. Read-only endpoints can be inspected without a token. Use synthetic records rather than overwriting actual imported metadata.

## Upgrade, verify and rollback

Stop API/web to avoid concurrent writes, take and verify a PostgreSQL backup, extract the patch, rebuild api/web and verify `alembic current` reports `0006_catalog_metadata (head)`. The backend Docker startup runs the upgrade automatically. Run:

```powershell
docker compose exec api pytest -q
docker compose exec web node --experimental-strip-types --test tests/*.test.mjs
docker compose exec web npm run build
```

CI uses `backend/ci/database_smoke.py` on a disposable PostgreSQL database. **Do not run it against the development catalog.** It checks migration schema consistency and the new metadata endpoints as well as existing authentication/search/library paths. Use a fresh CI database only.

`alembic downgrade` drops optional metadata, normalized links and override markers. It refuses to downgrade if any newly supported roles exist; it does not silently delete credits. The old compatibility columns do not contain the complete structured information after edits. For a real rollback use the verified pre-upgrade backup and matching prior code, not a downgrade as a substitute for restoration.

## Remaining work

Enrichment-v2 must populate missing provider-backed information without overwriting manual data, verify country/language codes and record provider provenance. Full metadata and person photographs, directory browsing, unified search and filters, editorial contribution forms and administration UI are scheduled for separate branches. Country-specific certification selection, production companies/budget/revenue (if later needed), release scopes and external link content verification are not implemented here. No live external API calls or import of new movie records occurs in this branch.
