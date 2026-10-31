from elo import Elo
from divisions import ASSIGNED, DivisionLookup, school_year_start
import pandas as pd
import numpy as np
import glob
import os
import sys

# Sport-specific Elo configuration overrides
# Only specify parameters that differ from Elo class defaults (k=30, home_field=50, spread_factor=25).
# k, home_field, and season_regression set win probabilities and rating updates; spread_factor and spread_home_field
# (Elo points, defaults to home_field) convert ratings to predicted margins. Values come from
# calibrate_elo.py and are kept at their previous values where the fit did not improve a
# chronological holdout.
SPORT_CONFIG = {
    "baseball": {"spread_factor": 57.9, "spread_home_field": 46},
    "boys-basketball": {"spread_factor": 20},
    "boys-cross-country": {"k": 80, "home_field": 0, "spread_factor": 22.4, "spread_home_field": -48},
    "boys-golf": {"k": 40, "home_field": 0, "spread_factor": 14.2, "spread_home_field": -32},
    "boys-hockey": {"k": 100, "home_field": 40, "spread_factor": 120.2, "spread_home_field": 56},
    "boys-lacrosse": {"k": 80, "home_field": 60, "spread_factor": 53.3, "spread_home_field": 92},
    "boys-soccer": {"k": 80, "spread_factor": 121.6, "spread_home_field": 38},
    "boys-tennis": {"k": 150, "spread_factor": 160.1, "spread_home_field": 123},
    "boys-volleyball": {"k": 120, "home_field": 110, "spread_factor": 246.1, "spread_home_field": 206},
    "fall-girls-swimming": {"spread_factor": 10},  # not calibrated: insufficient data
    "field-hockey": {"k": 120, "season_regression": 0.1, "spread_factor": 128.7, "spread_home_field": 43},
    "football": {"k": 60, "home_field": 30, "spread_factor": 17.5, "spread_home_field": 22},
    "girls-basketball": {"k": 60, "home_field": 60, "spread_factor": 24.5, "spread_home_field": 104},
    "girls-cross-country": {"k": 100, "home_field": 10, "spread_factor": 20, "spread_home_field": -18},
    "girls-hockey": {"k": 120, "home_field": 40, "spread_factor": 143.4, "spread_home_field": 38},
    "girls-lacrosse": {"k": 80, "home_field": 90, "spread_factor": 54.3, "spread_home_field": 130},
    "girls-soccer": {"k": 100, "spread_factor": 132.8, "spread_home_field": 51},
    "girls-tennis": {"spread_factor": 66.7, "spread_home_field": 51},
    "girls-volleyball": {"k": 120, "spread_factor": 197.2, "spread_home_field": 46},
    "softball": {"spread_factor": 38.3, "spread_home_field": 55},
    "volleyball": {"spread_factor": 35},  # not calibrated: insufficient data
    "wrestling": {"k": 80, "home_field": 0, "spread_factor": 14.1, "spread_home_field": 17},
}
# Sports not listed use Elo class defaults. Sports with under 300 completed games are not
# calibrated (e.g. indoor track, swimming, gymnastics, rugby).

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

def load_sport_games(sport, data_dir="data"):
    """
    Load all games for a sport, one row per game, labeled by season.

    Data files are named by the calendar year the games were fetched in, so a
    winter season (December through March) is split across two files, and
    games fetched in both windows appear in both. Games are deduplicated by
    game_id, preferring a completed result and then the newer file. Each game
    belongs to the school year (starting August 1) of its date, and each
    school year is labeled with the newest file year it appears in (e.g. the
    2025-26 winter season is 2026), which matches the file year for fall and
    spring sports.

    Returns:
        DataFrame: Games with a season column, or None if no data files exist
    """
    data_files = glob.glob(f"{data_dir}/{sport}-*.csv")
    if not data_files:
        return None
    print(f"Found {len(data_files)} data files: {sorted(os.path.basename(f) for f in data_files)}")

    all_games = []
    for file in data_files:
        df = pd.read_csv(file)
        # Extract year from filename (e.g., "field-hockey-2025.csv" -> 2025)
        df["file_year"] = int(os.path.basename(file).split("-")[-1].replace(".csv", ""))
        all_games.append(df)
    games = pd.concat(all_games, ignore_index=True)

    games["completed"] = (
        (games["status"] == "FINAL") & games["home_score"].notna() & games["visitor_score"].notna()
    )
    games = (
        games.sort_values(by=["completed", "file_year"], kind="mergesort")
        .drop_duplicates(subset="game_id", keep="last")
    )
    school_year = games["date"].map(school_year_start)
    games["season"] = games.groupby(school_year)["file_year"].transform("max")
    return games.drop(columns=["completed", "file_year"]).sort_index().reset_index(drop=True)


