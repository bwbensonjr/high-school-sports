import numpy as np
import pandas as pd
import pytest

from calibrate_elo import fit_spread, recent_mask, replay_rating_differences, scored_mask
from elo import Elo


def test_spread_home_field_defaults_to_home_field():
    elo = Elo(teams=["A", "B"], home_field=50, spread_factor=25)
    assert elo.spread_home_field == 50
    assert elo.point_spread("A", "B") == pytest.approx(2.0)


def test_spread_home_field_only_affects_spread():
    base = Elo(teams=["A", "B"], home_field=50, spread_factor=25)
    split = Elo(teams=["A", "B"], home_field=50, spread_factor=25, spread_home_field=10)
    split.set_rating("A", 1600)
    base.set_rating("A", 1600)
    assert split.point_spread("A", "B") == pytest.approx((100 + 10) / 25)
    assert split.home_win_prob("A", "B") == pytest.approx(base.home_win_prob("A", "B"))


def test_fit_spread_recovers_parameters():
    rng = np.random.default_rng(0)
    diffs = rng.normal(0, 150, 5000)
    margins = (diffs + 20) / 50 + rng.normal(0, 0.5, 5000)
    spread_factor, spread_home_field = fit_spread(diffs, margins)
    assert spread_factor == pytest.approx(50, rel=0.02)
    assert spread_home_field == pytest.approx(20, abs=2)


def test_recent_mask_keeps_latest_selected_games():
    mask = np.array([False, True, True, False, True, True, True])
    recent = recent_mask(mask, 0.4)
    assert recent.tolist() == [False, False, False, False, False, True, True]


def test_scored_mask_skips_warmup_of_first_season_only():
    games = pd.DataFrame({
        "season": [2025, 2025, 2026, 2026],
        "date": pd.to_datetime(["2025-09-01", "2025-10-15", "2026-09-01", "2026-09-02"]),
    })
    assert scored_mask(games).tolist() == [False, True, True, True]


def test_replay_matches_elo_updates():
    games = pd.DataFrame({
        "season": [2026, 2026, 2026],
        "home_team": ["A", "B", "A"],
        "visitor_team": ["B", "C", "C"],
        "home_score": [3, 1, 0],
        "visitor_score": [1, 1, 2],
    })
    diffs = replay_rating_differences(games, k=30, home_field=40)
    elo = Elo(teams=["A", "B", "C"], k=30, home_field=40)
    expected = []
    for game in games.itertuples():
        expected.append(elo.team_rating(game.home_team) - elo.team_rating(game.visitor_team))
        elo.update_ratings(game.home_team, game.home_score, game.visitor_team, game.visitor_score)
    assert diffs.tolist() == pytest.approx(expected)
