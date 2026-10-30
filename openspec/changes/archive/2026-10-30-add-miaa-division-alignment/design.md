# Design

## Context

See proposal.md for motivation. Current state that shapes the approach:

- `process_games.py` writes `data/{sport}-{year}.csv`, where the year comes from the fetched date. The year is not a season: `boys-basketball-2025.csv` holds games from Dec 2025 through Jan 2026. The Globe API already carries `tourneyName` and `tourneyLevel` on every game, but they are dropped.
- `high_school_elo.py` keys Elo by team **name**. `results/{sport}-elo-final.csv` has only `team,elo`, and the markdown report has a single ranking table. Team IDs are in the game CSVs, and names map one-to-one to IDs within a sport.
- MIAA publishes each sport's alignment as a PDF linked from a cycle page (e.g., `miaa.net/2025-26-2026-27-tournament-alignment-cycle`). A probe with `pdfplumber` extracted all 338 boys soccer rows with a consistent 12-column table. The column holding the final division differs between sports (soccer vs basketball) and the header is not repeated on later pages.
- A probe crosswalk using simple name normalization matched 239 of 388 Globe boys soccer teams. All 98 matched teams that played in the Nov 2025 tournament agreed with the PDF division, and the 40 unmatched tournament teams failed only on naming (e.g., "BC High", "Cambridge", "Millbury Mem.Jr./Sr.H.S.").
- The daily GitHub Actions job runs `process_games.py --today` and `high_school_elo.py`, then commits `data/` and `results/`.

## Goals / Non-Goals

**Goals:**
- One alignment refresh per cycle (plus re-runs for appeal revisions), done manually; the daily job only reads committed files.
- A crosswalk that is mostly automated but auditable, where manual decisions survive re-runs.
- Division lookups that are cheap and deterministic during Elo runs.

**Non-Goals:**
- Changing Elo math or how seasons are split for regression.
- A database or web UI; outputs stay as CSV and markdown.
- Scraping MIAA pages on a schedule or detecting new cycles automatically.

## Decisions

### Data layout under `data/miaa/`
- `alignment-{cycle}.csv`, e.g. `alignment-2025-27.csv`, with columns `cycle, miaa_sport, season, gender, school, aligned_school, city, section, division, cem_enrollment, is_private, appeal, coop_role, host_school, source_url`. `section` is set only for sectionally aligned sports (swimming, golf, gymnastics, wrestling), where the division label is written like `CW 1`.
- `alignment-{cycle}-manifest.csv`, listing each sport document's URL, SHA-256, row count and status (`ok` / `missing` / `failed`).
- `sport-map.csv`, mapping `miaa_sport, season, gender` to `sport_slug`.
- `team-crosswalk.csv`, with columns `team_id, team_name, sport, school, status, method, confirmed, note`. `sport` is blank for the school-wide default; `status` is `member` or `non-member`; `method` is `auto`, `manual` or `tourney`; `note` records the score, alternates or reason.
- `coverage-{cycle}.md`, the coverage and validation report.
- Downloaded PDFs are cached in a git-ignored `data/miaa/pdf/` folder. The manifest hash records exactly which document produced the committed CSV.

Alternative considered: committing the PDFs. They are about 30 files of 150-300 KB per cycle, and the parsed CSV plus hash give enough provenance without bloating the repo.

### Separate `data/miaa/` namespace
`high_school_elo.py` finds sports by globbing `data/*.csv` and parsing `{sport}-{year}`. Putting the new files in a subdirectory keeps them out of that glob, so it needs no special-casing.

### CLI: one new script, `miaa_alignment.py`, with subcommands
- `ingest --cycle 2025-27 --index-url <cycle page>` reads the cycle page, collects the per-sport links (which return PDFs directly), parses each one, and writes the alignment CSV and manifest.
- `crosswalk` proposes entries for unmapped teams and writes them with `confirmed=false`. Rows with `confirmed=true` are never modified.
- `report --cycle 2025-27` writes the coverage and validation report.

This follows the existing argparse style in `process_games.py`. Alternative considered: separate scripts per step. Rejected because the steps share parsing and normalization code.

### PDF parsing
pdfplumber's table extraction (line and text strategies) failed on several documents: it merged a page's divisions into one cell, dropped name cells, or split words. So parsing works from word positions instead:
- Group words into lines.
- Find the header line containing `MailCITY`, whose labels (TEAM/SCHOOL, Aligned, MailCITY, Sport, Gender, Coop, HostSchool) set the left-hand column positions.
- Classify the tokens to the right by pattern: CEM enrollment, `AA`/`CC` appeal flags, and the final division with an optional 1-3 letter section code. A bare `Y` counts as private or as an appeal depending on which header word ("Private" or "Appeal") is nearer.
- Skip page footers, and stop at "TOTAL NUMBER OF TEAMS", since summaries and notes follow it.
- Strip the clipped overflow that pdfplumber glues onto the next column (e.g. "SchooBridgewater").