def compute_elo_ratings(sport):
    print(f"Processing {sport} Elo ratings...")

    games_df = load_sport_games(sport)
    if games_df is None:
        print(f"No data files found for {sport}")
        return

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

    # Attach MIAA divisions as of each game's own date
    divisions = DivisionLookup()
    add_game_divisions(all_games_with_elo, sport, divisions)

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

    # Divisions are those in effect at the end of the current season's results
    current_season = max(all_games_with_elo["season"].unique())
    reference_date = division_reference_date(all_games_with_elo, current_season)
    final_ratings = add_rating_divisions(final_ratings, games_df, sport, divisions, reference_date)

    # Save final Elo ratings
    elo_output_file = f"results/{sport}-elo-final.csv"
    final_ratings.to_csv(elo_output_file, index=False)
    print(f"Elo ranks saved to {elo_output_file}")
    print(final_ratings.iloc[:30])

    # Generate Markdown report for the current season
    generate_markdown_report(
        sport,
        current_season,
        upcoming_games_with_elo,
        completed_games_with_elo,
        final_ratings,
        has_divisions=divisions.has_alignment(sport, reference_date),
    )


def add_game_divisions(games, sport, divisions):
    """Add home and visitor MIAA division columns resolved for each game's date."""
    for side in ("home", "visitor"):
        games[f"{side}_division"] = [
            divisions.division_for(sport, team_id, game_date)[0]
            for team_id, game_date in zip(games[f"{side}_team_id"], games["date"])
        ]


def division_reference_date(games, season):
    """Date whose alignment cycle applies to current ratings: the season's latest completed game."""
    season_games = games[games["season"] == season]
    completed = season_games[season_games["status"] == "FINAL"]
    return (completed if len(completed) else season_games)["date"].max()


def division_sort_key(label):
    """Order statewide divisions numerically and sectional ones by section, then number."""
    section, _, number = str(label).rpartition(" ")
    return (section, int(number))


def add_rating_divisions(final_ratings, games, sport, divisions, reference_date):
    """Add team ID, overall rank, division, division status, and rank within division."""
    # Map each team name to the ID it carried in its most recent game
    appearances = pd.concat([
        games[["date", "home_team", "home_team_id"]].set_axis(["date", "team", "team_id"], axis=1),
        games[["date", "visitor_team", "visitor_team_id"]].set_axis(["date", "team", "team_id"], axis=1),
    ]).sort_values("date")
    team_ids = appearances.drop_duplicates("team", keep="last").set_index("team")["team_id"]

    ratings = final_ratings.copy()
    ratings["team_id"] = ratings["team"].map(team_ids).astype("Int64")
    ratings["overall_rank"] = range(1, len(ratings) + 1)
    resolved = [divisions.division_for(sport, team_id, reference_date) for team_id in ratings["team_id"]]
    ratings["division"] = [division for division, _ in resolved]
    ratings["division_status"] = [status for _, status in resolved]
    ratings["division_rank"] = (
        ratings[ratings["division_status"] == ASSIGNED]
        .groupby("division")["elo"]
        .rank(method="first", ascending=False)
        .astype("Int64")
    )
    return ratings


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


