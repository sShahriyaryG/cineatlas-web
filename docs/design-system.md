# Modern Cinematheque design system

## Scope

This frontend-only update establishes the Modern Cinematheque visual identity: a restrained concrete-and-cobalt palette, forest accents, strong sans-serif typography, editorial rules and numbered headings, aligned poster grids, and square-edged controls. It restyles Discover, watchlists, recommendations, movie and person pages, authentication, review reporting, account security, and the existing administrative/editor screens. The current navigation, API contract, session behavior and database schema are unchanged. The next application-shell milestone will restructure navigation and page composition; later milestones will add new data, community and personalization functionality.

## Appearance

Choose **Light**, **Dark**, or **System** in the header. System is the default and follows the operating system preference. Explicit choices override the OS and are persisted locally under `ca_appearance`. Other tabs sharing that browser origin receive storage events. The preference is intentionally device/browser-local, not account data; it is retained when signing out or changing accounts. No credential uses this key. The document's `data-theme` attribute and `color-scheme` control application and native form colors, and the `theme-color` metadata follows the resolved theme. The preference is applied before React mounts; the initial HTML may briefly use the default canvas before the JS bundle runs. No remote fonts or new dependencies are needed.

## Tokens

`frontend/src/design.css` owns semantic tokens. Use the tokens in new components rather than fixed theme-specific color values. `style.css` retains shared component layout rules and refers to the tokens; `design.css` is imported after it from `main.tsx` and contains the editorial composition and responsive refinements.

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | `#EDEDE8` | `#161817` |
| Surface | `#F9F9F5` | `#222624` |
| Text | `#202421` | `#E5E7DF` |
| Muted | `#59625B` | `#A0A69D` |
| Accent | `#3154BD` | `#9AAEFF` |
| Forest | `#203D35` | `#A3BDAA` |

Use `--on-accent` for text on filled accent buttons, `--control-border` for input borders and `--line` for decorative rules. Success, warning and danger have their own text, background and border roles. Artwork and poster placeholders have independent colors; never recolor provider logos or movie artwork. Use `--font-body`, `--font-display`, `--space` and `--radius` for consistent typography, spacing and edges. System fonts avoid network font dependencies.

## Verification

Run from the project root:

```powershell
docker compose up -d --build web
docker compose exec web node --experimental-strip-types --test tests/*.test.mjs
docker compose exec web npm run build
docker compose exec api pytest -q
```

The frontend logic suite now includes seven theme tests: normalization, system overrides, storage, unavailable storage, document metadata, text contrast and control contrast. This brings the expected frontend total to 25. The contrast tests check selected semantic color pairs against 4.5:1 (text) and 3:1 (controls), not a complete accessibility certification. The backend suite is unchanged (68 expected tests). GitHub Actions should run the wildcard test command above.

Manual browser checks: switch all three appearance modes, reload and open another tab, change the OS or DevTools emulated color scheme in System mode, sign in and out, try movie/person navigation and search, save and rate a film, check review/spoiler controls and moderation, open the account security/password dialog, and inspect Admin/Editor views. Check at 320px, 390px, 768px and desktop; make sure the header is navigable, forms and focused controls are visible, no document-wide horizontal overflow occurs, and attribution remains readable in both themes.

Development verification: all 25 Node tests passed. Theme helpers passed strict TypeScript checking and the 16 frontend source modules passed TypeScript transpilation syntax checks. CSS parsing and 30 Chromium layout checks passed on representative static markup fixtures (Discover with expanded filters, movie with review form, and admin at five widths for both themes). These fixtures are not the running application. A full production build and integrated browser acceptance tests remain necessary because React dependencies were unavailable in the patch preparation environment.

No database migration or backend change is required.
