# Proposal

## Why

Elo ratings, predictions, and division rankings are regenerated daily but are only visible as CSV files and per-season markdown reports in `results/`, which are hard to browse and not designed for casual readers. A public GitHub Pages site gives anyone a simple, fast view of each sport's results, predictions, and rankings, built from the same daily data without rebuilding the UI each day (`docs/ui-design.md`).

## What Changes

- Add a static, single-page website (HTML, CSS, vanilla JavaScript; no build step) served by GitHub Pages.
- Add a site data export step that, after Elo ratings are computed, writes compact JSON data files for the site: a sport index (with in-season flags and last-updated time) and one file per sport containing recent games with results, upcoming games with predicted spreads and win probabilities, overall Elo rankings, and division Elo rankings for the current season.
- The UI reads only those data files at runtime; daily updates change data, never UI code.
- For each sport the site shows four views: Recent results, Upcoming (with predicted spreads), Elo rankings across all divisions, and Elo rankings by division.
- Every sport with data is reachable, but sports currently in season are listed first and the most active in-season sport is shown by default.
- The design follows `docs/ui-design-principles.md`: minimal text, clear hierarchy, tokenized colors/spacing/typography, light and dark themes, WCAG AA contrast, semantic and screen-reader friendly markup, and progressive disclosure (e.g., one view at a time, division chosen from a selector, long lists truncated with "show more").
- Extend the daily GitHub Actions workflow to run the export and deploy the site to GitHub Pages.

## Capabilities

### New Capabilities
- `site-data-export`: The JSON data contract the website consumes (sport index, per-sport games and rankings, in-season determination, freshness) and when it is regenerated.
- `sports-website`: The public website's behavior: sport selection and default, the four per-sport views, layout and accessibility rules, and deployment to GitHub Pages.

### Modified Capabilities
<!-- None: existing Elo, division, and report outputs are read, not changed. -->

## Impact

- New code: `site_export.py` (Python export to `site/data/`), `site/` (static `index.html`, `styles.css`, `app.js`), tests in `tests/`.
- Workflow: `.github/workflows/update-scores.yml` gains an export step and a Pages deploy job; repository Pages settings must use "GitHub Actions" as the source.
- Inputs consumed unchanged: `results/{sport}-elo-ratings.csv` and `results/{sport}-elo-final.csv` (including division columns from `division-reporting`).
- No new Python dependencies (pandas and stdlib `json`); no JavaScript dependencies or build tooling.
- Out of scope: team detail pages, historical seasons browsing, search, charts, and custom domains.
