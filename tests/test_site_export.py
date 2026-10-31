import json
from datetime import date

import pandas as pd

from site_export import (
    build_sport,
    display_name,
    export_site_data,
    index_entry,
    order_index,
)

GAME_COLUMNS = [
    "date", "game_id", "status", "home_team", "home_score", "home_outcome",
    "visitor_team", "visitor_score", "visitor_outcome", "time",
    "tourney_name", "tourney_level", "season", "home_win_prob", "pred_point_spread",
]
FINAL_COLUMNS = ["team", "elo", "team_id", "overall_rank", "division", "division_status", "division_rank"]
TODAY = date(2026, 10, 31)


def game(day, game_id, home, visitor, score=None, status="FINAL", season=2026, **extra):
    """Game row; score is (home, visitor) and sets outcomes (1 win, 0 loss, 2 tie)."""
    home_score = visitor_score = home_outcome = visitor_outcome = None
    if score is not None:
        home_score, visitor_score = score
        if home_score > visitor_score:
            home_outcome, visitor_outcome = 1.0, 0.0
        elif home_score < visitor_score:
            home_outcome, visitor_outcome = 0.0, 1.0
        else:
            home_outcome = visitor_outcome = 2.0
    row = {
        "date": day, "game_id": game_id, "status": status,
        "home_team": home, "home_score": home_score, "home_outcome": home_outcome,
        "visitor_team": visitor, "visitor_score": visitor_score, "visitor_outcome": visitor_outcome,
        "time": None, "tourney_name": None, "tourney_level": None, "season": season,
        "home_win_prob": 0.6, "pred_point_spread": 1.04,
    }
    row.update(extra)
    return row


def games_frame(rows):
    return pd.DataFrame(rows, columns=GAME_COLUMNS)


def final_frame(rows):
    return pd.DataFrame(rows, columns=FINAL_COLUMNS).astype({"division": "string"})


def sport(rows, final_rows, slug="hoops"):
    return build_sport(slug, games_frame(rows), final_frame(final_rows), TODAY, "2026-10-31T06:00-04:00")


def test_display_name():
    assert display_name("boys-skiing-(alpine)") == "Boys Skiing (Alpine)"
    assert display_name("field-hockey") == "Field Hockey"


def test_recent_window_anchored_to_latest_completed_game():
    rows = [
        game("2026-05-31", 1, "A", "B", (2, 1)),
        game("2026-06-01", 2, "A", "B", (3, 1)),
        game("2026-06-14", 3, "B", "A", (0, 4)),
    ]
    data = sport(rows, [["A", 1600, 1, 1, None, "unknown", None], ["B", 1400, 2, 2, None, "unknown", None]])
    assert [g["date"] for g in data["recent"]] == ["2026-06-14", "2026-06-01"]
    assert data["recent"][0] == {"date": "2026-06-14", "home": "B", "hs": 0, "visitor": "A", "vs": 4, "ho": 0, "spread": 1.0}


def test_recent_excludes_prior_seasons_and_keeps_forfeits_and_tournaments():
    rows = [
        game("2025-10-30", 1, "A", "B", (1, 0), season=2025),
        game("2026-10-29", 2, "A", "B", status="FORFEIT (Away)", home_outcome=1.0, visitor_outcome=0.0),
        game("2026-10-30", 3, "A", "B", (2, 1), tourney_name="MIAA Division 3", tourney_level="Final"),
    ]
    data = sport(rows, [["A", 1600, 1, 1, None, "unknown", None], ["B", 1400, 2, 2, None, "unknown", None]])
    assert [g["date"] for g in data["recent"]] == ["2026-10-30", "2026-10-29"]
    assert data["recent"][0]["tourney"] == "MIAA Division 3"
    assert data["recent"][0]["level"] == "Final"
    assert "tourney" not in data["recent"][1]
    assert data["recent"][1]["status"] == "FORFEIT (Away)"


def test_upcoming_excludes_stale_rows_and_keeps_predictions():
    rows = [
        game("2026-10-30", 1, "A", "B", (2, 1)),
        game("2026-10-20", 2, "A", "B", status="UPCOMING"),
        game("2026-11-02", 3, "B", "A", status="UPCOMING", home_win_prob=0.235, pred_point_spread=-1.64, time="1:00 P.M."),
        game("2026-10-31", 4, "A", "B", status="UPCOMING", home_win_prob=0.8812, pred_point_spread=2.61),
    ]
    data = sport(rows, [["A", 1600, 1, 1, None, "unknown", None], ["B", 1400, 2, 2, None, "unknown", None]])
    assert data["upcoming"] == [
        {"date": "2026-10-31", "home": "A", "visitor": "B", "homeProb": 0.881, "spread": 2.6},
        {"date": "2026-11-02", "time": "1:00 P.M.", "home": "B", "visitor": "A", "homeProb": 0.235, "spread": -1.6},
    ]


