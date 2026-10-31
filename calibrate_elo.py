"""
Calibrate K, home field advantage, between-season regression, and spread scaling
for high school sports Elo.

Elo predictions are made with pre-game ratings, so replaying every game in
order and scoring each prediction is already an out-of-sample evaluation.
For each sport:

1. k, home_field, and season_regression are chosen jointly from a grid to
   minimize the log loss of the pre-game home win probability. All drive
   rating updates; season_regression is only searched when the data spans
   more than one season.
2. With ratings replayed at those values, the actual home margin is
   regressed on the pre-game rating difference over the most recent scored
   games, where ratings have matured to the spread that predictions for
   upcoming games will use (the rating spread grows over a sport's first
   seasons, which changes the margin per rating point):
       margin = a + b * (home_elo - away_elo)
   giving spread_factor = 1 / b and spread_home_field = a / b (Elo points).

Margins follow each sport's scoring direction (see
high_school_elo.SCORE_ORDER and home_margins), so sports where the lower
score wins, or where the recorded result decides, are handled. Sports configured with margin_of_victory=False (golf) are rated on
results alone: step 2 is skipped and no spread is predicted.

Games in the first few weeks of the earliest season are not scored, since
every team starts at the same rating. A chronological holdout (fit on the
earlier scored games, evaluate on the later ones) compares the fitted
parameters against the current configuration; a fitted value is recommended
only where it improves on the current one.

Usage:
    python calibrate_elo.py field-hockey
    python calibrate_elo.py --all
"""

import argparse
import glob
import math
import os
import sys

import numpy as np
import pandas as pd

from elo import Elo

K_GRID = [10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200, 250]
HOME_FIELD_GRID = list(range(0, 151, 10))
SEASON_REGRESSION_GRID = [0.0, 0.1, 0.2, 0.33, 0.5, 0.67, 0.8, 1.0]
WARMUP_DAYS = 28
HOLDOUT_FRACTION = 0.3
SPREAD_FIT_FRACTION = 0.4
MIN_LOG_LOSS_GAIN = 0.001
MIN_GAMES = 300


def load_sport_data(sport):
    """
    Load completed games for a sport from all seasons, in chronological order.

    Returns:
        DataFrame: Completed games with a season column, or None if no data found
    """
    from high_school_elo import load_sport_games

    games = load_sport_games(sport)
    if games is None:
        return None
    games = games[
        (games["status"] == "FINAL") &
        games["home_score"].notna() &
        games["visitor_score"].notna()
    ].copy()
    from high_school_elo import home_margins

    games["date"] = pd.to_datetime(games["date"])
    games["home_margin"] = home_margins(games, sport)
    return games.sort_values(by=["season", "date"], kind="mergesort").reset_index(drop=True)


def game_margins(games):
    """Home margins as used for rating updates; home minus visitor score if not precomputed."""
    if "home_margin" in games:
        return games["home_margin"].to_numpy(float)
    return (games["home_score"] - games["visitor_score"]).to_numpy(float)


def replay_rating_differences(games, k, home_field, season_regression=0.33, margin_of_victory=True):
    """
    Replay games through Elo, matching high_school_elo.process_game_elo.

    Returns:
        ndarray: Pre-game home rating minus away rating for each game (no home field)
    """
    elo = Elo(k=k, home_field=home_field, season_regression=season_regression,
              margin_of_victory=margin_of_victory)
    diffs = np.empty(len(games))
    seasons = games["season"].to_numpy()
    rows = zip(games["home_team"], games["visitor_team"], game_margins(games))
    for i, (home, away, margin) in enumerate(rows):
        if i > 0 and seasons[i] != seasons[i - 1]:
            elo.regress_towards_mean()
        for team in (home, away):
            if team not in elo.ratings:
                elo.add_team(team)
        diffs[i] = elo.team_rating(home) - elo.team_rating(away)
        elo.update_ratings_margin(home, away, margin)
    return diffs


def home_results(margins):
    """Convert home margins to results: 1 win, 0 loss, 0.5 tie."""
    return np.where(margins > 0, 1.0, np.where(margins < 0, 0.0, 0.5))


def log_loss(diffs, home_field, results):
    """Mean log loss of the home win probability."""
    prob = 1 / (1 + 10 ** (-(diffs + home_field) / 400))
    prob = np.clip(prob, 1e-9, 1 - 1e-9)
    return float(-np.mean(results * np.log(prob) + (1 - results) * np.log(1 - prob)))


