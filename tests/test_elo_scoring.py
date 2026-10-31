import math

import numpy as np
import pandas as pd
import pytest

from calibrate_elo import replay_rating_differences
from elo import Elo
from high_school_elo import SCORE_ORDER, SPORT_CONFIG, format_spread, home_margins, process_game_elo


def games_frame(rows):
    """Rows of (home_score, visitor_score, home_outcome)."""
    return pd.DataFrame(rows, columns=["home_score", "visitor_score", "home_outcome"])


def test_higher_score_wins_by_default_and_ignores_outcome():
    # One conflicting record (home lost 0-1 but outcome says home won) keeps the score's verdict
    games = games_frame([(3, 1, 1), (0, 2, 0), (1, 1, 2), (0, 1, 1)])
    assert home_margins(games, "field-hockey").tolist() == [2, -2, 0, -1]


def test_lower_score_wins_in_cross_country():
    games = games_frame([(15, 50, 1), (40, 20, 0), (28, 28, 2)])
    assert SCORE_ORDER["girls-cross-country"] == "lower"
    assert home_margins(games, "girls-cross-country").tolist() == [35, -20, 0]


def test_golf_follows_recorded_outcome_across_formats():
    # Stroke play (lower wins), match play points (higher wins), a tie, and a missing outcome
    games = games_frame([(160, 175, 1), (5.5, 3.5, 1), (4, 5, 0), (4.5, 4.5, 2), (170, 160, None)])
    assert SCORE_ORDER["boys-golf"] == "outcome"
    assert home_margins(games, "boys-golf").tolist() == [15, 2, -1, 0, 10]


def test_update_ratings_matches_margin_update():
    by_score = Elo(teams=["A", "B"], k=30, home_field=40)
    by_margin = Elo(teams=["A", "B"], k=30, home_field=40)
    assert by_score.update_ratings("A", 3, "B", 1) == by_margin.update_ratings_margin("A", "B", 2)


def test_lower_score_win_raises_winner_rating():
    elo = Elo(teams=["Home", "Away"], k=30, home_field=0)
    margin = home_margins(games_frame([(15, 50, 1)]), "boys-cross-country").iloc[0]
    new_home, new_away = elo.update_ratings_margin("Home", "Away", margin)
    assert new_home > 1500 > new_away


def test_without_margin_of_victory_only_result_counts():
    narrow = Elo(teams=["A", "B"], k=30, home_field=0, margin_of_victory=False)
    wide = Elo(teams=["A", "B"], k=30, home_field=0, margin_of_victory=False)
    assert narrow.update_ratings_margin("A", "B", 1) == wide.update_ratings_margin("A", "B", 80)
    # A win from even ratings moves k * 0.5 points
    assert narrow.team_rating("A") == pytest.approx(1515)
    assert math.isnan(narrow.point_spread("A", "B"))


def test_golf_configured_without_spreads():
    for sport in ("boys-golf", "girls-golf"):
        assert SPORT_CONFIG[sport]["margin_of_victory"] is False


def test_process_game_elo_records_oriented_margin_and_no_golf_spread():
    games = pd.DataFrame({
        "date": ["2026-09-01", "2026-09-02"],
        "season": [2026, 2026],
        "home_team": ["A", "B"],
        "visitor_team": ["B", "A"],
        "home_score": [160.0, 4.0],
        "visitor_score": [175.0, 5.0],
        "home_outcome": [1.0, 0.0],
    })
    elo = Elo(teams=["A", "B"], **SPORT_CONFIG["boys-golf"])
    result = process_game_elo(elo, games, "boys-golf")
    assert result["actual_point_spread"].tolist() == [15, -1]
    assert result["pred_point_spread"].isna().all()
    assert elo.team_rating("A") > elo.team_rating("B")


def test_replay_uses_precomputed_margins():
    games = pd.DataFrame({
        "season": [2026, 2026],
        "home_team": ["A", "A"],
        "visitor_team": ["B", "B"],
        "home_score": [15, 20],
        "visitor_score": [50, 40],
        "home_outcome": [1, 1],
    })
    games["home_margin"] = home_margins(games, "boys-cross-country")
    diffs = replay_rating_differences(games, k=30, home_field=0)
    assert diffs[0] == 0
    assert diffs[1] > 0  # A won the first meet with the lower score


def test_format_spread():
    assert format_spread(2.04) == "+2.0"
    assert format_spread(-1.6) == "-1.6"
    assert format_spread(np.nan) == ""