def generate_markdown_report(sport, season, upcoming_games_df, completed_games_df, final_ratings_df, has_divisions=False):
    """
    Generate a Markdown report with upcoming game predictions, recent results, and current Elo ratings.

    Args:
        sport (str): Sport name
        season (int): Season year
        upcoming_games_df (DataFrame): Upcoming games with Elo predictions
        completed_games_df (DataFrame): Completed games with Elo ratings
        final_ratings_df (DataFrame): Current Elo ratings for all teams, with division columns
        has_divisions (bool): Whether MIAA alignment data covers this sport and season
    """
    # Filter for upcoming games in the current season
    upcoming = upcoming_games_df[
        (upcoming_games_df["season"] == season) &
        (upcoming_games_df["status"] == "UPCOMING")
    ].copy()
    upcoming["date"] = pd.to_datetime(upcoming["date"])

    # Only include games in the future (exclude old games that were never updated)
    today = pd.Timestamp.now().normalize()
    upcoming = upcoming[upcoming["date"] >= today]

    upcoming = upcoming.sort_values("date")

    # Format sport name for display
    sport_display = sport.replace("-", " ").title()

    # Build markdown content
    markdown_lines = []
    markdown_lines.append(f"# {sport_display} - {season} Season")
    markdown_lines.append(f"\nGenerated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Section 1: Upcoming Games with Predictions
    markdown_lines.append("## Upcoming Games\n")

    if len(upcoming) == 0:
        markdown_lines.append("*No upcoming games scheduled*\n")
    else:
        markdown_lines.append("| Date | Time | Home Team | Away Team | Home Win % | Predicted Spread |")
        markdown_lines.append("|------|------|-----------|-----------|------------|------------------|")

        for _, game in upcoming.iterrows():
            date_str = game["date"].strftime("%Y-%m-%d")

            # Format time (handle missing times)
            if pd.notna(game["time"]) and game["time"]:
                time_str = str(game["time"])
            else:
                time_str = "TBD"

            home_team = game["home_team"]
            away_team = game["visitor_team"]
            home_win_pct = game["home_win_prob"] * 100
            pred_spread = game["pred_point_spread"]

            # Format spread with sign
            if pred_spread > 0:
                spread_str = f"+{pred_spread:.1f}"
            else:
                spread_str = f"{pred_spread:.1f}"

            markdown_lines.append(
                f"| {date_str} | {time_str} | {home_team} | {away_team} | "
                f"{home_win_pct:.1f}% | {spread_str} |"
            )

    # Section 2: Recent Games (last 7 days)
    markdown_lines.append("\n## Recent Games\n")

    # Filter for completed games in the current season
    recent_completed = completed_games_df[
        completed_games_df["season"] == season
    ].copy()
    recent_completed["date"] = pd.to_datetime(recent_completed["date"])

    # Get games from the last 7 days
    today = pd.Timestamp.now().normalize()
    week_ago = today - pd.Timedelta(days=7)
    recent_completed = recent_completed[
        (recent_completed["date"] >= week_ago) &
        (recent_completed["date"] <= today)
    ]
    recent_completed = recent_completed.sort_values("date", ascending=False)

    if len(recent_completed) == 0:
        markdown_lines.append("*No games in the last 7 days*\n")
    else:
        markdown_lines.append("| Date | Home Team | Score | Away Team | Score | Predicted Spread | Actual Spread |")
        markdown_lines.append("|------|-----------|-------|-----------|-------|------------------|---------------|")

        for _, game in recent_completed.iterrows():
            date_str = game["date"].strftime("%Y-%m-%d")
            home_team = game["home_team"]
            away_team = game["visitor_team"]
            home_score = int(game["home_score"])
            away_score = int(game["visitor_score"])
            pred_spread = game["pred_point_spread"]
            actual_spread = game["actual_point_spread"]

            # Format predicted spread with sign
            if pred_spread > 0:
                pred_spread_str = f"+{pred_spread:.1f}"
            else:
                pred_spread_str = f"{pred_spread:.1f}"

            # Format actual spread with sign
            if actual_spread > 0:
                actual_spread_str = f"+{actual_spread:.1f}"
            else:
                actual_spread_str = f"{actual_spread:.1f}"

            markdown_lines.append(
                f"| {date_str} | {home_team} | {home_score} | {away_team} | "
                f"{away_score} | {pred_spread_str} | {actual_spread_str} |"
            )

    # Section 3: Current Elo Ratings
    markdown_lines.append("\n## Current Elo Ratings\n")
    markdown_lines.append("| Rank | Team | Elo Rating |")
    markdown_lines.append("|------|------|------------|")

    for rank, (_, row) in enumerate(final_ratings_df.iterrows(), start=1):
        team = row["team"]
        elo = row["elo"]
        markdown_lines.append(f"| {rank} | {team} | {elo:.1f} |")

    # Section 4: Elo Ratings by MIAA Division
    markdown_lines.append("\n## Elo Ratings by Division\n")
    if not has_divisions:
        markdown_lines.append("*MIAA division data is unavailable for this sport and season.*\n")
    else:
        assigned = final_ratings_df[final_ratings_df["division_status"] == ASSIGNED]
        for division in sorted(assigned["division"].unique(), key=division_sort_key):
            markdown_lines.append(f"\n### Division {division}\n")
            markdown_lines.append("| Division Rank | Team | Elo Rating | Overall Rank |")
            markdown_lines.append("|---------------|------|------------|--------------|")
            for _, row in assigned[assigned["division"] == division].sort_values("division_rank").iterrows():
                markdown_lines.append(
                    f"| {row['division_rank']} | {row['team']} | {row['elo']:.1f} | {row['overall_rank']} |"
                )

        others = final_ratings_df[final_ratings_df["division_status"] != ASSIGNED]
        if len(others):
            markdown_lines.append("\n### Other teams\n")
            markdown_lines.append("Non-MIAA opponents and teams without a known division.\n")
            markdown_lines.append("| Team | Elo Rating | Overall Rank | Status |")
            markdown_lines.append("|------|------------|--------------|--------|")
            for _, row in others.iterrows():
                markdown_lines.append(
                    f"| {row['team']} | {row['elo']:.1f} | {row['overall_rank']} | {row['division_status']} |"
                )

    # Write to file
    markdown_content = "\n".join(markdown_lines)
    output_file = f"results/{sport}-{season}.md"
    with open(output_file, "w") as f:
        f.write(markdown_content)

    print(f"Markdown report saved to {output_file}")


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
