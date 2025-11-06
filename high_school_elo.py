from elo import Elo
import pandas as pd
import numpy as np
import glob
import os
import sys

# Sport-specific Elo configuration overrides
# Only specify parameters that differ from Elo class defaults (k=20, home_field=50, spread_factor=25)
# Adjust spread_factor based on typical scoring levels in each sport
SPORT_CONFIG = {
    "football": {
        "spread_factor": 15,  # High scoring sport
    },
    "boys-basketball": {
        "spread_factor": 20,  # Medium-high scoring
    },
    "girls-basketball": {
        "spread_factor": 20,  # Medium-high scoring
    },
    "boys-soccer": {
        "spread_factor": 40,  # Low scoring sport
    },
    "girls-soccer": {
        "spread_factor": 40,  # Low scoring sport
    },
    "field-hockey": {
        "spread_factor": 40,  # Low scoring sport
    },
    "volleyball": {
        "spread_factor": 35,  # Points but lower differential
    },
    "girls-volleyball": {
        "spread_factor": 35,  # Points but lower differential
    },
    # Sports not listed here (e.g., boys-golf) will use Elo class defaults
}

def main():
    if len(sys.argv) > 1:
        sport = sys.argv[1]
        compute_elo_ratings(sport)
    else:
        # No sport specified, process all available sports
        sports = get_available_sports()
        if not sports:
            print("No sports data files found in data/ directory")
            return

        print(f"No sport specified. Processing all {len(sports)} available sports...")
        for sport in sorted(sports):
            print(f"\n{'='*60}")
            compute_elo_ratings(sport)
            print(f"{'='*60}")

def get_available_sports():
    """Get list of all available sports from data files."""
    data_files = glob.glob("data/*.csv")
    sports = set()

    for file in data_files:
        filename = os.path.basename(file)
        # Extract sport name from filename (e.g., "field-hockey-2025.csv" -> "field-hockey")
        if filename.endswith(".csv") and "-" in filename:
            # Split by "-" and remove the year part (last element)
            parts = filename.replace(".csv", "").split("-")
            if len(parts) >= 2 and parts[-1].isdigit():  # Last part should be year
                sport = "-".join(parts[:-1])  # Everything except the year
                sports.add(sport)

    return list(sports)

def compute_elo_ratings(sport):
    print(f"Processing {sport} Elo ratings...")

    # Load all available data files for the sport
    data_files = glob.glob(f"data/{sport}-*.csv")
    if not data_files:
        print(f"No data files found for {sport}")
        return

    print(f"Found {len(data_files)} data files: {[os.path.basename(f) for f in data_files]}")

    # Load and combine all games
    all_games = []
    for file in data_files:
        df = pd.read_csv(file)
        # Extract year from filename (e.g., "field-hockey-2025.csv" -> 2025)
        year = int(os.path.basename(file).split("-")[-1].replace(".csv", ""))
        df["season"] = year
        all_games.append(df)

    games_df = pd.concat(all_games, ignore_index=True)

    # Separate completed and upcoming games
    completed_games = games_df[
        (games_df["status"] == "FINAL") &
        (games_df["home_score"].notna()) &
        (games_df["visitor_score"].notna())
    ].copy()

    upcoming_games = games_df[
        (games_df["status"] != "FINAL") |
        (games_df["home_score"].isna()) |
        (games_df["visitor_score"].isna())
    ].copy()

    print(f"Found {len(completed_games)} completed games with valid scores")
    print(f"Found {len(upcoming_games)} upcoming games")

    # Get all teams from both completed and upcoming games
    teams = set(
        list(games_df["home_team"].unique()) +
        list(games_df["visitor_team"].unique())
    )
    print(f"Found {len(teams)} teams")

    # Get sport-specific configuration overrides (if any)
    config = SPORT_CONFIG.get(sport, {})
    if config:
        config_str = ", ".join(f"{k}={v}" for k, v in config.items())
        print(f"Using sport-specific overrides: {config_str}")

    # Initialize Elo system with sport-specific parameters
    # Any parameters not in config will use Elo class defaults
    elo_system = Elo(teams=teams, **config)

    # Process completed games and calculate Elo ratings
    completed_games_with_elo = process_game_elo(elo_system, completed_games, sport)

    # Process upcoming games with current Elo ratings
    upcoming_games_with_elo = process_upcoming_games(elo_system, upcoming_games)

    # Combine all games
    all_games_with_elo = pd.concat([completed_games_with_elo, upcoming_games_with_elo], ignore_index=True)

    # Sort by date for better readability
    all_games_with_elo["date"] = pd.to_datetime(all_games_with_elo["date"])
    all_games_with_elo = all_games_with_elo.sort_values("date").reset_index(drop=True)

    # Save results
    output_file = f"results/{sport}-elo-ratings.csv"
    os.makedirs("results", exist_ok=True)
    all_games_with_elo.to_csv(output_file, index=False)
    print(f"Results saved to {output_file}")

    # Display final ratings
    print("\nFinal Team Ratings:")
    final_ratings = pd.DataFrame({
        "team": list(teams),
        "elo": [elo_system.team_rating(team) for team in teams],
    }).sort_values("elo", ascending=False)

    # Save final Elo ratings
    elo_output_file = f"results/{sport}-elo-final.csv"
    final_ratings.to_csv(elo_output_file, index=False)
    print(f"Elo ranks saved to {elo_output_file}")
    print(final_ratings.iloc[:30])