Valid divisions are the integers 1-8. Any other value makes that sport `failed`. All 29 published 2025-27 documents parse, with row counts matching each document's stated team total.

### Name normalization and matching
- Normalize names: lowercase; `&` becomes `and`; `St.` becomes `saint`; `Mt.` becomes `mount`; drop parentheticals; drop suffix words (high school, regional, reg, H.S., memorial, jr./sr., charter, academy, school, RVT, voc/tech).
- An exact normalized match on a unique school gives a confirmed `auto` entry. Out-of-state names (a state abbreviation in parentheses), teams in NEPSAC tournaments, and teams whose main conference is an independent-school league (ISL, EIL, MBIL, IGC, NEPSAC) are confirmed `non-member`.
- Otherwise, take `difflib` candidates scored by name similarity plus a bonus when the Globe name contains the school's city.
- Tournament evidence adds to or subtracts from the score by the share of the team's tournament sports whose division agrees with the school's. It is averaged, not summed, so teams in many sports aren't over-weighted.
- Proposals at or above the threshold are written `confirmed=false` for review.

The crosswalk is school-wide by default because Globe team IDs and MIAA school names are both school-level. Per-sport rows exist only for co-op exceptions. Alternative considered: a crosswalk per sport. Rejected because it multiplies manual curation by about 30 sports.

### School identity across documents
School names are keyed by normalized name alone, because co-op rows list the aligned school's city. Where a crosswalk name is a truncation (e.g. "Advanced Math & Science Acad."), the lookup uses the single school in that sport, in the same most-common city, whose key extends it. A shorter key never matches a longer crosswalk name, so "Foxborough Regional Charter" can't resolve to "Foxborough High School".

### Lookup module `divisions.py`
It loads the alignment CSVs, sport map and crosswalk once, and exposes:
- `cycle_for_date(date)`: school year starts Aug 1; cycles are two school years starting at an odd-to-even boundary taken from the ingested cycle names, not hard-coded.
- `division_for(sport_slug, team_id, date)`, returning `(division, status)`.

Unconfirmed crosswalk rows are not used for lookups. They only appear in the coverage report.

### Elo integration
In `compute_elo_ratings`:
- Build a name-to-ID map from the game data and add `team_id` to the final ratings.
- Resolve division for the **reference date**: the latest completed game date in the current season, so reports after the season ends still show that season's divisions.
- Add `overall_rank`, `division`, `division_status` and `division_rank`.
- For per-game results, resolve home and visitor division for each game's own date.
- `generate_markdown_report` writes the overall table, then one table per division, then an "Other teams" table.

## Risks / Trade-offs

- [MIAA changes PDF layout in a future cycle] → Parsing checks each sport's structure and fails it loudly. The manifest shows which sports need attention, and the cached PDFs let us iterate offline.
- [Globe renames a team or reuses an ID] → The crosswalk stores `team_name` at mapping time. The report flags rows whose current Globe name differs.
- [Co-ops change between seasons] → Per-sport override rows. Co-op guests stay unmatched until handled, and the coverage report lists them.
- [Manual curation of about 100+ schools up front] → Tournament-evidence narrowing and city hints cut the work. The first pass is a one-time cost that carries across sports and cycles.
- [Divisions shown for the current cycle on a report covering an earlier season] → Reference-date resolution ties divisions to the season's own dates.
- [`pdfplumber` added to the CI install] → It's a pure-Python dependency with a small footprint. The daily job never calls it, but `uv sync` installs it.

## Migration Plan

1. Add the tournament columns to `process_games.py`. Backfill the 2025-26 tournament windows (Nov 2025, late Feb-Mar 2026, Jun 2026) so validation has evidence, plus the fall 2026 tournament once it starts.
2. Ingest `2025-27`, build and curate the crosswalk until all MIAA tournament teams are confirmed, and commit the data.
3. Ship the Elo and report changes. The new columns are additive, and sports without alignment data render as before plus a note.
4. Rollback: revert the Elo changes. The data files are inert without them.

Per-cycle procedure (to document in the README): when MIAA posts the next cycle page (expected during the 2026-27 school year for `2027-29`), run `ingest`, then `crosswalk`, review, run `report`, and commit. Re-run `ingest` if MIAA posts appeal revisions.

## Implementation Notes

- The fall 2025 tournament backfill ran through 2025-12-10 to include football finals. Re-fetching older windows overwrote 11 rescheduled spring games' later FINAL rows with stale entries; those rows were restored from the committed files, and CLAUDE.md records the caveat.
- The 2025-27 crosswalk has 636 rows, all confirmed: 633 teams and 3 per-sport co-op overrides. Every team that played an MIAA tournament game in 2025-26 is confirmed.

## Open Questions

- Whether any 2025-27 sport uses a non-integer division label (e.g., a split division). The parser rejects it loudly, so this can be resolved when encountered.
- Exact URL of the 2027-29 cycle page. `ingest` takes it as an argument, so the plan doesn't depend on it.
