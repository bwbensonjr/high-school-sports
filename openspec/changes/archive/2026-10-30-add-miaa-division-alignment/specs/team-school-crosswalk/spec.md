# Spec Delta

## Purpose

Links Boston Globe team identities used in game data to MIAA school identities used in alignments, so school-level attributes such as division can be attached to teams and games.

## ADDED Requirements

### Requirement: Crosswalk keyed by Globe team ID
The crosswalk SHALL map each Globe team ID to exactly one of: an MIAA school name, or an explicit non-member status (e.g., NEPSAC/prep, out-of-state). A school mapping SHALL apply across all sports unless overridden for a specific sport.

#### Scenario: School shared across sports
- **WHEN** Globe team ID 4051 (Braintree) is mapped to "Braintree High School"
- **THEN** that mapping applies to Braintree's games in every sport

#### Scenario: Out-of-state opponent
- **WHEN** a Globe team such as "Moses Brown (R.I.)" is recorded as non-member
- **THEN** division lookups for it return non-member rather than unmatched

### Requirement: Sport-specific overrides for co-ops
The crosswalk SHALL support a per-sport override so a combined Globe team (e.g., "New Mission/English High") maps to the MIAA host school whose division governs the co-op in that sport.

#### Scenario: Co-op team division
- **WHEN** a Globe co-op team has a sport override pointing to the co-op's host school
- **THEN** the team's division in that sport is the host school's division

### Requirement: Automated candidate matching
The system SHALL propose crosswalk entries for unmapped Globe teams by comparing normalized names and city against alignment schools, and SHALL never overwrite an existing manually confirmed entry.

#### Scenario: Suffix normalization
- **WHEN** an unmapped Globe team is named "Doherty" and an alignment school is "Doherty Memorial High School"
- **THEN** the system proposes that match

#### Scenario: Manual entry preserved
- **WHEN** a crosswalk entry is marked as manually confirmed and candidate matching is re-run
- **THEN** the entry is unchanged

### Requirement: Validation against tournament divisions
The system SHALL compare each mapped team's alignment division with the MIAA division of any Globe tournament game it played in the same cycle and sport, and SHALL report every disagreement. Tournament teams with no alignment division SHALL be reported separately.

#### Scenario: Agreement
- **WHEN** a team mapped to a Division 3 school played in an "MIAA Division 3" tournament game that cycle
- **THEN** no disagreement is reported for that team

#### Scenario: Disagreement
- **WHEN** a team's alignment division is 2 but it played in an "MIAA Division 3" tournament game
- **THEN** the team, sport, cycle, and both divisions are listed in the validation report

#### Scenario: Tournament team without an alignment row
- **WHEN** a mapped team played in an MIAA tournament but its school has no row in that sport's alignment
- **THEN** the team is listed among tournament teams without an alignment division, not as a disagreement

### Requirement: School name variants
Alignment documents abbreviate or truncate the same school's name differently. Lookups SHALL treat names that normalize alike as one school, and SHALL resolve a truncated crosswalk name to the single same-city school in that sport whose name extends it.

#### Scenario: Truncated name in the crosswalk
- **WHEN** the crosswalk maps a team to "Advanced Math & Science Acad." and the baseball document lists "Advanced Math & Science Acad. Charter" in the same city
- **THEN** the team's baseball division is that row's division

#### Scenario: Shorter name of a different school
- **WHEN** the crosswalk maps a team to "Foxborough Regional Charter School" and the sport lists only "Foxborough High School"
- **THEN** no division is resolved from "Foxborough High School"

### Requirement: Coverage report
For each cycle and sport the system SHALL report counts and names of Globe teams that are mapped, non-member, and unmatched, and alignment schools that have no Globe team.

#### Scenario: Unmatched teams listed
- **WHEN** coverage is generated for boys soccer `2025-27`
- **THEN** every Globe boys soccer team with no crosswalk entry is listed by name and team ID
