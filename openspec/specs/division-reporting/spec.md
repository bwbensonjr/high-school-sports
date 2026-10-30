# division-reporting Specification

## Purpose

Makes division available on rated teams and games so Elo ratings can be viewed, ranked, and analyzed within an MIAA division for a sport and season.

## Requirements

### Requirement: Division on final ratings
The final ratings output for each sport SHALL include team ID, current division for the current cycle, and division status (`assigned`, `non-member`, or `unknown`) for every rated team.

#### Scenario: Assigned team
- **WHEN** a rated team is mapped to an alignment school assigned Division 4 for boys soccer in the current cycle
- **THEN** that team's final rating row shows division 4 and status `assigned`

#### Scenario: Unmapped team
- **WHEN** a rated team has no crosswalk entry
- **THEN** its row has an empty division and status `unknown`, and it still appears in the overall ranking

### Requirement: Per-division rank
The final ratings output SHALL include each assigned team's rank within its division, ordered by Elo descending, alongside its overall rank.

#### Scenario: Rank within division
- **WHEN** three Division 2 teams have Elo 1700, 1650, and 1600
- **THEN** their division ranks are 1, 2, and 3 regardless of their overall ranks

### Requirement: Division on game-level outputs
The per-game Elo results SHALL include home and visitor division resolved for each game's own date, so analytics over games (e.g., cross-division results) need no separate join.

#### Scenario: Cross-division game
- **WHEN** a Division 1 team plays a Division 3 team on 2026-10-15
- **THEN** that game's row shows home and visitor divisions of 1 and 3

### Requirement: Markdown report grouped by division
The sport markdown report SHALL keep the overall Elo table and add a section per division listing that division's teams by division rank, followed by a section for non-member and unknown teams.

#### Scenario: Report sections
- **WHEN** the boys soccer report is generated for a season with Divisions 1 through 5 assigned
- **THEN** the report contains the overall table, one table each for Divisions 1-5, and an "Other teams" table

#### Scenario: Sport with no alignment
- **WHEN** a sport has no alignment data for the current cycle
- **THEN** the report contains only the overall table and states that division data is unavailable

### Requirement: Division as a filterable dimension
Ratings and game outputs SHALL expose division as a plain column so a consumer can select a sport and division and obtain its teams' current Elo and game history without further joins.

#### Scenario: Analyst filters by division
- **WHEN** an analyst loads the boys basketball final ratings and filters to division 3
- **THEN** the result is exactly the Division 3 teams with their Elo and division ranks
