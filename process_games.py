import json
import pandas as pd
import os
import requests
import argparse
from datetime import datetime, timedelta
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

    # Determine the school year from the date
    date_obj = datetime.strptime(date_string, '%Y-%m-%d')
    # School year starts in fall, so if month >= 8, it's the start of the school year
    if date_obj.month >= 8:
        school_year = f"{date_obj.year}{str(date_obj.year + 1)[2:]}"
    else:
        school_year = f"{date_obj.year - 1}{str(date_obj.year)[2:]}"

    # Construct URL from README pattern
    url = f"https://www.bostonglobe.com/partners/data-high-school-sports-services/prd/{school_year}/v2/scoreboard/{date_string}.json"

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

def test_game_updates():
    """Test that games are properly updated when processing multiple dates."""
    import tempfile
    import shutil
    from pathlib import Path

    # Create temporary data directory for testing
    original_data_dir = Path('data')
    temp_dir = Path(tempfile.mkdtemp())
    test_data_dir = temp_dir / 'data'
    test_data_dir.mkdir()

    print(f"Running tests in temporary directory: {temp_dir}")

    # Mock data for day 1 - initial games
    day1_data = {
        "date": "2025-09-20",
        "dates": [{
            "date": "2025-09-20",
            "sports": [{
                "id": 54,
                "name": "field hockey",
                "games": [
                    {
                        "id": 12345,
                        "date": "2025-09-20",
                        "status": "UPCOMING",
                        "teams": {
                            "home": {"id": 100, "name": "Team A", "score": "", "outcome": None},
                            "visitor": {"id": 101, "name": "Team B", "score": "", "outcome": None}
                        },
                        "homeConference": "League 1",
                        "visitorConference": "League 1",
                        "time": "4:00 P.M.",
                        "overtime": None,
                        "isShootoutWin": 0
                    },
                    {
                        "id": 12346,
                        "date": "2025-09-20",
                        "status": "FINAL",
                        "teams": {
                            "home": {"id": 102, "name": "Team C", "score": "2", "outcome": 1},
                            "visitor": {"id": 103, "name": "Team D", "score": "1", "outcome": 0}
                        },
                        "homeConference": "League 2",
                        "visitorConference": "League 2",
                        "time": "3:00 P.M.",
                        "overtime": None,
                        "isShootoutWin": 0
                    }
                ]
            }]
        }]
    }

    # Mock data for day 2 - updated games + new games
    day2_data = {
        "date": "2025-09-21",
        "dates": [
            {
                "date": "2025-09-20",  # Previous day with updates
                "sports": [{
                    "id": 54,
                    "name": "field hockey",
                    "games": [
                        {
                            "id": 12345,  # Same ID but now FINAL
                            "date": "2025-09-20",
                            "status": "FINAL",
                            "teams": {
                                "home": {"id": 100, "name": "Team A", "score": "3", "outcome": 1},
                                "visitor": {"id": 101, "name": "Team B", "score": "1", "outcome": 0}
                            },
                            "homeConference": "League 1",
                            "visitorConference": "League 1",
                            "time": "4:00 P.M.",
                            "overtime": None,
                            "isShootoutWin": 0
                        },
                        {
                            "id": 12346,  # Same game, same data
                            "date": "2025-09-20",
                            "status": "FINAL",
                            "teams": {
                                "home": {"id": 102, "name": "Team C", "score": "2", "outcome": 1},
                                "visitor": {"id": 103, "name": "Team D", "score": "1", "outcome": 0}
                            },
                            "homeConference": "League 2",
                            "visitorConference": "League 2",
                            "time": "3:00 P.M.",
                            "overtime": None,
                            "isShootoutWin": 0
                        }
                    ]
                }]
            },
            {
                "date": "2025-09-21",  # New day with new games
                "sports": [{
                    "id": 54,
                    "name": "field hockey",
                    "games": [
                        {
                            "id": 12347,  # New game
                            "date": "2025-09-21",
                            "status": "UPCOMING",
                            "teams": {
                                "home": {"id": 104, "name": "Team E", "score": "", "outcome": None},
                                "visitor": {"id": 105, "name": "Team F", "score": "", "outcome": None}
                            },
                            "homeConference": "League 3",
                            "visitorConference": "League 3",
                            "time": "5:00 P.M.",
                            "overtime": None,
                            "isShootoutWin": 0
                        }
                    ]
                }]
            }
        ]
    }

    try:
        # Change to temporary directory
        os.chdir(temp_dir)

        # Process day 1 data
        print("Processing day 1 data...")
        process_games_json(day1_data)

        # Check initial state
        csv_file = test_data_dir / "field-hockey-2025.csv"
        df1 = pd.read_csv(csv_file)
        print(f"After day 1: {len(df1)} games")

        # Verify initial data
        assert len(df1) == 2, f"Expected 2 games, got {len(df1)}"
        upcoming_games = df1[df1['status'] == 'UPCOMING']
        assert len(upcoming_games) == 1, f"Expected 1 upcoming game, got {len(upcoming_games)}"

        # Process day 2 data (with updates)
        print("Processing day 2 data with updates...")
        process_games_json(day2_data)

        # Check updated state
        df2 = pd.read_csv(csv_file)
        print(f"After day 2: {len(df2)} games")

        # Verify updates
        assert len(df2) == 3, f"Expected 3 games total, got {len(df2)}"

        # Check that game 12345 was updated from UPCOMING to FINAL
        game_12345 = df2[df2['game_id'] == 12345]
        assert len(game_12345) == 1, "Game 12345 should appear exactly once"
        assert game_12345.iloc[0]['status'] == 'FINAL', f"Game 12345 should be FINAL, got {game_12345.iloc[0]['status']}"
        assert str(game_12345.iloc[0]['home_score']) == '3.0', f"Game 12345 home score should be 3.0, got {game_12345.iloc[0]['home_score']}"

        # Check that new game was added
        game_12347 = df2[df2['game_id'] == 12347]
        assert len(game_12347) == 1, "New game 12347 should be present"
        assert game_12347.iloc[0]['date'] == '2025-09-21', "New game should have correct date"

        print("✓ All tests passed!")
        print("✓ Games properly updated when scores/status change")
        print("✓ New games properly added")
        print("✓ No duplicate games in final CSV")

    finally:
        # Clean up - change back to original directory and remove temp
        os.chdir(original_data_dir.parent)
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temporary directory: {temp_dir}")