def fit_spread(diffs, margins):
    """
    Fit margin = (diff + spread_home_field) / spread_factor by least squares.

    Returns:
        tuple: (spread_factor, spread_home_field)
    """
    design = np.column_stack([np.ones(len(diffs)), diffs])
    (intercept, slope), *_ = np.linalg.lstsq(design, margins, rcond=None)
    if slope <= 0:
        raise ValueError("Rating differences do not predict margins")
    return 1 / slope, intercept / slope


def spread_rmse(diffs, margins, spread_factor, spread_home_field):
    """Root mean squared error of predicted spreads."""
    predicted = (diffs + spread_home_field) / spread_factor
    return float(np.sqrt(np.mean((margins - predicted) ** 2)))


def scored_mask(games, warmup_days=WARMUP_DAYS):
    """Exclude the opening weeks of the earliest season, when all ratings are equal."""
    first = games["season"].min()
    start = games.loc[games["season"] == first, "date"].min()
    warmup = (games["season"] == first) & (games["date"] < start + pd.Timedelta(days=warmup_days))
    return ~warmup.to_numpy()


def recent_mask(mask, fraction):
    """Keep only the most recent fraction of the games selected by mask."""
    scored = np.flatnonzero(mask)
    recent = np.zeros_like(mask)
    recent[scored[int(len(scored) * (1 - fraction)):]] = True
    return recent


def replay_grid(games, regression_grid, margin_of_victory=True):
    """Replay ratings for every (k, home_field, season_regression) combination in the grid."""
    return {
        (k, home_field, regression): replay_rating_differences(
            games, k, home_field, regression, margin_of_victory)
        for k in K_GRID
        for home_field in HOME_FIELD_GRID
        for regression in regression_grid
    }


def fit_rating_parameters(replays, results, mask):
    """
    Choose (k, home_field, season_regression) from the grid by log loss of the
    home win probability.

    Returns:
        tuple: (k, home_field, season_regression)
    """
    losses = {
        params: log_loss(diffs[mask], params[1], results[mask])
        for params, diffs in replays.items()
    }
    return min(losses, key=losses.get)


def fit_spread_recent(games, diffs, mask):
    """Fit spread parameters on the most recent scored games."""
    margins = game_margins(games)
    recent = recent_mask(mask, SPREAD_FIT_FRACTION)
    return fit_spread(diffs[recent], margins[recent])