def process_game_elo(elo, games_input, sport, verbose=False):
    games = games_input.copy()

    # Sort games by date to process chronologically
    games["date"] = pd.to_datetime(games["date"])
    games = games.sort_values(["season", "date"]).reset_index(drop=True)

    seasons = sorted(games["season"].unique())

    for season in seasons:
        print(f"{season} {sport} season...")
        season_games = games[games["season"] == season]

        for ix, game in season_games.iterrows():
            # All games in our dataset are completed (status == "FINAL")
            home_team = game["home_team"]
            away_team = game["visitor_team"]  # Note: field hockey uses "visitor_team"
            home_score = game["home_score"]
            away_score = game["visitor_score"]  # Note: field hockey uses "visitor_score"

            # Get pre-game ratings
            pre_home = elo.team_rating(home_team)
            pre_away = elo.team_rating(away_team)

            # Calculate predictions before updating
            home_win_prob = elo.home_win_prob(home_team, away_team)
            away_win_prob = 1 - home_win_prob
            pred_point_spread = elo.point_spread(home_team, away_team)

            # Calculate actual point spread (positive means home team won by more than predicted)
            actual_point_spread = home_score - away_score

            if verbose:
                print(f"{game['date'].strftime('%Y-%m-%d')}: "
                      f"{away_team} ({pre_away:.0f}) {away_score:.0f} at "
                      f"{home_team} ({pre_home:.0f}) {home_score:.0f}")

            # Update ratings based on game result
            post_home, post_away = elo.update_ratings(
                home_team, home_score, away_team, away_score
            )

            # Store all the Elo information
            games.at[ix, "home_elo_pre"] = pre_home
            games.at[ix, "away_elo_pre"] = pre_away
            games.at[ix, "home_elo_post"] = post_home
            games.at[ix, "away_elo_post"] = post_away
            games.at[ix, "home_win_prob"] = home_win_prob
            games.at[ix, "away_win_prob"] = away_win_prob
            games.at[ix, "pred_point_spread"] = pred_point_spread
            games.at[ix, "actual_point_spread"] = actual_point_spread

        print(f"End of {season} season")

        # Regress towards mean between seasons (except for the most recent season)
        if season != max(seasons):
            print("Regressing towards the mean between seasons...")
            elo.regress_towards_mean()

    return games

