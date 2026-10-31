# High School Sports

Scores and Elo for MA high school sports

## Overview

This project is able to create and then do daily updates of
Massachusetts high school sports teams, creating logs of matchups with
scores, and then using the scores to do Elo ratings of the teams by
sport.

## Data Source

The data comes from calls to API URLs like the following:

* https://www.bostonglobe.com/partners/data-high-school-sports-services/prd/202526/v2/scoreboard/2025-09-20.json

There is a sample data file in `data/2025-09-20.json`. The JSON data
has the following structure:

```
{
  "date": "2025-09-20",
  "dates": [
    {
      "date": "2025-09-10",
      "sports": [
        {
          "id": 54,
          "name": "field hockey",
          "gender": 2,
          "season": "fall",
          "games": [
            {
              "id": 48604,
              "date": "2025-09-10",
              "homeConference": "Bay State",
              "visitorConference": "Bay State",
              "tourneyName": null,
              "tourneyLevel": null,
              "time": "4:00 P.M.",
              "label": "",
              "status": "FINAL",
              "teams": {
                "visitor": {
                  "id": 4279,
                  "teamPageUrl": "https://www.bostonglobe.com/sports/high-schools/schedule?sport=field-hockey&school=newton-north",
                  "name": "Newton North",
                  "score": "0",
                  "tracked": "1",
                  "outcome": "0"
                },
                "home": {
                  "id": 4059,
                  "teamPageUrl": "https://www.bostonglobe.com/sports/high-schools/schedule?sport=field-hockey&school=brookline",
                  "name": "Brookline",
                  "score": "3",
                  "tracked": "1",
                  "outcome": "1"
                }
              },
              "overtime": null,
              "isShootoutWin": 0,
              "gameUrl": null,
              "story": {
                "preview": null,
                "url": null,
                "author": null
              },
              "lastUpdated": 1757556807
            },
            ...
          ]
        },
        ...
      ],
    },
    ...
  ]
}
```
  
Per-sport CSV files are automatically generated in the `data` directory like
`data/field-hockey-2025.csv` that contain game results and upcoming matchups between the teams.

## Data Processing

The `process_games.py` script handles fetching and processing game data from the Boston Globe API:

### Usage

```bash
# Process games for a single date
python process_games.py --date 2025-09-20

# Process games for today's date
python process_games.py --today

# Process games for a date range
python process_games.py --start 2025-09-20 --end 2025-09-25

# Run tests to verify update functionality
python process_games.py --test

# Show help
python process_games.py --help
```

### Features

- **Automatic data fetching**: Downloads game data directly from the Boston Globe API
- **Smart updates**: Running the same date multiple times updates existing CSV files without creating duplicates
- **Score updates**: Games initially marked as "UPCOMING" are updated with final scores when re-processed
- **Completed results are kept**: Re-fetching an older date never replaces a FINAL game with a stale UPCOMING or POSTPONED entry; only score corrections and forfeit rulings replace a FINAL game
- **Date range processing**: Process multiple days of games in a single command
- **Error handling**: Graceful handling of network errors and invalid dates
- **Built-in testing**: Comprehensive tests verify that game updates work correctly

### Output

The script creates separate CSV files for each sport (e.g., `boys-soccer-2025.csv`, `field-hockey-2025.csv`) with columns including:
- Game date and ID
- Home and visitor teams (names and IDs)
- Scores and outcomes
- Game status (FINAL, UPCOMING, etc.)
- Conference information
- Game time and metadata
- Tournament name and round (`tourney_name`, e.g. "MIAA Division 3", and `tourney_level`, e.g. "Quarterfinals"), empty for regular-season games

## Computing Elo Ratings

The Elo rating system is implemented in `elo.py` and used by `high_school_elo.py` to compute team rankings based on game results.

### Usage

```bash
# Compute Elo ratings for field hockey (as an example)
python high_school_elo.py field-hockey

# The script will process all available data files for the sport
# and generate rankings with detailed game-by-game Elo changes
```

### Features

- **Multi-season support**: Processes all available years of data for a sport
- **Chronological processing**: Games are processed in date order for accurate rating evolution
- **Between-season regression**: Ratings regress toward the mean between seasons
- **Lower-score sports**: `SCORE_ORDER` in `high_school_elo.py` sets which score
  wins. Cross country is lowest-wins. Golf mixes stroke play (lowest wins) with
  match play and points formats (highest wins) without saying which, so the
  game's recorded result decides; golf is rated on wins and losses only
  (`margin_of_victory=False`) and predicts no spreads
