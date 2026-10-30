# Spec Delta

## Purpose

Defines the per-sport game records collected from the Boston Globe scoreboard API, including the fields downstream Elo and reporting rely on.

## ADDED Requirements

### Requirement: Tournament fields on game records
Each game record SHALL include `tourney_name` (e.g., "MIAA Division 3", "NEPSAC Class A") and `tourney_level` (e.g., "First round", "Final") as provided by the API, left empty for regular-season games.

#### Scenario: Tournament game
- **WHEN** a fetched game has tourneyName "MIAA Division 1" and tourneyLevel "Quarterfinals"
- **THEN** the stored record has `tourney_name` "MIAA Division 1" and `tourney_level` "Quarterfinals"

#### Scenario: Regular-season game
- **WHEN** a fetched game has null tournament fields
- **THEN** the stored record has empty `tourney_name` and `tourney_level`

### Requirement: Backward-compatible game files
Existing game CSVs without tournament columns SHALL remain readable, and updating such a file SHALL add the columns with empty values for prior rows unless those games are re-fetched.

#### Scenario: Update an older file
- **WHEN** a date is processed into a sport CSV that predates the tournament columns
- **THEN** the file gains both columns, new or refreshed games are populated, and other rows are empty

### Requirement: Tournament backfill
The system SHALL support re-fetching past dates so tournament fields are populated for historical tournament games in seasons already collected.

#### Scenario: Backfill fall 2025 tournament
- **WHEN** the date range covering the November 2025 tournaments is reprocessed
- **THEN** those games' records carry their MIAA division tournament names