def process_upcoming_games(elo, games_input):
    """Process upcoming games to add current Elo ratings and predictions."""
    games = games_input.copy()

    # Sort games by date
    games["date"] = pd.to_datetime(games["date"])
    games = games.sort_values(["season", "date"]).reset_index(drop=True)

    # Initialize columns with proper float dtype to avoid concatenation warnings
    games["home_elo_pre"] = 0.0
    games["away_elo_pre"] = 0.0
    games["home_elo_post"] = np.nan
    games["away_elo_post"] = np.nan
    games["home_win_prob"] = 0.0
    games["away_win_prob"] = 0.0
    games["pred_point_spread"] = 0.0
    games["actual_point_spread"] = np.nan

    for ix, game in games.iterrows():
        home_team = game["home_team"]
        away_team = game["visitor_team"]

        # Get current ratings (these will be the final ratings after processing completed games)
        current_home = elo.team_rating(home_team)
        current_away = elo.team_rating(away_team)

        # Calculate predictions
        home_win_prob = elo.home_win_prob(home_team, away_team)
        away_win_prob = 1 - home_win_prob
        pred_point_spread = elo.point_spread(home_team, away_team)

        # Store current Elo information (no post-game ratings for upcoming games)
        games.at[ix, "home_elo_pre"] = current_home
        games.at[ix, "away_elo_pre"] = current_away
        games.at[ix, "home_elo_post"] = np.nan  # No post-game rating
        games.at[ix, "away_elo_post"] = np.nan  # No post-game rating
        games.at[ix, "home_win_prob"] = home_win_prob
        games.at[ix, "away_win_prob"] = away_win_prob
        games.at[ix, "pred_point_spread"] = pred_point_spread
        games.at[ix, "actual_point_spread"] = np.nan  # No actual result yet

    return games

def elo_rankings(elo_file):
    elo_games = (pd.read_csv(elo_file, parse_dates=["date"])
                 .query("season == 2025"))
    home_games = (elo_games[[
        "date",
        "game_id",
        "status",
        "season",
        "home_team",
        "home_team_id",
        "home_conference",
        "home_score",
        "home_elo_pre",
        "home_elo_post",
        "visitor_team",
        "visitor_team_id",
        "visitor_conference",
        "visitor_score",
        "away_elo_pre",
        "away_elo_post",
        ]].rename(columns={
            "home_team": "team",
            "home_team_id": "team_id",
            "home_conference": "conference",
            "home_score": "score",
            "home_elo_pre": "elo_pre",
            "home_elo_post": "elo_post", 
            "visitor_team": "opponent",
            "visitor_team_id": "opponent_team_id",
            "visitor_conference": "opponent_conference",
            "visitor_score": "opponent_score",
            "away_elo_pre": "opponent_elo_pre",
            "away_elo_post": "opponent_elo_post",
            }))
    away_games = (elo_games[[
        "date",
        "game_id",
        "status",
        "season",
        "home_team",
        "home_team_id",
        "home_conference",
        "home_score",
        "home_elo_pre",
        "home_elo_post",
        "visitor_team",
        "visitor_team_id",
        "visitor_conference",
        "visitor_score",
        "away_elo_pre",
        "away_elo_post",
        ]].rename(columns={
            "visitor_team": "team",
            "visitor_team_id": "team_id",
            "visitor_conference": "conference",
            "visitor_score": "score",
            "away_elo_pre": "elo_pre",
            "away_elo_post": "elo_post", 
            "home_team": "opponent",
            "home_team_id": "opponent_team_id",
            "home_conference": "opponent_conference",
            "home_score": "opponent_score",
            "home_elo_pre": "opponent_elo_pre",
            "home_elo_post": "opponent_elo_post",
            }))
    games = (pd.concat([home_games, away_games], ignore_index=True)
             .sort_values("date", ascending=True))

if __name__ == "__main__":
    main()
