# Tasks

## 1. Site data export

- [x] 1.1 Create `site_export.py` with argparse (`--date`, `--results-dir`, `--out-dir` defaulting to `results/` and `site/data/`), Eastern-time "today", and slug-to-display-name conversion; verify `uv run python site_export.py --help` runs and a pytest case maps `boys-skiing-(alpine)` to `Boys Skiing (Alpine)`
- [x] 1.2 Implement current-season selection, `recent` (14 days ending on latest completed game, FINAL and FORFEIT, newest first), and `upcoming` (scheduled games on or after export date, soonest first, stale UPCOMING excluded); verify pytest cases for the off-season recent window, stale-row exclusion, tournament fields, and home-perspective spread
- [x] 1.3 Implement `teams`: filter `*-elo-final.csv` to teams with a completed current-season game, recompute overall and division ranks, count W-L-T, set `hasDivisions`/`divisions`; verify pytest cases for inactive-team exclusion, re-ranking, record counting, and a sport with no alignment
- [x] 1.4 Implement `index.json` (in-season flag per 14-day rule, recent game count, ordering, `generated` timestamp) and per-sport JSON writing with rounding and null omission; verify pytest cases for ordering and in-season edge dates, and that a full run over `results/` writes valid JSON for every sport (`python -m json.tool` succeeds on each file)
- [x] 1.5 Add `site/data/` to `.gitignore` and document the export command in `CLAUDE.md` and `README.md`; verify `git status` shows no generated JSON after a run and the documented command works as written

## 2. Site shell and design tokens

- [x] 2.1 Create `site/index.html` (semantic header, sport `<nav>`, `<main>` with title, view links, content region, `lang`, viewport meta, no external assets) and `site/styles.css` with color, type, spacing, radius tokens plus dark overrides; verify the page loads with `python -m http.server -d site` with no console errors and the tokens are the only color/spacing literals in component rules
- [x] 2.2 Check every text and UI color pair in both themes against WCAG AA (4.5:1 text, 3:1 focus and boundaries) and record the ratios in `site/README.md`; verify all listed pairs pass
- [x] 2.3 Write `site/README.md` covering tokens, components (sport nav, view links, game list, ranking table), breakpoints, routing format, and local preview; verify the preview instructions work as written

## 3. Site behavior

- [x] 3.1 Implement `site/app.js` data loading (index then sport file, `encodeURIComponent` on slugs) and hash routing `#/{sport}/{view}[/{division}]` with fallbacks and back/forward support; verify manually that the root loads the first index sport, an unknown sport falls back to it, `boys-skiing-(alpine)` loads, and back/forward restores prior selections
- [x] 3.2 Render the sport nav (in-season pills with `aria-current`, out-of-season under `<details>` "Other sports") and the last-updated time; verify against a local export that in-season sports appear first in index order and every sport is reachable
- [x] 3.3 Render the Results and Upcoming views (date groups, winner emphasis, tournament tag, favorite with margin and probability per the agreement rule, empty-state line); verify against local data that the Woburn-Beverly style case shows the visitor as favorite and an off-season sport shows an empty Upcoming message
- [x] 3.4 Render the Rankings table (top 25 then "Show all N") and the Divisions view (labeled division `<select>` with Other, unavailable message when `hasDivisions` is false); verify against local data for boys soccer (divisions) and a sport without alignment
- [x] 3.5 Implement load-failure handling for index and sport files; verify by renaming a sport file locally that an error line appears and other sports remain selectable
- [x] 3.6 Run the manual accessibility and layout checklist (keyboard-only pass with visible focus, 360px width without page horizontal scroll, light and dark themes, screen reader heading/table order spot check) and record results in `site/README.md`; verify every checklist item passes

## 4. Deployment

- [x] 4.1 Add `.github/workflows/deploy-site.yml` (triggers: `workflow_run` on successful "Update Scores and Elo Ratings", `push` to `main` on `site/**` or `site_export.py`, `workflow_dispatch`; steps: checkout, setup uv, `uv sync`, run export, `upload-pages-artifact` from `site/`, `deploy-pages`; `pages: write`, `id-token: write`, `github-pages` environment, concurrency group); verify with `actionlint` or a YAML parse and review that triggers match design Decision 5
- [x] 4.2 Document in `README.md` that Pages Source must be "GitHub Actions" and how to redeploy manually; verify the steps match the repository Settings UI labels

## 5. Integration

- [x] 5.1 Run `uv run pytest` and confirm the full suite passes
- [ ] 5.2 After merge, set Pages Source to "GitHub Actions", dispatch "Deploy Site", and confirm the Pages URL shows in-season sports first with current results, predictions, and rankings; then confirm the next scheduled update triggers a redeploy with a newer last-updated time
