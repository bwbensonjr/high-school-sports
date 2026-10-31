# Site

Static GitHub Pages site for Massachusetts high school sports results,
predictions, and Elo rankings. There is no build step: `index.html`,
`styles.css`, and `app.js` are served as-is and read JSON from `data/`,
which `site_export.py` generates. Daily updates change only `data/`.

Design goals come from `docs/ui-design.md` and
`docs/ui-design-principles.md`.

## Local preview

```bash
python site_export.py              # writes site/data/ from results/
python -m http.server -d site      # open http://localhost:8000
```

## Data

| File | Contents |
|------|----------|
| `data/index.json` | `generated` timestamp, export `date`, and `sports` in display order (`slug`, `name`, `season`, `inSeason`, `recentGames`) |
| `data/sports/{slug}.json` | `recent` results, `upcoming` games, `teams` rankings, `hasDivisions`, `divisions` |

Game fields: `home`/`visitor` names, `hs`/`vs` scores, `ho` home outcome
(1 home won, 0 visitor won, 2 tie, from the source data so low-score
sports like cross country are correct), `homeProb`, `spread` (home
perspective), `tourney`, `level`, `time`, and `status` for forfeits.
Missing values are omitted.

## Routing

State lives in the URL hash so links can be shared and GitHub Pages needs
no rewrite rules: `#/{sport}/{view}[/{division}]`, for example
`#/girls-soccer/divisions/2`. Views are `results`, `upcoming`, `rankings`,
and `divisions`; the division `other` lists non-member and unmatched teams.
Unknown parts fall back to the first sport in the index, `results`, and the
first division, and the URL is rewritten to match what is shown.

## Tokens

All component rules use the custom properties at the top of `styles.css`;
dark values override colors under `prefers-color-scheme: dark`.

| Group | Tokens |
|-------|--------|
| Color | `--bg`, `--surface`, `--text`, `--text-muted`, `--border` (decorative dividers), `--border-strong` (control boundaries), `--accent`, `--accent-text`, `--accent-soft`, `--focus` |
| Type | `--font-sans` (system stack); sizes `--text-xs` 13px, `--text-sm` 14px, `--text-md` 16px, `--text-lg` 20px, `--text-xl` 28px (32px at 600px+); weights 400/500/700; `--leading-tight`, `--leading-normal` |
| Space | `--space-1`..`--space-7` = 4, 8, 12, 16, 24, 32, 48px; `--gutter` |
| Shape | `--radius-sm`, `--radius-md`, `--radius-pill`, `--border-width`, `--focus-width` |
| Layout | `--max-width` 720px; column widths `--col-rank`, `--col-num`, `--col-record`, `--col-time`, `--col-score`, `--col-prob`, `--col-sport` |

### Contrast (WCAG 2.1 AA)

| Pair | Use | Min | Light | Dark |
|------|-----|-----|-------|------|
| `--text` on `--bg` | Body text on page | 4.5:1 | 16.4:1 | 15.8:1 |
| `--text` on `--surface` | Text on cards and tables | 4.5:1 | 17.8:1 | 14.4:1 |
| `--text-muted` on `--bg` | Date headings, season, updated time | 4.5:1 | 6.2:1 | 7.7:1 |
| `--text-muted` on `--surface` | Losing team, records, game time | 4.5:1 | 6.7:1 | 7.1:1 |
| `--accent-text` on `--accent` | Selected sport and view; inset focus ring on selected view | 4.5:1 | 7.9:1 | 8.5:1 |
| `--text` on `--accent-soft` | Tournament tag | 4.5:1 | 15.1:1 | 12.1:1 |
| `--accent` on `--surface` | Current sport in Other sports | 4.5:1 | 7.9:1 | 8.1:1 |
| `--accent` on `--bg` | Current sport in Other sports | 4.5:1 | 7.3:1 | 8.9:1 |
| `--border-strong` on `--surface` | Pill, view switcher, select, button boundaries | 3:1 | 3.6:1 | 3.7:1 |
| `--border-strong` on `--bg` | Control boundaries against page | 3:1 | 3.3:1 | 4.1:1 |
| `--focus` on `--bg` | Focus ring | 3:1 | 7.3:1 | 8.9:1 |
| `--focus` on `--surface` | Focus ring on cards and controls | 3:1 | 7.9:1 | 8.1:1 |

Recheck these pairs whenever a color token changes.

## Components

Top to bottom, in DOM and reading order:

- **Header**: site name and last-updated time (muted, secondary).
- **Sport nav** (`<nav aria-label="Sports">`): in-season sports as pill
  links in index order; out-of-season sports inside a `<details>` "Other
  sports" list, opened automatically when the current sport is there.
  Current sport has `aria-current="page"`. Links keep the current view.
- **Sport title**: `h1` with the season in muted weight.
- **View switcher** (`<nav aria-label="Views">`): four links styled as a
  segmented control. Plain links rather than an ARIA tablist, so keyboard
  behavior is native and every view has a URL. Nav links are built once
  and updated in place, so focus stays put while navigating.
- **Game list** (Results, Upcoming): `h2` per date ("Today", "Yesterday",
  "Tomorrow" prefixes), then a card of rows. Visitor on top, home below
  with `@`. Results bold the winner and mute the loser. Upcoming shows the
  time and, on the favorite's line, the margin (`-1.6`) and win
  probability; the margin is omitted when the spread disagrees with the
  probability (they use separately fitted home edges). Tournament games
  get a short tag ("D3 · Final") with the full name for screen readers.
- **Ranking table** (Rankings, Divisions): `<table>` with a screen-reader
  caption and `scope="col"` headers. Rankings shows 25 rows and a "Show
  all N" button that moves focus to the first revealed row. Divisions adds
  a labeled `<select>` and lists that division by division rank.
- **Messages**: one muted line for empty, unavailable, and load-error
  states.

## Breakpoints

- Up to 400px: 12px gutter, tighter table cells, smaller view labels.
- 600px and up: larger sport title.
- Content is capped at 720px. Team names wrap; records never wrap. Tables
  scroll inside their card if ever wider than the screen, never the page.

## Accessibility and layout checklist

Run against a local export with Chrome (light and dark, 1024px and 360px).
Results from 2026-10-31:

| Check | Result |
|-------|--------|
| Skip link is the first tab stop, focuses content, and keeps the route | Pass |
| Keyboard only: choose a sport, switch views, choose a division, show all rankings, with a visible focus ring (including on the selected view) | Pass |
| Back and forward restore sport, view, and division | Pass |
| 360px wide: no horizontal page scroll on all four views, light and dark | Pass |
| Dark theme follows the system preference | Pass |
| Headings: one `h1` (sport), then `h2` date groups | Pass |
| Tables have captions and column headers; "#" and "Div" headers have spoken labels | Pass |
| Division select has a visible label | Pass |
| Unknown sport in the URL falls back to the default sport | Pass |
| Sport file that fails to load shows an error; other sports still work | Pass |
| No console errors | Pass |
