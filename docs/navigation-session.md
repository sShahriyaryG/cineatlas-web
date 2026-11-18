# Navigation and client-side session isolation

## Purpose

This change fixes detail-page Back navigation and prevents account changes from retaining the previous application's search, filters, pagination, collections, administrative screens, drafts, or pending response state. No backend, migration, dependency, or application-version change is required.

## Navigation

`navigation.ts` defines validated routes and non-secret history entry metadata. `useNavigation.ts` owns the native History API, path changes, focus and best-effort scroll restoration. Each visit has a distinct key; the index indicates whether there is a known in-app predecessor. Movie/person detail and error/loading pages use a shared Back action. Example: Discover search → film → person → another film → Back returns to the person, next Back returns to the first film, and next Back restores Discover with its search, filters and pagination. The browser's forward button retraces the same entries.

A direct link with no known predecessor uses a Discover fallback (replace, not push). The action does not send the user to a referrer outside CineAtlas. Each in-memory application/session boundary has its own non-secret history scope. Old or unmarked history entries encountered via popstate are replaced with a clean Discover entry rather than restoring an earlier account's page. The browser's actual history cannot be erased; a user may need multiple native Back presses to reach entries preceding an authentication boundary. A full reload creates a new in-memory scope and opens the requested URL, but does not restore previous search/scroll state or prior in-app navigation context. History contains neither account tokens nor private data.

## Authentication transitions

`SessionRoot` owns a `SessionScope` and renders the application with a key unique to that scope. A successful login/registration, logout, authenticated 401, or observed cross-tab token change cancels the old scope and replaces the current route with `/`. All application/child state is recreated, including modal, expanded filters, search results, watchlist, recommendations and admin view state. The current release's home remains Discover; a later milestone introduces the personalized dashboard. Failed login does not clear the current guest search. Closing the authentication dialog aborts its pending request, and simultaneous form submissions are prevented.

Every API request is bound to the scope's token and abort signal, combined with the caller's signal. Responses are checked for cancellation after fetching and decoding. Requests use `cache: no-store` to avoid reuse of authenticated HTTP responses. A stale request or stale unauthorized response cannot transition a newer scope. Guest authentication errors remain ordinary errors. A stored token is verified on initial load; transient errors offer a retry or sign-out rather than discarding the token. Same-origin tabs observe the existing shared localStorage token, and restored back/forward-cache documents check it on `pageshow`.

Logout removes the local token and discards the application state immediately. Server revocation is attempted separately with the captured old credential and an eight-second timeout. If revocation cannot be confirmed, the UI reports that local sign-out succeeded but server revocation was unconfirmed. A request already processed by the server may still commit a write despite client cancellation; cancelling a fetch is not database rollback.

This fixes client lifecycle/state isolation, not backend session storage. The existing bearer token in localStorage and in-memory server token registry are unchanged. Durable revocation, expiration policy, rate limits and any change to credential storage are part of the separate session-security milestone. The client uses browser AbortSignal.any and AbortSignal.timeout (modern browsers); legacy browsers are not targeted in this branch.

## Verification

From the project root:

```powershell
docker compose up -d --build web
docker compose exec web node --experimental-strip-types --test tests/*.test.mjs
docker compose exec web npm run build
docker compose exec api pytest -q
```

The frontend suite contains 16 pure logic tests (3 existing, 13 added), including history scope validation, fallback, request isolation, cancellation during response decoding, stale unauthorized responses, guest headers and logout handling. These are not browser end-to-end tests. The existing GitHub Actions frontend job discovers all test files automatically. The backend suite should remain at 59 tests.

Manual browser checks (use two test accounts, not a real administrator for mutation tests):

1. Enter a title search, expand filters, select a genre, and navigate result pages. Open a film, a cast member, and a film in their filmography. Use in-page Back repeatedly, checking the original search/filter/pagination state. Check browser Forward, Watchlist/For You origin, and repeated visits to the same film.
2. Open a movie/person URL in a new tab and use its Discover fallback. Check missing records and unsupported routes. Check keyboard navigation and the skip link.
3. Sign out from a filtered Discover page, a detail page, and a personal workspace. Verify `/`, default search, collapsed filters, page one, no private data, and signed-out header. Sign in as another user; check the same reset and the correct account's saved films. Native Back into the old scope must not restore the previous account's workspace or UI.
4. With two tabs open, sign out or sign in in one tab; the other should reset to the same account/guest. With throttled network, start a personal-data request and change accounts; old results must not populate the new session. Cancel a slow login attempt; it must not navigate or sign in later. A slow registration may create an account server-side even if the UI cancels.
5. Test invalid credentials, an expired server token, and offline sign-out. In the offline case, restore the network afterward; locally removed credentials are no longer available to retry revocation. Verify the warning and use disposable accounts.
6. Confirm movie browsing, watchlists, ratings, review publishing/reporting, editor and admin screens, and mobile layout remain usable. No persistent catalog data should change except deliberate test writes.
