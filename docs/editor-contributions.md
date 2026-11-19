# Editorial contributions

## Scope

The Editor workspace supports new film/person proposals, updates to existing core and extended metadata, and shared credits. Published catalog writes still require administrator approval. Existing synopsis-only proposals appear in the same contribution history in both workspaces; their old API stays compatible. New proposals use the contributions API. An administrator cannot review a contribution they authored.

Migration `0008_contributions` adds `contributions` and a nullable `movie_credits.position`. Earlier records and credit identities are retained. Null positions keep the prior name-based ordering; movie editors may explicitly order credits within a role. Person filmography edits do not reorder existing movie credits. Soundtracks and quotations can be reordered. Each credit references an existing movie/person by ID. Propose and approve a new related entity first if it is not yet in the catalog.

## Workflow

1. Admin assigns a separate member account the editor role (Admin Studio → Members). Sign in as that editor and open `/editor`.
2. Choose New film or New person, or search for a film or person under Edit existing record. Record finders show up to six matching results per page only after typing a nonblank query; clearing the query hides the results. Missing fields can be filled in the same editing form. Changes are scoped to the selected record. The server captures and verifies an exact baseline. For a list, use Add to commit each typed item to the form; remove existing items explicitly. Add credits via the related record finder and choose the credit role. Empty optional fields may be cleared. A new film requires a title and release year; a new person requires a name before submission.
3. Save draft to persist typed changes. Drafts may be incomplete, but entered values must pass their individual field validators. Unsaved form edits are not automatically saved. Use the new-record preview (for new films/people) or the comparison preview (for edits) and supply a reason (at least five characters) and an optional HTTP(S) supporting source URL. Submit for review saves and submits the draft. A failed submission after a successful draft save remains a draft; invalid field values are rejected before saving. Validation messages and draft-save confirmation appear beside Save draft and Submit for review buttons.
4. Drafts are private to their owner and can be resumed, changed, or deleted. Pending contributions cannot be edited; they can be withdrawn. Approved/rejected/withdrawn contributions retain their baseline, proposed changes, author, reviewer (when reviewed), note, and timestamps. Rejected/withdrawn contributions can be used to prepare a revised draft with a fresh baseline. Review preserved collection values carefully before resubmitting; credit revisions replay the prior delta so newly added unrelated credits are retained.
5. As a separate admin, open `/admin` → Editor proposals → Catalog contribution review. The default All statuses view includes all submitted contributions (never private drafts). Select Pending for the review queue. Click View details on a compact entry to see proposed new-record fields or original/proposed edit fields; Check current catalog values reads the latest record for edits. Approve and publish or reject with a reason of at least five characters. Only approval applies changes.
6. If the baseline no longer matches the record, approval returns HTTP 409 and does not write anything. Reject with a conflict explanation or ask the editor to withdraw, then prepare a revised draft. The check is deliberately conservative: any changed field or credit on the target record can invalidate a proposal, even when it is unrelated to the submitted change.

The redundant Missing information workspace has been removed from the interface; its read-only API remains available for compatibility. Both workspaces show one combined timeline with title, type, status and attribution, five per page, newest creation date first. Only one expanded detail is mounted at once. The single status filter applies to both kinds. Existing synopsis proposals retain their underlying table and actions; no original synopsis snapshot or review note is reconstructed. Pending admin synopsis previews may show the live synopsis, explicitly labeled. New-record previews display proposed values only. The admin proposal badge uses the combined pending total.

## API (relative to `/api`)

All new routes require the editor or admin role; `/admin/contributions` and `/admin/contribution-history` require admin. Existing authentication/session and CSRF rules apply. Permissions and transitions are enforced on the server, not only in the frontend.

