import pandas as pd
import pytest

from elo import Elo
from high_school_elo import load_sport_games

COLUMNS = ["date", "game_id", "status", "home_team", "visitor_team", "home_score", "visitor_score"]


def write_file(tmp_path, name, rows):
    pd.DataFrame(rows, columns=COLUMNS).to_csv(tmp_path / name, index=False)


def test_winter_season_spanning_files_is_one_deduplicated_season(tmp_path):
    write_file(tmp_path, "hoops-2024.csv", [
        ["2024-12-10", 1, "FINAL", "A", "B", 50, 40],
    ])
    write_file(tmp_path, "hoops-2025.csv", [
        ["2025-12-05", 2, "FINAL", "A", "B", 60, 55],
        ["2026-01-08", 3, "UPCOMING", "B", "A", None, None],
    ])
    write_file(tmp_path, "hoops-2026.csv", [
        ["2026-01-08", 3, "FINAL", "B", "A", 45, 44],
        ["2026-02-01", 4, "FINAL", "A", "B", 70, 61],
    ])
    games = load_sport_games("hoops", data_dir=tmp_path).set_index("game_id")
    assert sorted(games.index) == [1, 2, 3, 4]
    assert games.loc[3, "status"] == "FINAL"
    assert games["season"].to_dict() == {1: 2024, 2: 2026, 3: 2026, 4: 2026}


def test_completed_row_beats_newer_stale_row(tmp_path):
    write_file(tmp_path, "fh-2025.csv", [["2025-10-01", 7, "FINAL", "A", "B", 2, 1]])
    write_file(tmp_path, "fh-2026.csv", [["2025-10-01", 7, "POSTPONED", "A", "B", None, None]])
    games = load_sport_games("fh", data_dir=tmp_path)
    assert games["status"].tolist() == ["FINAL"]


def test_fall_seasons_keep_file_year(tmp_path):
    write_file(tmp_path, "fh-2024.csv", [["2024-09-10", 1, "FINAL", "A", "B", 2, 1]])
    write_file(tmp_path, "fh-2025.csv", [["2025-09-10", 2, "FINAL", "A", "B", 3, 1]])
    games = load_sport_games("fh", data_dir=tmp_path)
    assert games.sort_values("game_id")["season"].tolist() == [2024, 2025]


def test_season_regression_parameter():
    elo = Elo(teams=["A"], season_regression=0.2)
    elo.set_rating("A", 1605)
    elo.regress_towards_mean()
    assert elo.team_rating("A") == pytest.approx(1605 - 0.2 * 100)
