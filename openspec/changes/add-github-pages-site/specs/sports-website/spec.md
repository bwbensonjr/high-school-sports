# Spec Delta

## Purpose

A public, static GitHub Pages website that presents each sport's recent results, upcoming predictions, and Elo rankings overall and by MIAA division, emphasizing sports currently in season.

## ADDED Requirements

### Requirement: Data-driven static site
The website SHALL render all sport content at runtime from the exported data files, so a daily data update changes what the site shows without any change to its HTML, CSS, or JavaScript.

#### Scenario: New day of data
- **WHEN** the daily export replaces the data files and the site code is unchanged
- **THEN** a visitor loading the site sees the new results, predictions, and rankings

### Requirement: Published on GitHub Pages
The website SHALL be published to the repository's GitHub Pages URL after each scheduled data update and on manual dispatch.

#### Scenario: Scheduled publish
- **WHEN** the daily update workflow completes successfully
- **THEN** the GitHub Pages site serves the newly exported data files

### Requirement: Sport selection emphasizes in-season sports
The website SHALL let a visitor choose any sport in the index, presenting in-season sports first and visually separated from out-of-season sports, in index order.

#### Scenario: Sport list
- **WHEN** field hockey and football are in season and baseball is not
- **THEN** field hockey and football appear in the primary group and baseball appears in a secondary "Other sports" group

### Requirement: Default sport
With no sport chosen in the URL, the website SHALL show the first sport in the index; if no sport is in season, it SHALL still show the first sport.

#### Scenario: Default on first visit
- **WHEN** a visitor opens the site root and field hockey is first in the index
- **THEN** the field hockey page is shown

### Requirement: Shareable location
The selected sport and view SHALL be reflected in the URL, and opening that URL SHALL restore the same sport and view; browser back and forward SHALL move between prior selections.

#### Scenario: Shared link
- **WHEN** a visitor opens a link for girls soccer, Division view, Division 2
- **THEN** girls soccer's Division 2 rankings are shown

#### Scenario: Unknown sport in URL
- **WHEN** the URL names a sport not in the index
- **THEN** the default sport is shown

### Requirement: Per-sport views
Each sport page SHALL offer four views, one visible at a time: Results (recent games), Upcoming (games with predictions), Rankings (all teams by Elo across divisions), and Divisions (teams ranked within a chosen division).

#### Scenario: Switching views
- **WHEN** a visitor on the Results view selects Rankings
- **THEN** the overall Elo table replaces the results list without reloading the page

### Requirement: Results view
The Results view SHALL list recent games newest first, grouped by date, showing each team with its current-season record and score, with the winner emphasized, and showing tournament name and level for tournament games.

#### Scenario: Winner emphasis
- **WHEN** Sandwich beats Hingham 3-1
- **THEN** Sandwich's name and score are visually stronger than Hingham's

#### Scenario: Team record
- **WHEN** Uxbridge's current-season record is 12 wins, 1 loss, and 3 ties
- **THEN** Uxbridge is shown as "Uxbridge (12-1-3)", with the record visually secondary to the name

#### Scenario: Team without a record
- **WHEN** a team has no completed game this season
- **THEN** its name is shown without a record

### Requirement: Results compared with prediction
Each result with scores and a non-even prediction SHALL show the predicted favorite's spread on its line and a verdict: "As expected" when the favorite won by more than the spread, "Closer than expected" when it won by less or tied, and "Upset" when it lost, with upsets emphasized. Even predictions and forfeits SHALL show no verdict.

#### Scenario: Favorite won as expected
- **WHEN** Shrewsbury was predicted to win by 2.2 and won 8-0
- **THEN** Shrewsbury's line shows -2.2 and the game is tagged "As expected"

#### Scenario: Favorite won by less than expected
- **WHEN** Milton was predicted to win by 3.6 and won 3-1
- **THEN** Milton's line shows -3.6 and the game is tagged "Closer than expected"

#### Scenario: Tie
- **WHEN** Walpole hosted Uxbridge, Uxbridge was predicted to win by 2.0, and the game ended 1-1
- **THEN** the game is tagged "Closer than expected"

#### Scenario: Upset
- **WHEN** Wellesley was predicted to win by 2.7 and lost 0-1
- **THEN** the game is tagged "Upset" with emphasis

### Requirement: Upcoming view
The Upcoming view SHALL list scheduled games soonest first, grouped by date, showing time, both teams with their current-season records, the predicted favorite with the predicted margin, and the favorite's win probability.

#### Scenario: Predicted favorite
- **WHEN** Woburn hosts Beverly with home win probability 23.5% and predicted spread -1.6
- **THEN** the game shows Beverly as favorite by 1.6 with a 77% win probability

#### Scenario: No upcoming games
- **WHEN** a sport has no upcoming games
- **THEN** the view shows a single short message that no games are scheduled

### Requirement: Rankings view
The Rankings view SHALL list teams by overall rank with Elo rounded to a whole number, record, and division, showing the top 25 and revealing the rest on request.

#### Scenario: Long list
- **WHEN** a sport has 300 ranked teams
- **THEN** 25 rows are shown with a control to show all

### Requirement: Divisions view
The Divisions view SHALL let a visitor choose one division and list its teams by division rank with Elo and record, plus a choice for teams outside the alignment; when the sport has no division data, the view SHALL say so instead of showing a selector.

#### Scenario: Choose division
- **WHEN** a visitor selects Division 4 for boys soccer
- **THEN** only Division 4 teams are listed, ranked 1 to N by Elo

#### Scenario: Sport without alignment
- **WHEN** the sport's data marks divisions as unavailable
- **THEN** the Divisions view shows a short unavailable message

### Requirement: Data freshness
The website SHALL show when the data was last updated, taken from the index timestamp.

#### Scenario: Last updated
- **WHEN** the index timestamp is 2026-10-31 08:24
- **THEN** the page shows that update time in a secondary position

### Requirement: Load failure
If a data file cannot be loaded, the website SHALL show a short error in place of the affected content and keep sport selection usable.

#### Scenario: Missing sport file
- **WHEN** a sport's data file returns an error
- **THEN** that sport's content area shows an error message and other sports remain selectable

### Requirement: Accessible and responsive presentation
The website SHALL meet WCAG 2.1 AA text contrast in light and dark color schemes, follow the system color preference, use semantic headings, tables, and labeled controls in reading order, be fully keyboard operable, and remain usable at 360px width without horizontal page scrolling.

#### Scenario: Dark mode
- **WHEN** the visitor's system prefers a dark color scheme
- **THEN** the site renders in its dark theme with AA contrast

#### Scenario: Keyboard use
- **WHEN** a visitor uses only the keyboard
- **THEN** they can choose a sport, switch views, choose a division, and expand rankings, with visible focus

#### Scenario: Phone width
- **WHEN** the site is viewed at 360px wide
- **THEN** all views are readable without horizontal scrolling of the page
