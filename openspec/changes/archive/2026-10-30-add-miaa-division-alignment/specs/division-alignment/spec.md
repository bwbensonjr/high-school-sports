# Spec Delta

## Purpose

Maintains the authoritative relationship between MIAA member schools, sports, and tournament divisions for each two-year MIAA alignment cycle, and resolves which cycle applies to a given date.

## ADDED Requirements

### Requirement: Alignment cycle identification
An alignment cycle SHALL be identified by its first and last school years in the form `YYYY-YY` (e.g., `2025-27` covering 2025-26 and 2026-27). Each cycle SHALL be ingested from MIAA's published per-sport final alignment documents for that cycle.

#### Scenario: Ingest the current cycle
- **WHEN** the operator runs alignment ingestion for cycle `2025-27`
- **THEN** the system fetches every published per-sport alignment document listed for that cycle and writes a normalized alignment dataset for `2025-27`

#### Scenario: Sport document not yet published
- **WHEN** a sport for the cycle is listed by MIAA as not yet published (e.g., alpine and nordic ski)
- **THEN** ingestion completes for the other sports and reports the missing sport by name

### Requirement: Normalized alignment record
Each alignment record SHALL contain cycle, MIAA sport, season, gender, school, aligned school, city, section, final division, CEM enrollment, private-school flag, appeal flags, and co-op role and host school when present. Final division SHALL come from the document's final division column, not be inferred from enrollment.

#### Scenario: Private school bumped up a division
- **WHEN** a school's row is flagged as private and lists a final division
- **THEN** the record's division equals the listed final division and its private flag is true

#### Scenario: Sectional division
- **WHEN** a swimming, golf, gymnastics, or wrestling row lists its final division as "CW 1"
- **THEN** the record's section is "CW" and its division is 1

#### Scenario: Appeal flag in its own column
- **WHEN** a row has "Y" under the appeal-granted column rather than the private-school column
- **THEN** the record's private flag is false and its appeal flags record the appeal

#### Scenario: Co-op guest school
- **WHEN** a row identifies a school as a co-op guest of a host school
- **THEN** the record keeps the guest school name, a co-op role of guest, and the host school name

### Requirement: Ingestion validates document shape
Ingestion SHALL fail for a sport, without writing partial records for it, when the document's rows cannot be parsed into the required fields or a final division value is not a recognized division.

#### Scenario: Unrecognized layout
- **WHEN** a sport document's table lacks a recognizable final division column
- **THEN** that sport is reported as failed and no records for it are written

### Requirement: Reproducible committed dataset
The normalized alignment dataset for each cycle SHALL be committed to the repository so that daily processing never depends on fetching MIAA documents. Re-running ingestion for a cycle SHALL replace that cycle's records and leave other cycles untouched.

#### Scenario: Re-ingest after an appeal revision
- **WHEN** MIAA revises a sport document mid-cycle and ingestion for `2025-27` is re-run
- **THEN** the `2025-27` records reflect the revised document and records for any other cycle are unchanged

### Requirement: MIAA sport to project sport mapping
The system SHALL maintain an explicit mapping from (MIAA sport, gender, season) to the project's sport slug. MIAA sports without a project sport, and project sports without an MIAA alignment, SHALL be listed rather than silently dropped.

#### Scenario: Volleyball by season
- **WHEN** alignment records exist for MIAA fall volleyball and spring volleyball
- **THEN** fall volleyball maps to `girls-volleyball` and spring volleyball maps to `boys-volleyball`

#### Scenario: One document for both genders
- **WHEN** the MIAA cross country document lists schools without a gender
- **THEN** its records apply to both `boys-cross-country` and `girls-cross-country`

### Requirement: Cycle resolution by date
The applicable cycle for a game SHALL be determined from the game date's school year, where a school year begins on August 1, not from the year in a data file name.

#### Scenario: Winter game in January
- **WHEN** a boys basketball game is dated 2026-01-10 and is stored in a file named for 2025
- **THEN** its school year is 2025-26 and its cycle is `2025-27`

#### Scenario: Date outside any ingested cycle
- **WHEN** a game is dated 2024-12-01 and no cycle covering 2024-25 has been ingested
- **THEN** no division is resolved for that game and the result is an explicit unknown, not an error