| Method | Path | Purpose |
|---|---|---|
| GET | `/editor/catalog/{entity}/{id}` | Exact snapshot (`movie` or `person`) |
| GET | `/editor/missing/{entity}?field=...&page=1&size=20` | Paginated incomplete records |
| GET | `/editor/credit-labels/{entity}?ids=1&ids=2` | Resolve related IDs to display names |
| GET | `/me/contribution-history?status=pending&page=1&size=5` | Unified owned history (structured and synopsis; status optional) |
| GET | `/admin/contribution-history?status=pending&page=1&size=5` | Unified review/history, excludes private drafts |
| GET | `/me/contributions?status=draft&page=1&size=20` | Own contributions, status optional |
| POST | `/me/contributions` | Create draft |
| PATCH | `/me/contributions/{id}` | Update owned draft (version required) |
| DELETE | `/me/contributions/{id}?version=1` | Delete owned draft |
| POST | `/me/contributions/{id}/submit` | Submit owned draft |
| POST | `/me/contributions/{id}/withdraw` | Withdraw owned pending proposal |
| GET | `/admin/contributions?status=pending&page=1&size=20` | Review queue/history, excludes drafts |
| POST | `/admin/contributions/{id}/review` | Review with `version`, `decision`, `note` |
| POST | `/me/suggestions/{id}/withdraw` | Withdraw an older owned synopsis proposal |

Example new movie draft:

```json
{
  "entity": "movie",
  "target_id": null,
  "changes": {
    "core": {"title": "Synthetic QA film", "year": 2024, "genres": ["Drama"]},
    "metadata": {"original_language": "English", "tags": ["Fixture"]},
    "credits": []
  },
  "reason": "Synthetic local acceptance record",
  "source_url": null
}
```

For an existing record, set `target_id` and include the exact complete `baseline` object retrieved from the catalog snapshot endpoint. `changes.core` and `changes.metadata` are partial maps, omitted keys remain untouched. Null clears nullable scalars, an empty array clears a collection, and omitting `credits` retains relationships. Sending `credits` replaces the selected record's credit set using stable IDs and preserves identical rows. A movie credit can specify nullable, nonnegative `position`; a person's credits use movie IDs and never set position. The form submits only changed fields and passes structured metadata to the same validation helpers as the admin metadata API.

Use the returned `version` for every subsequent update/transition. For submission or withdrawal: `{"version": 1}` (substitute the current version). Review: `{"version": 2,"decision":"approved","note":""}`. Rejection requires a meaningful note. The version guards concurrent changes to a proposal. Validation exercises the publication path inside a rolled-back savepoint; draft/pending/rejected/withdrawn state does not persist catalog mutations. Database sequences may advance during validation; gaps in IDs are normal. Approval changes the catalog and records its review in one transaction. PostgreSQL catalog API mutations and approval share a transaction-scoped advisory lock. Existing external import scripts are not part of this lock, so stop application services before running enrichment as previously documented.

New proposed movies check title/year collisions; person proposals conservatively check same display name and birthday, including cases where a birthday is unknown. These checks are not comprehensive external identity reconciliation. Credits reject exact duplicate identities/roles/characters and nonexistent references. Approved metadata and changed credit groups write manual-override markers for future enrichment. New contribution history keeps plain catalog IDs so deleting a catalog record later does not erase that history. Legacy synopsis proposals retain their existing semantics (no historical baseline migration). No self-review on either review path.

## Verification and limits

Run `pytest -q` from backend, `node --experimental-strip-types --test tests/*.test.mjs` and `npm run build` from frontend, and use the existing empty-database migration smoke test. Never run the smoke script against the populated local catalog. The new tests cover privacy, role boundaries, immutable pending status, approval, rejection, withdrawal, version checks, conflict handling, duplicate checks, validation rollback, shared credit edits/order, missing-record lists and history retention. Browser testing and PostgreSQL CI are required before merging.

No new dependencies or external provider requests are required. Classification fields currently use normalized text labels, not a taxonomy reassign/merge tool; that remains planned for Admin Studio. Credits are limited to 500 per changed collection. No automatic draft saving, full external identity verification, user notifications, comprehensive direct-admin audit log, simultaneous cross-record proposal, or automatic conflict merge is introduced. The full Admin Studio redesign remains separate, including compact report history and search-driven movie management.

Back up the PostgreSQL database before upgrading. Migration rollback drops all new contribution history and explicit ordering but cannot undo already-approved catalog changes. To undo the entire update, use a verified pre-upgrade backup with the matching source version rather than downgrading in place.
