import pandas as pd

import pytest

from process_games import neutral_site_from_label, process_games_json, venue_from_label


def game(game_id, date, status, home_score="", visitor_score=""):
    return {
        "id": game_id,
        "date": date,
        "status": status,
        "teams": {
            "home": {"id": 100, "name": "Team A", "score": home_score, "outcome": None},
            "visitor": {"id": 101, "name": "Team B", "score": visitor_score, "outcome": None},
        },
        "homeConference": "League 1",
        "visitorConference": "League 1",
        "time": "4:00 P.M.",
        "overtime": None,
        "isShootoutWin": 0,
    }


def scoreboard(*games):
    return {
        "date": "2026-04-01",
        "dates": [{"date": "2026-04-01", "sports": [{"id": 1, "name": "softball", "games": list(games)}]}],
    }


def stored(game_id):
    df = pd.read_csv("data/softball-2026.csv")
    rows = df[df["game_id"] == game_id]
    assert len(rows) == 1
    return rows.iloc[0]


def test_stale_refetch_does_not_overwrite_final(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Rescheduled game played and recorded as FINAL on its new date
    process_games_json(scoreboard(game(1, "2026-05-09", "FINAL", "4", "1")))
    # Re-fetching an older window still lists it as POSTPONED on the original date
    process_games_json(scoreboard(game(1, "2026-04-01", "POSTPONED")))
    row = stored(1)
    assert row["status"] == "FINAL"
    assert row["date"] == "2026-05-09"
    assert row["home_score"] == 4


def test_upcoming_and_suspended_do_not_overwrite_final(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    process_games_json(scoreboard(game(1, "2026-04-01", "FINAL", "3", "2"), game(2, "2026-04-01", "FINAL", "5", "0")))
    process_games_json(scoreboard(game(1, "2026-04-01", "UPCOMING"), game(2, "2026-04-01", "SUSPENDED")))
    assert stored(1)["status"] == "FINAL"
    assert stored(2)["status"] == "FINAL"


def test_final_score_correction_still_applies(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    process_games_json(scoreboard(game(1, "2026-04-01", "FINAL", "3", "2")))
    process_games_json(scoreboard(game(1, "2026-04-01", "FINAL", "3", "4")))
    assert stored(1)["visitor_score"] == 4


def test_forfeit_ruling_replaces_final(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    process_games_json(scoreboard(game(1, "2026-04-01", "FINAL", "3", "2")))
    process_games_json(scoreboard(game(1, "2026-04-01", "FORFEIT (Home)")))
    assert stored(1)["status"] == "FORFEIT (Home)"


def test_upcoming_game_updated_to_final(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    process_games_json(scoreboard(game(1, "2026-04-01", "UPCOMING")))
    process_games_json(scoreboard(game(1, "2026-04-01", "FINAL", "6", "1"), game(2, "2026-04-02", "UPCOMING")))
    assert stored(1)["status"] == "FINAL"
    assert stored(2)["status"] == "UPCOMING"


@pytest.mark.parametrize("label, venue", [
    ("Final at UMass Dartmouth, Dartmouth", "UMass Dartmouth, Dartmouth"),
    ("Non-Playoff at Taunton High School, Taunton", "Taunton High School, Taunton"),
    (
        "MVADA Tournament / Large School (Championship). Championship at Foley Stadium, Worcester",
        "Foley Stadium, Worcester",
    ),
    ("Quarterfinals", ""),
    ("", ""),
    (None, ""),
])
def test_venue_from_label(label, venue):
    assert venue_from_label(label) == venue


@pytest.mark.parametrize("home_team, venue, neutral", [
    ("Uxbridge", "UMass Dartmouth, Dartmouth", True),
    ("Falmouth", "Falmouth Ice Arena, Falmouth", False),
    ("Concord-Carlisle", "Concord-Carlisle, Concord", False),
    ("Methuen/Tewksbury", "Methuen High School, Methuen", False),
    ("Hopedale", "Blackstone Valley IcePlex, Hopedale", False),
    ("Blackstone Valley", "Blackstone Valley IcePlex, Hopedale", False),
    ("St. John’s (Shrewsbury)", "Shrewsbury High School, Shrewsbury", False),
    ("South Shore Voc-Tech", "Greater New Bedford Voc Tech, New Bedford", True),
    ("Bishop Guertin (N.H.)", "Londonderry High, Londonderry, N.H.", True),
    ("West Bridgewater", "Bridgewater-Raynham, Bridgewater", True),
])
def test_neutral_site_excludes_home_team_venue(home_team, venue, neutral):
    expected = venue if neutral else ""
    assert neutral_site_from_label(f"Semifinals at {venue}", home_team) == expected


def test_neutral_site_stored_from_label(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    final = game(1, "2026-04-01", "UPCOMING")
    final["label"] = "Final at Worcester State University, Worcester"
    home = game(2, "2026-04-01", "UPCOMING")
    home["label"] = "Quarterfinals"
    rink = game(4, "2026-04-01", "UPCOMING")
    rink["label"] = "First round at Team A Arena, Springfield"
    process_games_json(scoreboard(final, home, game(3, "2026-04-01", "UPCOMING"), rink))
    assert stored(1)["neutral_site"] == "Worcester State University, Worcester"
    assert stored(1)["venue"] == "Worcester State University, Worcester"
    assert stored(4)["venue"] == "Team A Arena, Springfield"
    assert pd.isna(stored(2)["venue"])
    assert pd.isna(stored(2)["neutral_site"])
    assert pd.isna(stored(3)["neutral_site"])
    assert pd.isna(stored(4)["neutral_site"])
