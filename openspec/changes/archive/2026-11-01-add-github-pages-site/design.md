# Design

## Context

See proposal.md for motivation. Current state relevant to the approach:

- `.github/workflows/update-scores.yml` runs daily (~6am Eastern), fetches scores, runs `high_school_elo.py` for all sports, and commits `data/` and `results/` to `main` using `GITHUB_TOKEN`.
- Per sport, `results/{sport}-elo-ratings.csv` holds every game across all seasons (1-2 MB for large sports) with `season`, `status`, pre-game Elo, `home_win_prob`, `pred_point_spread`, tournament fields, and `home_division`/`visitor_division`. Stale `UPCOMING` rows from past dates remain in the file (e.g. 566 in field hockey).
- `results/{sport}-elo-final.csv` holds `team, elo, team_id, overall_rank, division, division_status, division_rank` for every team ever rated, including teams that did not play this season (football: 381 rated vs 327 active).
- `docs/` holds design documents, so it is not available as a Pages root without mixing concerns.

## Goals / Non-Goals

**Goals:**
- Zero-build static site; UI code changes only when the design changes.
- Small per-sport payloads (tens of KB) so a phone loads one sport quickly.
- One small set of reusable components (sport nav, view tabs, game list, ranking table) styled by tokens.

**Non-Goals:**
- Changing Elo computation, division resolution, or existing `results/` outputs.
- Client-side frameworks, bundlers, npm, or third-party JS/CSS/fonts.
- Historical seasons, team pages, search, charts (candidates for later changes).

## Decisions

### 1. Static HTML/CSS/vanilla JS (ES modules), no build step
`site/index.html`, `site/styles.css`, `site/app.js`. The UI is four views over simple lists and tables; a framework would add tooling without benefit.
Alternatives: Jekyll (Pages-native, but templates would need regenerating with data and Liquid is awkward for interactive selection); React/Vite (build pipeline and dependencies for little gain).

### 2. Python exports compact JSON; the browser never reads raw CSVs
New `site_export.py` reads `results/*-elo-ratings.csv` and `*-elo-final.csv` with pandas and writes:

```
site/data/index.json
  { "generated": "2026-10-31T08:24:00-04:00", "date": "2026-10-31",
    "sports": [ { "slug": "field-hockey", "name": "Field Hockey", "season": 2026,
                  "inSeason": true, "recentGames": 212 }, ... ] }

site/data/sports/{slug}.json
  { "slug", "name", "season", "generated", "hasDivisions": true,
    "divisions": ["1","2","3","4","5"],
    "recent":   [ { "date","home","hs","visitor","vs","spread","tourney","level" } ],
    "upcoming": [ { "date","time","home","visitor","homeProb","spread","tourney","level" } ],
    "teams":    [ { "rank","team","elo","w","l","t","div","divStatus","divRank" } ] }
```

Values are rounded (Elo integer, probability 3 places, spread 1 place, integral scores as ints) and null fields omitted. Raw CSVs carry all history and many columns; filtering in Python keeps the browser simple and payloads small, and keeps the data contract testable in pytest.
Alternative: fetch CSVs and parse in JS - rejected for size (1-2 MB per sport) and for duplicating season/stale-row logic in two languages.

### 3. Team rankings recomputed among active teams
`teams` takes Elo and division columns from `*-elo-final.csv` but keeps only teams with a completed current-season game (from `*-elo-ratings.csv`), then recomputes `rank` and `divRank` among those teams. Record is counted from current-season FINAL/FORFEIT rows via each side's outcome; ties counted when neither side won. The existing final CSV and markdown report are untouched.

### 4. Dates and in-season logic in Eastern time
The export "today" is `datetime.now(ZoneInfo("America/New_York")).date()` (stdlib), overridable with `--date` for tests and backfills. In-season, recent window, and upcoming filtering follow the `site-data-export` spec. The current season per sport is the max `season` value, matching `high_school_elo.py`.

### 5. Deployment via a separate Pages workflow using Actions artifacts
New `.github/workflows/deploy-site.yml` triggers on `workflow_run` (Update Scores completed successfully), on `push` to `main` touching `site/**` or `site_export.py`, and on `workflow_dispatch`. It checks out `main`, runs `uv sync` and `uv run python site_export.py`, then `actions/upload-pages-artifact` (path `site/`) and `actions/deploy-pages` with `pages: write` and `id-token: write`. `site/data/` is gitignored.
Rationale: pushes made with `GITHUB_TOKEN` do not trigger `push` workflows, but `workflow_run` does; a separate workflow redeploys UI edits without fetching scores; generated JSON is not committed, avoiding daily diff noise.
Alternatives: commit JSON and serve from a `gh-pages` branch or `/docs` (daily churn, `/docs` already used); add deploy steps to `update-scores.yml` (UI-only changes would require a score fetch to redeploy).

