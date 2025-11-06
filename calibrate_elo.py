"""
Calibration script for optimizing Elo parameters for high school sports.

This script uses grid search with k-fold cross-validation to find optimal
Elo parameters (spread_factor, k, home_field) for each sport.

Usage:
    python calibrate_elo.py field-hockey --params spread_factor
    python calibrate_elo.py football --params spread_factor,k,home_field
    python calibrate_elo.py --all
"""

from elo import Elo
import pandas as pd
import numpy as np
import glob
import os
import sys
import argparse
from itertools import product


# Default parameter search spaces
PARAM_GRIDS = {
    "spread_factor": [10, 15, 20, 25, 30, 35, 40, 45, 50],
    "k": [10, 15, 20, 25, 30],
    "home_field": [25, 35, 50, 65, 75]
}

# Default values (from Elo class)
DEFAULT_PARAMS = {
    "spread_factor": 25,
    "k": 20,
    "home_field": 50,
    "rating_mean": 1505
}


def load_sport_data(sport):
    """
    Load all game data for a specific sport.

    Args:
        sport (str): Sport name (e.g., "field-hockey", "football")

    Returns:
        DataFrame: Combined game data from all seasons, or None if no data found
    """
    data_files = glob.glob(f"data/{sport}-*.csv")
    if not data_files:
        return None

    all_games = []
    for file in data_files:
        df = pd.read_csv(file)
        # Extract year from filename (e.g., "field-hockey-2025.csv" -> 2025)
        year = int(os.path.basename(file).split("-")[-1].replace(".csv", ""))
        df["season"] = year
        all_games.append(df)

    games_df = pd.concat(all_games, ignore_index=True)

    # Filter for completed games with valid scores
    completed_games = games_df[
        (games_df["status"] == "FINAL") &
        (games_df["home_score"].notna()) &
        (games_df["visitor_score"].notna())
    ].copy()

    return completed_games


def compute_elo_with_params(games_df, params):
    """
    Compute Elo ratings for all games with given parameters.

    Args:
        games_df (DataFrame): Game data with columns for teams, scores, dates, seasons
        params (dict): Elo parameters (spread_factor, k, home_field, rating_mean)

    Returns:
        DataFrame: Games with Elo predictions added
    """
    games = games_df.copy()

    # Initialize prediction columns
    games["pred_point_spread"] = 0.0
    games["actual_point_spread"] = 0.0

    # Sort games chronologically
    games["date"] = pd.to_datetime(games["date"])
    games = games.sort_values(["season", "date"]).reset_index(drop=True)

    # Get all teams
    teams = set(
        list(games["home_team"].unique()) +
        list(games["visitor_team"].unique())
    )

    # Initialize Elo system with provided parameters
    elo_system = Elo(
        teams=teams,
        k=params["k"],
        home_field=params["home_field"],
        spread_factor=params["spread_factor"],
        rating_mean=params["rating_mean"]
    )

    seasons = sorted(games["season"].unique())

    for season in seasons:
        season_games = games[games["season"] == season]

        for ix, game in season_games.iterrows():
            home_team = game["home_team"]
            away_team = game["visitor_team"]
            home_score = game["home_score"]
            away_score = game["visitor_score"]

            # Calculate predictions before updating
            pred_point_spread = elo_system.point_spread(home_team, away_team)
            actual_point_spread = home_score - away_score

            # Store predictions
            games.at[ix, "pred_point_spread"] = pred_point_spread
            games.at[ix, "actual_point_spread"] = actual_point_spread

            # Update ratings
            elo_system.update_ratings(home_team, home_score, away_team, away_score)

        # Regress towards mean between seasons (except for the most recent season)
        if season != max(seasons):
            elo_system.regress_towards_mean()

    return games


def k_fold_cross_validate(games_df, params, k=5):
    """
    Perform k-fold cross-validation to evaluate parameters.

    Args:
        games_df (DataFrame): All game data
        params (dict): Elo parameters to evaluate
        k (int): Number of folds for cross-validation

    Returns:
        dict: Average error metrics across all folds
    """
    # Sort games chronologically
    games_df = games_df.sort_values(["season", "date"]).reset_index(drop=True)

    # Split into k folds (chronological splits to respect temporal ordering)
    fold_size = len(games_df) // k
    mae_scores = []
    rmse_scores = []

    for fold_idx in range(k):
        # Define validation fold
        val_start = fold_idx * fold_size
        val_end = val_start + fold_size if fold_idx < k - 1 else len(games_df)

        # Train on all data except validation fold
        train_df = pd.concat([
            games_df.iloc[:val_start],
            games_df.iloc[val_end:]
        ]).reset_index(drop=True)

        val_df = games_df.iloc[val_start:val_end].reset_index(drop=True)

        # Compute Elo on training data
        train_with_elo = compute_elo_with_params(train_df, params)

        # Compute Elo on validation data
        val_with_elo = compute_elo_with_params(val_df, params)

        # Evaluate on validation fold
        predicted = val_with_elo["pred_point_spread"].tolist()
        actual = val_with_elo["actual_point_spread"].tolist()

        mae = Elo.calculate_mae(predicted, actual)
        rmse = Elo.calculate_rmse(predicted, actual)

        mae_scores.append(mae)
        rmse_scores.append(rmse)

    return {
        "mae_mean": np.mean(mae_scores),
        "mae_std": np.std(mae_scores),
        "rmse_mean": np.mean(rmse_scores),
        "rmse_std": np.std(rmse_scores),
        "count": len(games_df)
    }


