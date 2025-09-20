import json
import pandas as pd
import os
import requests
from pathlib import Path

def process_games_json(data):
    """Convert JSON data to per-sport CSV files."""

    # Create data directory if it doesn't exist
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)

    # Dictionary to collect games by sport
    sports_games = {}

    # Process each date
    for date_entry in data['dates']:
        date = date_entry['date']

        # Process each sport for this date
        for sport in date_entry['sports']:
            sport_name = sport['name'].replace(chr(8217), "").replace("'", "").replace("'", "").replace(" ", "-")

            if sport_name not in sports_games:
                sports_games[sport_name] = []

            # Process each game for this sport
            for game in sport['games']:
                home_team = game['teams']['home']
                visitor_team = game['teams']['visitor']

                game_record = {
                    'date': game['date'],
                    'game_id': game['id'],
                    'status': game['status'],
                    'home_team': home_team['name'],
                    'home_team_id': home_team['id'],
                    'home_score': home_team['score'] if home_team['score'] else '',
                    'home_outcome': home_team['outcome'],
                    'visitor_team': visitor_team['name'],
                    'visitor_team_id': visitor_team['id'],
                    'visitor_score': visitor_team['score'] if visitor_team['score'] else '',
                    'visitor_outcome': visitor_team['outcome'],
                    'home_conference': game.get('homeConference', ''),
                    'visitor_conference': game.get('visitorConference', ''),
                    'time': game.get('time', ''),
                    'overtime': game.get('overtime'),
                    'is_shootout_win': game.get('isShootoutWin', 0)
                }

                sports_games[sport_name].append(game_record)

    # Write CSV files for each sport
    year = data['date'][:4]  # Extract year from main date

    for sport_name, games in sports_games.items():
        if games:  # Only create file if there are games
            df = pd.DataFrame(games)

            # Sort by date and game_id for consistency
            df = df.sort_values(['date', 'game_id'])

            csv_filename = data_dir / f"{sport_name}-{year}.csv"

            # If file exists, append and remove duplicates, otherwise create new
            if csv_filename.exists():
                existing_df = pd.read_csv(csv_filename)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                # Remove duplicates based on game_id
                combined_df = combined_df.drop_duplicates(subset=['game_id'], keep='last')
                combined_df = combined_df.sort_values(['date', 'game_id'])
                combined_df.to_csv(csv_filename, index=False)
                print(f"Updated {csv_filename} with {len(df)} games (total: {len(combined_df)})")
            else:
                df.to_csv(csv_filename, index=False)
                print(f"Created {csv_filename} with {len(df)} games")

def fetch_and_process_games(date_string):
    """Fetch JSON data from Boston Globe API and process games."""

    # Construct URL from README pattern
    url = f"https://www.bostonglobe.com/partners/data-high-school-sports-services/prd/202526/v2/scoreboard/{date_string}.json"

    print(f"Fetching data from: {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Process the JSON data
        process_games_json(data)

        print(f"Successfully processed games for {date_string}")

    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python process_games.py <date_string>")
        print("Example: python process_games.py 2025-09-20")
        sys.exit(1)

    date_string = sys.argv[1]
    fetch_and_process_games(date_string)