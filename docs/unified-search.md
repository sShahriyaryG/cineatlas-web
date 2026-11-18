# Unified search and Explore

The archive has six context-aware Explore sections, plus a separate global search at `/search`, accessible from the header. The search input in Films matches display, original and alternative titles. Plot summaries can be searched using the optional toggle in advanced filters. People searches match display names, available full names and alternative names; classification directories match their names. The old API `mode` values are still supported for existing consumers but actor/director/all are no longer exposed in the film search interface.

Global search groups results into films, people, genres, countries, languages and tags using the same catalog and directory queries. `GET /api/search?q=...` returns up to five items per matching entity type (with totals); the All view hides empty groups; a category shows paginated results. It is a lookup tool, not a duplicate advanced-filter workspace. Film and person cards navigate to their respective existing routes. Directory links use stable IDs. Result category, search text and selected page are retained during in-session navigation, not browser reloads or account changes.

## Film filters

The main film index and every individual classification page share a single filter component. Classification pages retain a fixed server-side scope; the current classification is omitted from selectable options. Resetting or clearing filters never changes that scope. Other classifications of the same kind can still be selected to find co-productions, combinations of genres, etc.

Each vocabulary offers Ignore, Include and Exclude choices. Include All (AND) or Include Any (OR) applies within its group; exclusions always apply independently. All groups are combined with AND. A selected item cannot simultaneously be included and excluded. Exclusion only removes films with the specified known association, so records without that association remain eligible. Missing runtime, community rating or certification data does not satisfy an explicit filter on that field. Existing genre-name parameters remain available for older clients; use stable IDs in new clients.

Cast and crew selection uses the people directory, with a person ID and a particular role or any role. Matching uses the same credit row for person and role (not a name join). Multiple people or roles can be included using All/Any or excluded independently. Certifications require a country, and the optional rating label must match that same country's certification row. No universal age conversion is attempted.

### API additions

Both `GET /api/movies` and `GET /api/directory/classifications/{category}/{classification_id}` accept:

- `genre_ids`, `language_ids`, `country_ids`, `tag_ids`: repeated numeric identifiers (limit 20 per group); matching controlled by `genre_mode`, `language_mode`, `country_mode`, `tag_mode` (`and`/`or`).
- `exclude_genre_ids`, `exclude_language_ids`, `exclude_country_ids`, `exclude_tag_ids`: repeated IDs, limit 20 each.
- `credit`, `exclude_credit`: repeated `person_id:role` values (limit 20 each), `role` can be `any` or a supported credit role. `credit_mode` controls inclusions.
- `runtime_min`, `runtime_max`: inclusive whole minutes, 1–10080.
- `certification_country`: numeric country ID; optional `certification_rating`: exact label (requires country).
- `sort=title_desc`: descending title order; existing sort modes unchanged.

Use `/api/directory/filter-options` for classification IDs and `/api/directory/certification-options` for actual country/rating pairs, including countries without local production links. The people and classification directory endpoints accept `sort=relevance|name|name_desc|count_desc|count_asc`. Counts represent distinct local films.

## Interaction and verification

Explore search requests are debounced and older requests are cancelled. Resource identity includes request path, session and revision so stale results are not shown for a changed query. Searches and filter changes reset pagination. Automatic sorting uses alphabetical order with an empty query and relevance when searching; explicit sort overrides remain in place. The shared pager hides itself for zero or one page. Existing responsive page sizing remains in the grid views. Global search uses a compact list, with twenty entries per full result category. Advanced filter sections collapse independently and active conditions are removable outside the panel. Clear filters preserves the text and sorting; Reset all resets them too.

No migration, dependencies, external provider requests or catalog expansion are introduced. The expected migration head remains `0007_person_enrichment`. Run `pytest -q` in the backend and `node --experimental-strip-types --test tests/*.test.mjs` plus `npm run build` in the frontend. CI exercises the migration chain and combined search conditions against a disposable PostgreSQL database. Browser checks should cover both themes, mobile layouts, keyboard navigation, search back-navigation and combinations of inclusion/exclusion within fixed classification scopes. Legacy taxonomy cleanup, editor and admin metadata forms, and automatic refresh remain separate milestones.