### 6. Hash routing
State lives in the hash: `#/{sport}/{view}[/{division}]`, e.g. `#/girls-soccer/divisions/2`. Views: `results`, `upcoming`, `rankings`, `divisions`. Pages has no SPA fallback, so path routing would 404 on reload. Invalid parts fall back to defaults (first index sport, `results` view, first division).

### 7. Layout and progressive disclosure
Top to bottom, in DOM and reading order:
1. Header: site name (small) and last-updated time (muted).
2. Sport nav: in-season sports as a horizontally scrollable row of pill links (`aria-current` on the active one); out-of-season sports in a native `<details>` "Other sports" list. No sport is hidden.
3. Sport title (largest type) with season.
4. View tabs: four links styled as a segmented control (`aria-current="page"`), not ARIA tablist, keeping keyboard behavior native.
5. Content:
   - Results/Upcoming: date headings (`h3`, e.g. "Sat, Oct 31") over compact game rows. Results show two stacked team lines with right-aligned scores; winner bold, loser muted. Upcoming shows time, two team lines, and a single right-side figure "Beverly -1.6" with "77%" beneath. Tournament games get a small tag ("D3 Final").
   - Rankings: `<table>` with columns Rank, Team, Elo, Record, Div; first 25 rows then a "Show all N" button.
   - Divisions: a `<select>` labeled "Division" (Division 1..N, Other), then the same table component without the Div column.
   Empty and error states are one short line in muted text.

Predicted favorite is the team with win probability >= 0.5; the margin shown is `abs(spread)` only when the spread sign agrees with the favorite (home edge for spreads and probabilities are fit separately, so they can disagree near even), otherwise the margin is omitted and only the probability is shown.

### 8. Design tokens and themes
`styles.css` opens with CSS custom properties: colors (`--bg`, `--surface`, `--text`, `--text-muted`, `--border`, `--accent`, `--accent-text`, `--win`, `--focus`), type scale (`--font-sans` system stack, sizes 0.8125/0.875/1/1.25/1.75rem, weights 400/600/700), spacing (`--space-1`..`--space-7` = 4/8/12/16/24/32/48px), radius, and `--max-width` 720px. Dark values override the colors under `@media (prefers-color-scheme: dark)`. All component styles reference tokens only. Contrast pairs are checked to AA (4.5:1 for text, 3:1 for focus ring and UI boundaries). Numeric columns use `font-variant-numeric: tabular-nums`. A short `site/README.md` documents tokens, components, and breakpoints (handoff principle).

### 9. Tests
pytest covers the export with small in-memory frames: index ordering and in-season flags, display names, recent window anchored to latest game, stale UPCOMING exclusion, active-team filtering and re-ranking, record counting, no-division sports, and JSON rounding/omission. The UI is verified with a manual checklist (keyboard pass, 360px width, light/dark, a sport without divisions, an off-season sport) served locally with `python -m http.server -d site`.

## Risks / Trade-offs

- [Pages source must be switched to "GitHub Actions" in repo settings] → Listed as a manual task; the deploy workflow fails visibly until it is.
- [`workflow_run` deploys only after a successful update; a failed update leaves yesterday's site] → Acceptable; `workflow_dispatch` allows manual redeploy.
- [Sport slugs contain parentheses, e.g. `boys-skiing-(alpine)`] → Encode with `encodeURIComponent` in fetch URLs and hash; test that sport explicitly.
- [Individual sports (cross-country, track, swimming) have dual-meet scores whose spreads read oddly] → Shown with the same components; no special-casing in this change.
- [Spread/probability disagreement near even games] → Handled by Decision 7's omission rule.
- [Export picks a different current season than reports for winter sports spanning files] → Uses the same `season` column `high_school_elo.py` writes, so both agree.

## Migration Plan

1. Merge with `site/`, `site_export.py`, tests, and the deploy workflow.
2. In repository Settings > Pages, set Source to "GitHub Actions".
3. Run "Deploy Site" via `workflow_dispatch`; confirm the Pages URL renders.
4. Rollback: disable the deploy workflow or Pages; no existing outputs change.
