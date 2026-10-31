# Spec Delta

## Purpose

Produces the daily-regenerated JSON data files that the public website reads, so site content updates with each data run while the website code itself stays unchanged.

## ADDED Requirements

### Requirement: Sport index file
The export SHALL write one index file listing every sport that has Elo results, with its slug, display name, current season, in-season flag, count of completed games in the last 14 days, and the export timestamp. In-season sports SHALL be ordered first, by recent completed games descending, then the rest alphabetically by display name.

#### Scenario: Index lists all sports
- **WHEN** the export runs and `results/` contains Elo results for 40 sports
- **THEN** the index contains 40 entries, each with slug, display name, season, and in-season flag

#### Scenario: Display name
- **WHEN** a sport's slug is `boys-skiing-(alpine)`
- **THEN** its display name is `Boys Skiing (Alpine)`

#### Scenario: Ordering
- **WHEN** field hockey (120 recent games) and football (60 recent games) are in season and baseball is not
- **THEN** the index order is field hockey, football, then baseball among the out-of-season sports

### Requirement: In-season determination
A sport SHALL be in season when, relative to the export date, it has a completed game within the previous 14 days or a scheduled game within the next 14 days.

#### Scenario: Active fall sport
- **WHEN** the export runs on 2026-10-31 and field hockey has final results dated 2026-10-30
- **THEN** field hockey is in season

#### Scenario: Off-season sport
- **WHEN** the export runs on 2026-10-31 and baseball's latest game is 2026-06-14 with no upcoming games
- **THEN** baseball is not in season

### Requirement: Per-sport data file
The export SHALL write one data file per sport containing its current season's recent results, upcoming games, and team rankings, so the website needs no other file to render that sport.

#### Scenario: One file per sport
- **WHEN** the export runs for field hockey
- **THEN** a single field hockey data file contains `recent`, `upcoming`, and `teams` sections

### Requirement: Recent results
The `recent` section SHALL list current-season completed games (final and forfeit) dated within the 14 days ending on the sport's latest completed game date, newest first, each with date, home and visitor team names and scores, predicted spread, and tournament name and level when present.

#### Scenario: Out-of-season sport still shows results
- **WHEN** baseball's latest completed game is 2026-06-14
- **THEN** its `recent` section contains its completed games from 2026-06-01 through 2026-06-14

#### Scenario: Tournament game
- **WHEN** a recent game has tournament name "MIAA Division 3" and level "Final"
- **THEN** its entry carries both values; regular-season entries carry none

### Requirement: Upcoming games
The `upcoming` section SHALL list current-season scheduled games dated on or after the export date, soonest first, each with date, time, home and visitor team names, home win probability, and predicted spread. Scheduled games dated before the export date SHALL be excluded.

#### Scenario: Stale scheduled game excluded
- **WHEN** a game dated 2026-10-20 still has status UPCOMING on 2026-10-31
- **THEN** it does not appear in `upcoming`

#### Scenario: Prediction fields
- **WHEN** an upcoming game has home win probability 0.881 and predicted spread +2.6
- **THEN** its entry carries both values with the spread from the home team's perspective

### Requirement: Team rankings
The `teams` section SHALL list each team with a completed current-season game, with Elo, overall rank among those teams, current-season win-loss-tie record, division, division status, and division rank, ordered by Elo descending.

#### Scenario: Overall rank excludes inactive teams
- **WHEN** a team has an Elo rating but no completed game in the current season
- **THEN** it is not in `teams` and does not affect other teams' ranks

#### Scenario: Division fields
- **WHEN** a team is assigned Division 3 and ranks second in it
- **THEN** its entry shows division 3, status `assigned`, and division rank 2

#### Scenario: No alignment data
- **WHEN** a sport has no division alignment for the current cycle
- **THEN** every team's division is empty and the file marks divisions as unavailable

### Requirement: Daily regeneration
The data files SHALL be regenerated after Elo ratings are computed in each scheduled data update, and every file SHALL be valid JSON readable by a browser without further processing.

#### Scenario: Scheduled run
- **WHEN** the daily update fetches new scores and recomputes Elo
- **THEN** the index and every sport data file reflect that run and carry its timestamp
