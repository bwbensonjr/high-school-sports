# Proposal

## Why

MIAA places every member school into a tournament division per sport, fixed for a two-year alignment cycle (currently 2025-26 and 2026-27) based on enrollment adjusted by a Competitive Equity Modifier, private-school bumps, and appeals. The project currently knows only each team's league/conference, so Elo ratings are shown as a single statewide list that mixes Division 1 schools with Division 5 schools. Divisions are the frame fans, coaches, and the tournament itself use, and the authoritative alignment data is already published as per-sport PDFs, so we can attach division to every team for the full season rather than only after tournament games are played.

Starting now matters because 2026-27 is the second year of the current cycle: loading the 2025-27 alignments immediately covers both the in-progress season and all 2025-26 history, and establishes the process before the 2027-29 alignments are published during the 2026-27 school year.

## What Changes

- Ingest MIAA alignment PDFs for a named alignment cycle into a normalized, committed dataset of (cycle, MIAA sport, gender, school, division) plus supporting attributes (CEM enrollment, private flag, appeal flag, co-op host/guest).
- Introduce a durable crosswalk from Boston Globe team IDs to MIAA school names, built by automated matching, validated against divisions observed in Globe tournament games, and completed by manual curation. Teams that are not MIAA members (NEPSAC/prep, out-of-state) are recorded explicitly as such.
- Map MIAA sport names to the project's sport slugs (e.g., MIAA fall volleyball to `girls-volleyball`, spring volleyball to `boys-volleyball`, gender-split cross country and track).
- Provide a lookup that resolves the division for (sport slug, Globe team ID, game date), choosing the alignment cycle by school year of the date rather than by data file year.
- Capture `tourney_name` and `tourney_level` from the Globe API in the per-sport game CSVs so tournament games are identifiable and serve as an ongoing validation source.
- Extend Elo outputs: add `team_id` and `division` to final ratings, add per-division rank, and render the sport markdown report with division-grouped rating tables alongside the overall ranking.
- Produce a coverage/validation report per cycle (matched, unmatched, non-member, disagreements with tournament divisions) and document the recurring per-cycle refresh procedure.

## Capabilities

### New Capabilities
- `division-alignment`: Ingesting MIAA alignment cycles into a normalized school/sport/division dataset, the MIAA-to-project sport mapping, and resolving a cycle from a date.
- `team-school-crosswalk`: The mapping from Globe team IDs to MIAA schools (or explicit non-member status), how it is built, validated against tournament data, and reported for gaps.
- `division-reporting`: Exposing division on rated teams and games, and Elo ratings viewed and ranked by division in CSV and markdown outputs.
- `game-data-collection`: The per-sport game CSV schema produced from the Globe scoreboard API, now including tournament name and round.

### Modified Capabilities
<!-- None: no existing specs in openspec/specs/. -->

## Impact

- **New code**: an alignment ingestion script (PDF download and parse), a crosswalk build/validate script, and a small division lookup module shared by reporting.
- **Modified code**: `process_games.py` (two new columns), `high_school_elo.py` (final ratings keyed with team ID, division join, markdown by division).
- **New data files**: committed alignment CSV per cycle, crosswalk CSV, sport mapping, and a coverage report under `data/`.
- **Dependencies**: adds `pdfplumber` for PDF table extraction.
- **Automation**: the daily GitHub Actions workflow is unchanged in shape; it reads committed alignment and crosswalk data but does not fetch MIAA PDFs. Alignment refresh is a manual, per-cycle step.
- **Compatibility**: new columns are additive; existing CSV consumers keep working. Older game CSVs lack the tournament columns and are treated as empty.
- **Out of scope**: using division as an Elo model input (e.g., priors or K-factor), MIAA power rankings, NEPSAC classification beyond what tournament games reveal, and alignment cycles before 2025-27.