- **Detailed output**: Saves complete game-by-game results with pre/post Elo ratings and win probabilities
- **Top team rankings**: Displays final rankings of all teams

### Output

The script creates:
- `results/{sport}-elo-ratings.csv`: Complete game results with Elo data, including
  `home_division` and `visitor_division` resolved for each game's date
- `results/{sport}-elo-final.csv`: Current ratings with `team_id`, `overall_rank`,
  `division`, `division_status` (`assigned`, `non-member`, or `unknown`), and
  `division_rank` (rank within the team's MIAA division)
- `results/{sport}-{season}.md`: Report with upcoming games, recent results, the
  overall Elo table, and an Elo table for each MIAA division followed by other teams
- Console output showing top 20 team rankings

### Elo System Parameters

- **K-factor**: 20 (rating change multiplier)
- **Home field advantage**: 50 points
- **Starting rating**: 1500 points
- **Score multiplier**: Logarithmic based on the winning margin (none for golf)
- **Regression factor**: 33% toward mean between seasons


## Website

A static site in `site/` shows each sport's recent results, upcoming
games with predicted spreads, Elo rankings across divisions, and Elo
rankings within each MIAA division. Sports in season are listed first.
The page code never changes with the data: it reads JSON files that
`site_export.py` builds from `results/`.

```bash
# Build site/data/index.json and site/data/sports/{sport}.json from results/
python site_export.py            # --date YYYY-MM-DD overrides "today" (Eastern)

# Preview locally at http://localhost:8000
python -m http.server -d site
```

`site/data/` is generated and not committed. See `site/README.md` for the
design tokens, components, and accessibility checks.

### Deployment

The "Deploy Site" workflow (`.github/workflows/deploy-site.yml`) runs the
export and publishes `site/` to GitHub Pages after each successful "Update
Scores and Elo Ratings" run, on pushes to `main` that change `site/` or
`site_export.py`, and on manual dispatch.

One-time setup: in the repository's **Settings > Pages**, under **Build and
deployment**, set **Source** to **GitHub Actions**.

To redeploy by hand: **Actions > Deploy Site > Run workflow**, or
`gh workflow run deploy-site.yml`.

## MIAA Divisions

MIAA assigns each member school a tournament division per sport for a
two-year alignment cycle (for example 2025-26 and 2026-27, written
`2025-27`), based on enrollment adjusted by a Competitive Equity
Modifier, private-school placement, and appeals. Statewide divisions
are numbers (`1`-`8`); swimming, golf, gymnastics, and wrestling align
by section, written like `N 1`.

Division data lives in `data/miaa/`:

- `alignment-{cycle}.csv`: one row per school and sport, parsed from MIAA's alignment PDFs
- `alignment-{cycle}-manifest.csv`: each source document's URL, SHA-256, row count, and status
- `sport-map.csv`: MIAA alignment documents mapped to this project's sport names
- `team-crosswalk.csv`: Globe team IDs mapped to MIAA school names, or marked `non-member`
  (prep and out-of-state teams). Rows with a `sport` value override the school-wide row for
  co-ops. Only rows with `confirmed=True` are used.
- `coverage-{cycle}.md`: coverage and validation report

A game's division comes from the cycle containing its date, where school
years start on August 1. The daily update only reads these files; it never
contacts MIAA.

### Refreshing alignments each cycle

MIAA publishes the next cycle's alignments by season during the school year
before it starts (fall first, then winter, then spring). Run this when a new
cycle page is posted, and again if MIAA revises a sport after appeals:

```bash
# 1. Download and parse every sport's alignment PDF (cached in data/miaa/pdf/, not committed)
python miaa_alignment.py ingest --cycle 2025-27 \
  --index-url https://www.miaa.net/2025-26-2026-27-tournament-alignment-cycle

# 2. Propose crosswalk rows for any Globe team without a confirmed mapping.
#    Confirmed rows are never changed. Review rows with confirmed=False, fix the
#    school or status where needed, and set confirmed=True.
python miaa_alignment.py crosswalk

# 3. Check coverage, tournament-division disagreements, and unmatched teams
python miaa_alignment.py report --cycle 2025-27

# 4. Recompute Elo so reports pick up the divisions, then commit data/miaa/ and results/
python high_school_elo.py
```

Add any new MIAA sport to `sport-map.csv`; the report lists unmapped sports on
both sides. Tournament games recorded in the game CSVs are the main check on
the crosswalk: a team's alignment division should match the "MIAA Division N"
tournament it plays in.

### Tests

```bash
uv run pytest
```

PDF parsing tests use the cached PDFs and are skipped until `ingest` has run.