def process_date_range(start_date, end_date):
    """Process games for a range of dates."""
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')

    processed_dates = []

    while current_date <= end_date_obj:
        date_string = current_date.strftime('%Y-%m-%d')
        print(f"\nProcessing {date_string}...")

        try:
            fetch_and_process_games(date_string)
            processed_dates.append(date_string)
        except Exception as e:
            print(f"Error processing {date_string}: {e}")

        current_date += timedelta(days=1)

    print(f"\nCompleted processing {len(processed_dates)} dates: {processed_dates[0]} to {processed_dates[-1]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process high school sports games from Boston Globe API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python process_games.py --date 2025-09-20
  python process_games.py --today
  python process_games.py --start 2025-09-20 --end 2025-09-25
  python process_games.py --test
        """
    )

    # Create mutually exclusive group for different modes
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--date',
                           help='Process games for a single date (YYYY-MM-DD)')
    mode_group.add_argument('--today',
                           action='store_true',
                           help='Process games for today\'s date')
    mode_group.add_argument('--test',
                           action='store_true',
                           help='Run tests to verify game update functionality')
    mode_group.add_argument('--start',
                           help='Start date for date range processing (YYYY-MM-DD)')

    parser.add_argument('--end',
                       help='End date for date range processing (YYYY-MM-DD). Required if --start is used.')

    args = parser.parse_args()

    # Validate date range arguments
    if args.start and not args.end:
        parser.error("--end is required when --start is specified")
    elif args.end and not args.start:
        parser.error("--start is required when --end is specified")

    # Execute based on mode
    if args.test:
        test_game_updates()
    elif args.date:
        fetch_and_process_games(args.date)
    elif args.today:
        today_date = datetime.now().strftime('%Y-%m-%d')
        print(f"Processing games for today: {today_date}")
        fetch_and_process_games(today_date)
    elif args.start and args.end:
        # Validate date format
        try:
            datetime.strptime(args.start, '%Y-%m-%d')
            datetime.strptime(args.end, '%Y-%m-%d')
        except ValueError:
            parser.error("Dates must be in YYYY-MM-DD format")

        if args.start > args.end:
            parser.error("Start date must be before or equal to end date")

        process_date_range(args.start, args.end)