def test_teams_exclude_inactive_and_rerank_with_records():
    rows = [
        game("2025-10-01", 1, "Old", "A", (5, 0), season=2025),
        game("2026-10-01", 2, "A", "B", (2, 1)),
        game("2026-10-05", 3, "C", "A", (1, 1)),
        game("2026-10-08", 4, "B", "C", (3, 0)),
    ]
    final_rows = [
        ["Old", 1800, 9, 1, "2", "assigned", 1],
        ["A", 1700.4, 1, 2, "2", "assigned", 2],
        ["B", 1650, 2, 3, "2", "assigned", 3],
        ["C", 1500, 3, 4, None, "non-member", None],
    ]
    data = sport(rows, final_rows)
    assert data["teams"] == [
        {"rank": 1, "team": "A", "elo": 1700, "w": 1, "l": 0, "t": 1, "div": "2", "divStatus": "assigned", "divRank": 1},
        {"rank": 2, "team": "B", "elo": 1650, "w": 1, "l": 1, "t": 0, "div": "2", "divStatus": "assigned", "divRank": 2},
        {"rank": 3, "team": "C", "elo": 1500, "w": 0, "l": 1, "t": 1, "divStatus": "non-member"},
    ]
    assert data["hasDivisions"] is True
    assert data["divisions"] == ["2"]


def test_divisions_sorted_numerically_and_by_section():
    rows = [game("2026-10-01", i, f"T{i}", f"U{i}", (1, 0)) for i in range(4)]
    final_rows = [
        ["T0", 1600, 1, 1, "10", "assigned", 1],
        ["T1", 1590, 2, 2, "2", "assigned", 1],
        ["T2", 1580, 3, 3, "S 1", "assigned", 1],
        ["T3", 1570, 4, 4, "C 2", "assigned", 1],
    ]
    assert sport(rows, final_rows)["divisions"] == ["2", "10", "C 2", "S 1"]


def test_sport_without_alignment():
    rows = [game("2026-10-01", 1, "A", "B", (1, 0))]
    data = sport(rows, [["A", 1600, 1, 1, None, "unknown", None], ["B", 1400, 2, 2, None, "unknown", None]])
    assert data["hasDivisions"] is False
    assert data["divisions"] == []
    assert all("div" not in team for team in data["teams"])


def test_in_season_window_edges():
    def entry(rows):
        return index_entry("hoops", games_frame(rows), TODAY)

    assert entry([game("2026-10-17", 1, "A", "B", (1, 0))])["inSeason"] is True
    assert entry([game("2026-10-16", 1, "A", "B", (1, 0))])["inSeason"] is False
    assert entry([game("2026-11-14", 1, "A", "B", status="UPCOMING")])["inSeason"] is True
    assert entry([game("2026-11-15", 1, "A", "B", status="UPCOMING")])["inSeason"] is False
    off = entry([game("2026-06-14", 1, "A", "B", (1, 0)), game("2026-06-01", 2, "A", "B", status="UPCOMING")])
    assert off == {"slug": "hoops", "name": "Hoops", "season": 2026, "inSeason": False, "recentGames": 0}


def test_index_ordering():
    entries = [
        {"name": "Baseball", "inSeason": False, "recentGames": 0},
        {"name": "Football", "inSeason": True, "recentGames": 60},
        {"name": "Archery", "inSeason": False, "recentGames": 0},
        {"name": "Field Hockey", "inSeason": True, "recentGames": 120},
    ]
    assert [e["name"] for e in order_index(entries)] == ["Field Hockey", "Football", "Archery", "Baseball"]


def test_export_writes_index_and_sport_files(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    rows = [game("2026-10-30", 1, "A", "B", (2, 1)), game("2026-11-01", 2, "B", "A", status="UPCOMING")]
    final_rows = [["A", 1600, 1, 1, None, "unknown", None], ["B", 1400, 2, 2, None, "unknown", None]]
    games_frame(rows).to_csv(results / "boys-skiing-(alpine)-elo-ratings.csv", index=False)
    final_frame(final_rows).to_csv(results / "boys-skiing-(alpine)-elo-final.csv", index=False)
    # Ratings without a final file are skipped
    games_frame(rows).to_csv(results / "orphan-elo-ratings.csv", index=False)

    out = tmp_path / "site" / "data"
    export_site_data(results, out, TODAY, "2026-10-31T06:00-04:00")

    index = json.loads((out / "index.json").read_text())
    assert index["date"] == "2026-10-31"
    assert index["generated"] == "2026-10-31T06:00-04:00"
    assert [e["slug"] for e in index["sports"]] == ["boys-skiing-(alpine)"]
    data = json.loads((out / "sports" / "boys-skiing-(alpine).json").read_text())
    assert data["name"] == "Boys Skiing (Alpine)"
    assert len(data["recent"]) == 1 and len(data["upcoming"]) == 1
