# Tasks

## 1. Setup

- [x] 1.1 Add `pdfplumber` to `pyproject.toml` dependencies and `pytest` to a dev dependency group; verify `uv sync` succeeds and `uv run python -c "import pdfplumber"` runs
- [x] 1.2 Create `data/miaa/` and add `data/miaa/pdf/` to `.gitignore`; verify `git check-ignore data/miaa/pdf/x.pdf` reports it ignored

## 2. Tournament fields in game data

- [x] 2.1 Add `tourney_name` and `tourney_level` to the game record in `process_games.py` and extend the built-in `--test` fixture with a tournament game; verify `uv run python process_games.py --test` passes and asserts both fields
- [x] 2.2 Make CSV updates tolerate older files lacking the new columns; verify by processing one date into a copy of an existing sport CSV and checking prior rows have empty tournament fields
- [x] 2.3 Backfill tournament windows (2025-11-01..2025-11-25, 2026-02-20..2026-03-20, 2026-06-01..2026-06-25); verify `data/boys-soccer-2025.csv` contains rows with `tourney_name` "MIAA Division 1" through "MIAA Division 5"
- [x] 2.4 Update CLAUDE.md data format notes for the new columns

## 3. Alignment ingestion

- [x] 3.1 Implement `miaa_alignment.py ingest --cycle --index-url`: collect per-sport links from the cycle page, download to `data/miaa/pdf/{cycle}/`, record URL, SHA-256, status in `alignment-{cycle}-manifest.csv`; verify the manifest lists all fall, winter, and spring sports and marks ski as `missing`
- [x] 3.2 Implement PDF table parsing (header detection by `TEAM`, final-division column by `FINAL` header with last-non-empty fallback, page-artifact skipping, division validated as 1-8, sport fails atomically); add pytest cases using the cached boys soccer and boys basketball PDFs; verify boys soccer yields 338 rows and both layouts parse
- [x] 3.3 Write `data/miaa/alignment-2025-27.csv` with the normalized columns and replace-only-this-cycle semantics; verify re-running ingestion leaves row count stable and a dummy other-cycle file untouched
- [x] 3.4 Create `data/miaa/sport-map.csv` covering every MIAA sport in the manifest and every project sport slug in `data/`; verify `miaa_alignment.py report` lists any unmapped sport on either side and fall/spring volleyball map to girls/boys

## 4. Team-school crosswalk

- [x] 4.1 Implement name normalization and `crosswalk` candidate generation (exact normalized match confirmed as `auto`; difflib plus city and tournament-division narrowing written unconfirmed); add pytest cases for "Doherty", "Millbury Mem.Jr./Sr.H.S.", "Martha's Vineyard Reg. High Sch.", and preservation of confirmed rows
- [x] 4.2 Run `crosswalk` across all sports' Globe teams and write `data/miaa/team-crosswalk.csv`; verify every team ID appears at most once per sport scope
- [x] 4.3 Curate: confirm or correct proposals, add non-member rows for prep and out-of-state teams, add per-sport co-op overrides; verify every Globe team that played an MIAA tournament game in 2025-26 is confirmed
- [x] 4.4 Implement `report --cycle` producing `data/miaa/coverage-2025-27.md` (mapped / non-member / unmatched per sport, alignment schools without a Globe team, tournament-division disagreements, Globe name drift); verify the report shows zero disagreements for boys soccer

## 5. Division lookup

- [x] 5.1 Implement `divisions.py` with `cycle_for_date` (Aug 1 school-year boundary, cycles derived from ingested files) and `division_for(sport, team_id, date)` returning division and status, ignoring unconfirmed crosswalk rows; add pytest cases for 2026-01-10 resolving to `2025-27`, 2024-12-01 resolving to unknown, a co-op override, and a non-member

## 6. Elo reporting by division

- [x] 6.1 Add `team_id`, `overall_rank`, `division`, `division_status`, `division_rank` to `results/{sport}-elo-final.csv` using the season reference date; verify with `uv run python high_school_elo.py boys-soccer` that division ranks restart at 1 per division and unmapped teams show `unknown`
- [x] 6.2 Add `home_division` and `visitor_division` per game to `results/{sport}-elo-ratings.csv`; verify a cross-division game shows both values
- [x] 6.3 Extend `generate_markdown_report` with per-division tables and an "Other teams" table, and an unavailable note for sports without alignment; verify `results/boys-soccer-2026.md` and a sport without alignment render as specified
- [x] 6.4 Update README and CLAUDE.md with the division columns, report layout, and the per-cycle alignment refresh procedure; verify the documented commands run as written

## 7. Integration

- [x] 7.1 Run the daily sequence (`process_games.py --today`, `high_school_elo.py`) on a clean checkout without network access to miaa.net; verify it completes and does not touch `data/miaa/`
- [x] 7.2 Run `openspec validate add-miaa-division-alignment --strict` and verify it passes

## Workflow follow-up

- Archive the change after review with `/opsx:archive`.
- When MIAA posts the 2027-29 cycle page, run the per-cycle procedure from the README.