def calibrate_sport(sport, current):
    """
    Calibrate one sport and recommend parameters against its current configuration.

    k, home_field, and season_regression are fit jointly (season_regression
    only when the data spans more than one season). They are recommended only
    when the combination fitted on the earlier scored games beats the current
    one on the later holdout games by at least MIN_LOG_LOSS_GAIN in log loss. Since k sets the
    width of the rating scale, the spread parameters are always refit when the
    rating parameters change; otherwise they are refit only when that improves
    holdout RMSE.

    Args:
        sport (str): Sport slug
        current (dict): Current Elo overrides for the sport (from SPORT_CONFIG)

    Returns:
        dict: Recommended parameters and holdout comparison, or an error entry
    """
    games = load_sport_data(sport)
    if games is None or len(games) < MIN_GAMES:
        count = 0 if games is None else len(games)
        return {"sport": sport, "error": f"insufficient data ({count} games, need {MIN_GAMES})"}

    defaults = Elo()
    cur_k = current.get("k", defaults.k)
    cur_home_field = current.get("home_field", defaults.home_field)
    cur_spread_factor = current.get("spread_factor", defaults.spread_factor)
    cur_spread_home = current.get("spread_home_field", cur_home_field)
    cur_regression = current.get("season_regression", defaults.season_regression)
    margin_of_victory = current.get("margin_of_victory", True)

    margins = game_margins(games)
    results = home_results(margins)
    mask = scored_mask(games)
    test = recent_mask(mask, HOLDOUT_FRACTION)
    train = mask & ~test

    multi_season = games["season"].nunique() > 1
    replays = replay_grid(games, SEASON_REGRESSION_GRID if multi_season else [cur_regression], margin_of_victory)
    current_diffs = replay_rating_differences(games, cur_k, cur_home_field, cur_regression, margin_of_victory)

    # Rating parameters: holdout log loss of a train-fitted combination versus the current one
    train_params = fit_rating_parameters(replays, results, train)
    train_home_field = train_params[1]
    train_diffs = replays[train_params]
    current_log_loss = log_loss(current_diffs[test], cur_home_field, results[test])
    fitted_log_loss = log_loss(train_diffs[test], train_home_field, results[test])
    rating_changed = current_log_loss - fitted_log_loss >= MIN_LOG_LOSS_GAIN
    if rating_changed:
        k, home_field, regression = fit_rating_parameters(replays, results, mask)
        diffs = replays[(k, home_field, regression)]
    else:
        k, home_field, regression = cur_k, cur_home_field, cur_regression
        diffs = current_diffs

    if not margin_of_victory:
        return {
            "sport": sport,
            "games": int(mask.sum()),
            "seasons": int(games["season"].nunique()),
            "k": k,
            "home_field": home_field,
            "season_regression": regression,
            "margin_of_victory": False,
            "holdout_games": int(test.sum()),
            "current_log_loss": current_log_loss,
            "fitted_log_loss": fitted_log_loss,
            "rating_changed": rating_changed,
        }

    # Spread: holdout RMSE of the train-fitted configuration versus the current one
    current_rmse = spread_rmse(current_diffs[test], margins[test], cur_spread_factor, cur_spread_home)
    if rating_changed:
        fitted_rmse = spread_rmse(train_diffs[test], margins[test], *fit_spread_recent(games, train_diffs, train))
    else:
        fitted_rmse = spread_rmse(diffs[test], margins[test], *fit_spread_recent(games, diffs, train))
    if rating_changed or fitted_rmse < current_rmse:
        spread_factor, spread_home_field = fit_spread_recent(games, diffs, mask)
        spread_factor, spread_home_field = round(spread_factor, 1), round(spread_home_field)
    else:
        spread_factor, spread_home_field = cur_spread_factor, cur_spread_home

    return {
        "sport": sport,
        "games": int(mask.sum()),
        "seasons": int(games["season"].nunique()),
        "k": k,
        "home_field": home_field,
        "season_regression": regression,
        "spread_factor": spread_factor,
        "spread_home_field": spread_home_field,
        "home_margin": round(spread_home_field / spread_factor, 2),
        "holdout_games": int(test.sum()),
        "current_log_loss": current_log_loss,
        "fitted_log_loss": fitted_log_loss,
        "rating_changed": rating_changed,
        "current_rmse": current_rmse,
        "fitted_rmse": fitted_rmse,
        "spread_changed": (spread_factor, spread_home_field) != (cur_spread_factor, cur_spread_home),
    }


def print_result(result):
    if "error" in result:
        print(f"{result['sport']}: skipped, {result['error']}")
        return
    if result.get("margin_of_victory") is False:
        print(
            f"{result['sport']}: k={result['k']} home_field={result['home_field']} "
            f"season_regression={result['season_regression']} margin_of_victory=False (no spread) | "
            f"holdout {result['holdout_games']} games: log loss {result['current_log_loss']:.4f} -> "
            f"{result['fitted_log_loss']:.4f}{'' if result['rating_changed'] else ' (kept)'}"
        )
        return
    print(
        f"{result['sport']}: k={result['k']} home_field={result['home_field']} "
        f"season_regression={result['season_regression']} "
        f"spread_factor={result['spread_factor']} spread_home_field={result['spread_home_field']} "
        f"(home margin {result['home_margin']:+.2f}) | holdout {result['holdout_games']} games: "
        f"log loss {result['current_log_loss']:.4f} -> {result['fitted_log_loss']:.4f}"
        f"{'' if result['rating_changed'] else ' (kept)'}, "
        f"RMSE {result['current_rmse']:.3f} -> {result['fitted_rmse']:.3f}"
        f"{'' if result['spread_changed'] else ' (kept)'}"
    )


def main():
    from high_school_elo import SPORT_CONFIG, get_available_sports

    parser = argparse.ArgumentParser(description="Calibrate Elo K, home field, season regression, and spread scaling")
    parser.add_argument("sport", nargs="?", help="Sport slug (e.g., field-hockey)")
    parser.add_argument("--all", action="store_true", help="Calibrate all available sports")
    parser.add_argument("--output", help="Write results to this CSV file")
    args = parser.parse_args()

    if args.all:
        sports = sorted(get_available_sports())
    elif args.sport:
        sports = [args.sport]
    else:
        parser.print_help()
        sys.exit(1)

    results = []
    for sport in sports:
        result = calibrate_sport(sport, SPORT_CONFIG.get(sport, {}))
        print_result(result)
        results.append(result)

    if args.output:
        pd.DataFrame(results).to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
