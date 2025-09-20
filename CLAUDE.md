# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project that tracks Massachusetts high school sports scores and calculates Elo ratings for teams. It fetches data from the Boston Globe's high school sports API and processes game results to generate team rankings.

## Architecture

- **Single module design**: The main logic is contained in `elo.py` which implements an Elo rating system
- **Data source**: JSON files fetched from Boston Globe API (format: `https://www.bostonglobe.com/partners/data-high-school-sports-services/prd/202526/v2/scoreboard/YYYY-MM-DD.json`)
- **Data storage**:
  - Raw JSON data stored in `data/` directory
  - Per-sport CSV files generated (e.g., `data/field-hockey-2025.csv`) containing game results and matchups
- **Dependencies**: Uses pandas for data processing and requests for API calls

## Core Components

- **Elo class** (`elo.py`): Main rating system implementation
  - Configurable K-factor (default: 20), home field advantage (default: 50), and rating mean (default: 1505)
  - Methods for calculating win probabilities, point spreads, and updating ratings based on game results
  - Includes regression functionality to pull ratings toward historical mean

## Common Commands

- **Install dependencies**: `uv sync` (uses uv package manager)
- **Run Python code**: `python elo.py` or `uv run python elo.py`
- **Data fetching**: Use wget to download daily JSON files from the Boston Globe API (see `data/README.md`)

## Data Format

The API returns nested JSON with date/sport/game structure. Key fields:
- Games have home/visitor teams with scores, IDs, and outcomes
- Teams are identified by ID and name
- Status field indicates if game is "FINAL" or ongoing
- Score multipliers are calculated using logarithmic scaling based on point differential