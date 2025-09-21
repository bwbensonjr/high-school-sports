from elo import Elo
import pandas as pd
import glob
import os
import sys

def main():
    sport = sys.argv[1]
    compute_elo_ratings(sport)

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
        year = int(os.path.basename(file).split('-')[-1].replace('.csv', ''))
        df['season'] = year
        all_games.append(df)

    games_df = pd.concat(all_games, ignore_index=True)

    # Filter out games that haven't been played yet (no scores)
    completed_games = games_df[games_df['status'] == 'FINAL'].copy()
    print(f"Found {len(completed_games)} completed games")

    # Get all teams
    teams = set(
        list(completed_games["home_team"].unique()) +
        list(completed_games["visitor_team"].unique())
    )
    print(f"Found {len(teams)} teams")

    # Initialize Elo system
    elo_system = Elo(teams=teams)

    # Process games and calculate Elo ratings
    games_with_elo = process_game_elo(elo_system, completed_games, sport)

    # Save results
    output_file = f"results/{sport}-elo-ratings.csv"
    os.makedirs("results", exist_ok=True)
    games_with_elo.to_csv(output_file, index=False)
    print(f"Results saved to {output_file}")

    # Display final ratings
    print("\nFinal Team Ratings:")
    final_ratings = [(team, elo_system.team_rating(team)) for team in teams]
    final_ratings.sort(key=lambda x: x[1], reverse=True)

    for i, (team, rating) in enumerate(final_ratings[:20]):  # Top 20 teams
        print(f"{i+1:2d}. {team:<30} {rating:.0f}")

def process_game_elo(elo, games_input, sport, verbose=False):
    games = games_input.copy()

    # Sort games by date to process chronologically
    games['date'] = pd.to_datetime(games['date'])
    games = games.sort_values(['season', 'date']).reset_index(drop=True)

    seasons = sorted(games['season'].unique())

    for season in seasons:
        print(f"{season} {sport} season...")
        season_games = games[games["season"] == season]

        for ix, game in season_games.iterrows():
            # All games in our dataset are completed (status == 'FINAL')
            home_team = game["home_team"]
            away_team = game["visitor_team"]  # Note: field hockey uses 'visitor_team'
            home_score = game["home_score"]
            away_score = game["visitor_score"]  # Note: field hockey uses 'visitor_score'

            # Get pre-game ratings
            pre_home = elo.team_rating(home_team)
            pre_away = elo.team_rating(away_team)

            # Calculate predictions before updating
            home_win_prob = elo.home_win_prob(home_team, away_team)
            away_win_prob = 1 - home_win_prob
            point_spread = elo.point_spread(home_team, away_team)

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
            games.at[ix, "point_spread"] = point_spread

        print(f"End of {season} season")

        # Regress towards mean between seasons (except for the most recent season)
        if season != max(seasons):
            print("Regressing towards the mean between seasons...")
            elo.regress_towards_mean()

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