def grid_search(sport, param_names, param_grids=None, k_folds=5, verbose=True):
    """
    Perform grid search to find optimal parameters.

    Args:
        sport (str): Sport name
        param_names (list): List of parameter names to optimize
        param_grids (dict, optional): Custom parameter grids
        k_folds (int): Number of folds for cross-validation
        verbose (bool): Print progress updates

    Returns:
        dict: Results including best parameters and all tested combinations
    """
    # Load data for the sport
    games_df = load_sport_data(sport)
    if games_df is None or len(games_df) == 0:
        return {
            "error": f"No data found for sport: {sport}",
            "sport": sport
        }

    # Skip sports with insufficient data
    min_games = k_folds * 10  # At least 10 games per fold
    if len(games_df) < min_games:
        return {
            "error": f"Insufficient data (only {len(games_df)} games, need at least {min_games})",
            "sport": sport
        }

    if verbose:
        print(f"\nCalibrating Elo parameters for {sport}")
        print(f"Total games: {len(games_df)}")
        print(f"Parameters to optimize: {', '.join(param_names)}")
        print(f"Using {k_folds}-fold cross-validation")

    # Use default grids if none provided
    if param_grids is None:
        param_grids = PARAM_GRIDS

    # Build parameter combinations
    param_values = []
    for param_name in param_names:
        if param_name in param_grids:
            param_values.append(param_grids[param_name])
        else:
            param_values.append([DEFAULT_PARAMS[param_name]])

    # Generate all combinations
    combinations = list(product(*param_values))
    total_combinations = len(combinations)

    if verbose:
        print(f"Testing {total_combinations} parameter combinations...\n")

    # Test each combination
    results = []
    best_mae = float("inf")
    best_params = None

    for idx, combination in enumerate(combinations):
        # Build params dict
        params = DEFAULT_PARAMS.copy()
        for param_name, value in zip(param_names, combination):
            params[param_name] = value

        # Evaluate with cross-validation
        metrics = k_fold_cross_validate(games_df, params, k=k_folds)

        result = {
            "params": {name: params[name] for name in param_names},
            "metrics": metrics
        }
        results.append(result)

        # Track best parameters
        if metrics["mae_mean"] < best_mae:
            best_mae = metrics["mae_mean"]
            best_params = result

        if verbose and (idx + 1) % max(1, total_combinations // 10) == 0:
            progress = (idx + 1) / total_combinations * 100
            print(f"Progress: {progress:.0f}% ({idx + 1}/{total_combinations})")

    if verbose:
        print("\n" + "=" * 60)
        print("CALIBRATION RESULTS")
        print("=" * 60)
        print(f"\nBest parameters for {sport}:")
        for param_name, value in best_params["params"].items():
            print(f"  {param_name}: {value}")
        print(f"\nValidation metrics (averaged across {k_folds} folds):")
        print(f"  MAE:  {best_params['metrics']['mae_mean']:.3f} ± {best_params['metrics']['mae_std']:.3f}")
        print(f"  RMSE: {best_params['metrics']['rmse_mean']:.3f} ± {best_params['metrics']['rmse_std']:.3f}")
        print(f"  Games: {best_params['metrics']['count']}")

    return {
        "sport": sport,
        "best_params": best_params["params"],
        "best_metrics": best_params["metrics"],
        "all_results": results
    }


def main():
    """Main entry point for calibration script."""
    parser = argparse.ArgumentParser(
        description="Calibrate Elo parameters for high school sports"
    )
    parser.add_argument(
        "sport",
        nargs="?",
        help="Sport name (e.g., field-hockey, football). Omit with --all to calibrate all sports."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Calibrate all available sports"
    )
    parser.add_argument(
        "--params",
        default="spread_factor",
        help="Comma-separated list of parameters to optimize (spread_factor,k,home_field)"
    )
    parser.add_argument(
        "--k-folds",
        type=int,
        default=5,
        help="Number of folds for cross-validation (default: 5)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Parse parameter names
    param_names = [p.strip() for p in args.params.split(",")]

    # Validate parameter names
    valid_params = {"spread_factor", "k", "home_field"}
    invalid_params = set(param_names) - valid_params
    if invalid_params:
        print(f"Error: Invalid parameter names: {invalid_params}")
        print(f"Valid parameters: {valid_params}")
        sys.exit(1)

    # Determine which sports to calibrate
    if args.all:
        # Get all available sports
        from high_school_elo import get_available_sports
        sports = get_available_sports()
        if not sports:
            print("No sports data files found in data/ directory")
            sys.exit(1)
    elif args.sport:
        sports = [args.sport]
    else:
        parser.print_help()
        sys.exit(1)

    # Run calibration for each sport
    all_results = []
    for sport in sports:
        result = grid_search(
            sport,
            param_names,
            k_folds=args.k_folds,
            verbose=not args.quiet
        )
        all_results.append(result)

        if not args.quiet and len(sports) > 1:
            print("\n" + "=" * 60 + "\n")

    # If calibrating multiple sports, print summary
    if len(sports) > 1 and not args.quiet:
        print("\n" + "=" * 60)
        print("SUMMARY - BEST PARAMETERS FOR ALL SPORTS")
        print("=" * 60)
        for result in all_results:
            if "error" in result:
                print(f"\n{result['sport']}: {result['error']}")
            else:
                print(f"\n{result['sport']}:")
                for param_name, value in result["best_params"].items():
                    print(f"  {param_name}: {value}")
                metrics = result["best_metrics"]
                print(f"  MAE: {metrics['mae_mean']:.3f} ± {metrics['mae_std']:.3f}")


if __name__ == "__main__":
    main()
