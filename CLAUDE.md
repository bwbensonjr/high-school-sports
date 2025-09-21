# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project that tracks Massachusetts high school sports scores and calculates Elo ratings for teams. It fetches data from the Boston Globe's high school sports API and processes game results to generate team rankings.

## Architecture

- **Elo rating system**: The main logic is contained in `elo.py` which implements an Elo rating system
- **High school Elo calculator**: `high_school_elo.py` applies the Elo system to high school sports data
- **Data processing pipeline**: `process_games.py` handles fetching and processing game data
- **Data source**: JSON files fetched from Boston Globe API (format: `https://www.bostonglobe.com/partners/data-high-school-sports-services/prd/202526/v2/scoreboard/YYYY-MM-DD.json`)
- **Data storage**:
  - Per-sport CSV files generated (e.g., `data/field-hockey-2025.csv`) containing game results and matchups
  - Elo results saved to `results/` directory (e.g., `results/field-hockey-elo-ratings.csv`)
  - Automatic deduplication based on game_id when updating existing files
- **Dependencies**: Uses pandas for data processing, requests for API calls, and argparse for CLI

## Core Components

- **Elo class** (`elo.py`): Main rating system implementation
  - Configurable K-factor (default: 20), home field advantage (default: 50), and rating mean (default: 1505)
  - Methods for calculating win probabilities, point spreads, and updating ratings based on game results
  - Includes regression functionality to pull ratings toward historical mean

- **Data processor** (`process_games.py`): Game data fetching and processing
  - Command-line interface with argparse for different operation modes
  - Fetches JSON data directly from Boston Globe API
  - Converts nested JSON to per-sport CSV files with proper deduplication
  - Supports single date processing, today's date, date ranges, and built-in testing

- **High school Elo processor** (`high_school_elo.py`): Computes team rankings using Elo ratings
  - Takes sport name as command-line argument (e.g., `python high_school_elo.py field-hockey`)
  - Processes all available data files for the specified sport
  - Handles multi-season data with between-season regression
  - Outputs detailed game results with Elo ratings and team rankings

## Common Commands

- **Install dependencies**: `uv sync` (uses uv package manager)

### Data Processing Commands

- **Process single date**: `python process_games.py --date 2025-09-20`
- **Process today's date**: `python process_games.py --today`
- **Process date range**: `python process_games.py --start 2025-09-20 --end 2025-09-25`
- **Run update tests**: `python process_games.py --test`
- **Show help**: `python process_games.py --help`

### Elo Rating Commands

- **Compute Elo ratings for a sport**: `python high_school_elo.py field-hockey`
- **View available sports**: Check `data/` directory for `{sport}-{year}.csv` files
- **Results location**: Elo calculations are saved to `results/{sport}-elo-ratings.csv`

### Data Processing Behavior

- **Automatic updates**: Running the same date multiple times will update existing CSV files, replacing duplicate games based on game_id
- **Score updates**: Games initially marked as "UPCOMING" will be updated with final scores when processed again
- **New games**: Additional games from later data fetches are automatically added to existing files
- **Error handling**: Network failures and invalid dates are handled gracefully with informative error messages

## Data Format

The API returns nested JSON with date/sport/game structure. Key fields:
- Games have home/visitor teams with scores, IDs, and outcomes
- Teams are identified by ID and name
- Status field indicates if game is "FINAL" or ongoing
- Score multipliers are calculated using logarithmic scaling based on point differential