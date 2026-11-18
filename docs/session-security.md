# Authentication and session security

## Migration and compatibility

`0005_session_security` adds `auth_sessions`, `auth_attempts` and `security_events`. No existing user, password hash, movie, review, rating or watchlist is changed. Back up PostgreSQL before applying it. The old in-memory bearer registry is removed; all pre-upgrade credentials must sign in again. The browser removes the obsolete `ca_token` localStorage key.

## Browser and API contracts

- Browser registration and login use `X-Auth-Transport: cookie` with `credentials: include`. The trusted Origin must match configuration. The response contains the user and a non-secret `session_id` but never the raw token.
- The server issues a random 48-byte opaque secret in a host-only, HttpOnly, SameSite=Strict cookie (`ca_session`, path `/api`). Its SHA-256 digest alone is stored in PostgreSQL. A normal session expires after 24 hours and uses a browser-session cookie; Remember me explicitly selects a 30-day expiry and persistent cookie. Browser session restore behavior varies by browser; server expiry is authoritative.
- The browser stores only the session identifier (`ca_session_id`) in localStorage. Protected requests send `X-Session-ID` and the cookie. Both must refer to the same record. A stale tab cannot use a new account's cookie with its previous account's identifier. The marker alone grants no access.
- Non-browser API clients can continue using `Authorization: Bearer <token>` returned by the default register/login contract. Cookie secrets cannot authenticate via the bearer transport. Keep API tokens confidential.
- The server enforces revocation, expiry, the current account's active status and current role on protected requests. No authenticated API responses should be cached (`Cache-Control: no-store`). The origin is checked on cookie mutations; the custom header and restricted CORS prevent ordinary cross-site form CSRF. HttpOnly mitigates token extraction, not arbitrary actions by same-origin XSS.

## Account security controls

Click the signed-in username/user icon. The security panel displays active sessions, the recorded user-agent label (not verified device identity), creation and expiry, and the current session. Sign out one session, sign out everywhere, or change the password. Password changes require the current password, preserve the current session and revoke others. Passwords remain Argon2 hashed. Session enumeration and termination are restricted to their owner.

Logout clears the UI state immediately and attempts server revocation independently of cancelled page requests. A network failure or cookie mismatch results in an unconfirmed server sign-out warning. A revoked cookie is intentionally not deleted by the logout response: a delayed deletion could overwrite a newer cross-tab login. It is unusable after successful server revocation and overwritten on subsequent login or removed by browser expiry. Simultaneous logins in different tabs can race to assign the shared cookie; marker validation fails closed rather than showing the wrong account. Sign in again if that happens. Other devices discover revocation on their next authenticated request; already-rendered content and in-flight writes cannot be retroactively revoked.

Account suspension UI is planned for the Admin milestone. The existing `is_active` check denies inactive accounts; when implementing suspension, update the flag and call `revoke_all` in the same transaction so that reactivation does not resurrect old sessions. The session-management UI is not an administration console.

## Rate limits and audit events

Authentication attempts use atomic database upserts in 15-minute fixed UTC windows: 50 login attempts per IP, 10 per IP/identifier pair, 10 registrations per IP, 10 password-change attempts per IP/user pair. Successful and failed attempts count. Exceeding a limit returns 429 with Retry-After. Login uses generic invalid-credential errors and an Argon2 verification path for unknown users. Limits are intentionally simple, not comprehensive protection against distributed attacks or shared-IP denial of service. Use trusted reverse-proxy configuration and a deployment-level limiter before public hosting. Forwarded IP headers are not parsed directly by application code. Attempt counters store hashed keys, not plain identifiers; hashes should not be treated as anonymized personal data. Old windows are pruned on new attempts.

Security events include generic failed login, session creation/revocation, all-session revocation, failed password change and successful password change. No password or raw credential is logged. These tables need a defined retention/cleanup policy before production; automated session/event purging and admin audit UI are not implemented here.

## Local development and production

Docker Compose intentionally defaults `CINEATLAS_COOKIE_SECURE=false` for local HTTP. Open `http://localhost:5173` (or consistently use `127.0.0.1`). Frontend defaults to the same hostname on port 8000. Do not expose this local HTTP configuration publicly. For production use HTTPS, set `CINEATLAS_COOKIE_SECURE=true`, set `CINEATLAS_WEB_ORIGINS` to explicit trusted frontend origins (comma-separated, no wildcard), set `VITE_API_URL` for the deployed same-site API or `/api` behind a same-origin proxy, configure trusted proxies, and ensure that production cookie and origin settings are tested. The code defaults to secure cookies outside Compose unless explicitly disabled. Separate, cross-site frontend/API hosting is not supported by this Strict-cookie configuration. This branch is a foundation, not a production security audit or a complete password-reset/MFA solution.

## Verification

- Backend: `python -m pytest -q` from backend (isolated SQLite test fixtures).
- Frontend: `node --experimental-strip-types --test tests/*.test.mjs` and `npm run build` from frontend.
- GitHub Actions runs the PostgreSQL migration/API smoke check against a fresh disposable database, now including durable session creation and revocation. Never point `ci.database_smoke` at your real catalog database.
- Browser: sign in, inspect storage (no raw token), refresh, restart API, verify session remains valid, test separate browser profiles, revoke another device, change password, sign out everywhere, verify navigation and user-specific data isolation. Use disposable test accounts for password and rate-limit tests.

## Password change feedback and browser autofill

The password-change form includes the signed-in account username, stable field IDs and names, and standard username/current-password/new-password autocomplete attributes. Form submission reads the actual field values, including autofill values. A successful API response replaces the form with an inline, focused confirmation; a failed request retains the form and displays an error. The login and registration forms also expose stable autofill field names. No password is persisted by the frontend. Browser password-manager behavior is controlled by the browser or extension, not CineAtlas; it may offer to update the saved entry, or require manual confirmation/update, especially when the stored login uses an email alias rather than the account username.

Browser acceptance: use a disposable account, save its login in the browser, submit mismatched passwords and a wrong current password (no success confirmation), then change the password successfully. Verify visible confirmation, form removal, the current session remains active, other sessions are revoked, the old password fails, and the new password works. Check whether the password manager offers an update; if not, confirm its saving settings and update the saved entry manually.
