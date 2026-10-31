"""Export compact JSON data files for the GitHub Pages site.

Reads results/{sport}-elo-ratings.csv and results/{sport}-elo-final.csv and writes
site/data/index.json plus site/data/sports/{sport}.json. The site's HTML, CSS, and
JavaScript read only these files, so daily data updates never touch UI code.
"""

import argparse
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from divisions import ASSIGNED
from high_school_elo import division_sort_key

EASTERN = ZoneInfo("America/New_York")
WINDOW_DAYS = 14
RATINGS_SUFFIX = "-elo-ratings.csv"
FINAL_SUFFIX = "-elo-final.csv"

# Outcome codes used in game records
WIN, LOSS, TIE = 1, 0, 2


def display_name(slug):
    """Turn a sport slug into a display name, e.g. boys-skiing-(alpine) -> Boys Skiing (Alpine)."""
    words = []
    for word in slug.split("-"):
        if word.startswith("("):
            words.append("(" + word[1:].capitalize())
        else:
            words.append(word.capitalize())
    return " ".join(words)


def is_completed(games):
    """Mask of games with a result: final scores and forfeit rulings."""
    status = games["status"].fillna("")
    return (status == "FINAL") | status.str.startswith("FORFEIT")


def current_season(games):
    return int(games["season"].max())


def clean(value):
    """Convert pandas/numpy scalars to JSON values; NaN and empty strings become None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        value = item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def rounded(value, places):
    value = clean(value)
    return None if value is None else round(float(value), places)


def compact(record):
    """Drop keys whose values are None so files stay small."""
    return {key: value for key, value in record.items() if value is not None}


OPTIONAL_COLUMNS = ["time", "tourney_name", "tourney_level"]


def prepare_games(games):
    games = games.copy()
    for column in OPTIONAL_COLUMNS:
        if column not in games:
            games[column] = None
    games["date"] = pd.to_datetime(games["date"]).dt.date
    return games


def recent_games(games, season):
    """Completed current-season games in the 14 days ending on the latest completed game."""
    completed = games[(games["season"] == season) & is_completed(games)]
    if completed.empty:
        return []
    latest = completed["date"].max()
    window = completed[completed["date"] >= latest - timedelta(days=WINDOW_DAYS - 1)]
    window = window.sort_values(["date", "game_id"], ascending=[False, True])
    return [
        compact({
            "date": row.date.isoformat(),
            "home": row.home_team,
            "hs": clean(row.home_score),
            "visitor": row.visitor_team,
            "vs": clean(row.visitor_score),
            "ho": clean(row.home_outcome),
            "status": None if row.status == "FINAL" else row.status,
            "spread": rounded(row.pred_point_spread, 1),
            "tourney": clean(row.tourney_name),
            "level": clean(row.tourney_level),
        })
        for row in window.itertuples()
    ]


def upcoming_games(games, season, today):
    """Scheduled current-season games on or after today; stale scheduled rows are dropped."""
    upcoming = games[
        (games["season"] == season)
        & (games["status"] == "UPCOMING")
        & (games["date"] >= today)
    ].sort_values(["date", "game_id"])
    return [
        compact({
            "date": row.date.isoformat(),
            "time": clean(row.time),
            "home": row.home_team,
            "visitor": row.visitor_team,
            "homeProb": rounded(row.home_win_prob, 3),
            "spread": rounded(row.pred_point_spread, 1),
            "tourney": clean(row.tourney_name),
            "level": clean(row.tourney_level),
        })
        for row in upcoming.itertuples()
    ]


def season_records(games, season):
    """Win-loss-tie record per team name over completed current-season games."""
    completed = games[(games["season"] == season) & is_completed(games)]
    sides = pd.concat([
        completed[["home_team", "home_outcome"]].set_axis(["team", "outcome"], axis=1),
        completed[["visitor_team", "visitor_outcome"]].set_axis(["team", "outcome"], axis=1),
    ])
    records = {}
    for team, outcomes in sides.groupby("team")["outcome"]:
        counts = outcomes.value_counts()
        records[team] = tuple(int(counts.get(code, 0)) for code in (WIN, LOSS, TIE))
    return records


def team_rankings(games, final, season):
    """Teams with a completed current-season game, re-ranked overall and within division."""
    records = season_records(games, season)
    teams = final[final["team"].isin(records)].sort_values("elo", ascending=False).copy()
    teams["rank"] = range(1, len(teams) + 1)
    assigned = teams["division_status"] == ASSIGNED
    teams["div_rank"] = (
        teams[assigned].groupby("division")["elo"].rank(method="first", ascending=False).astype("Int64")
    )
    rows = []
    for row in teams.itertuples():
        wins, losses, ties = records[row.team]
        rows.append(compact({
            "rank": row.rank,
            "team": row.team,
            "elo": int(round(row.elo)),
            "w": wins,
            "l": losses,
            "t": ties,
            "div": clean(row.division) if row.division_status == ASSIGNED else None,
            "divStatus": clean(row.division_status),
            "divRank": clean(row.div_rank),
        }))
    divisions = sorted(teams.loc[assigned, "division"].dropna().unique(), key=division_sort_key)
    return rows, [str(division) for division in divisions]


def recent_activity(games, today):
    """Completed games in the previous 14 days and whether any game falls in the next 14."""
    window_start = today - timedelta(days=WINDOW_DAYS)
    window_end = today + timedelta(days=WINDOW_DAYS)
    completed = games[is_completed(games)]
    recent_count = int(((completed["date"] >= window_start) & (completed["date"] <= today)).sum())
    scheduled = games[
        (games["status"] == "UPCOMING") & (games["date"] >= today) & (games["date"] <= window_end)
    ]
    return recent_count, recent_count > 0 or not scheduled.empty


def build_sport(slug, games, final, today, generated):
    games = prepare_games(games)
    season = current_season(games)
    teams, divisions = team_rankings(games, final, season)
    return {
        "slug": slug,
        "name": display_name(slug),
        "season": season,
        "generated": generated,
        "hasDivisions": bool(divisions),
        "divisions": divisions,
        "recent": recent_games(games, season),
        "upcoming": upcoming_games(games, season, today),
        "teams": teams,
    }


def index_entry(slug, games, today):
    games = prepare_games(games)
    recent_count, in_season = recent_activity(games, today)
    return {
        "slug": slug,
        "name": display_name(slug),
        "season": current_season(games),
        "inSeason": in_season,
        "recentGames": recent_count,
    }


def order_index(entries):
    """In-season sports by recent games descending, then the rest alphabetically."""
    in_season = sorted(
        (e for e in entries if e["inSeason"]), key=lambda e: (-e["recentGames"], e["name"])
    )
    others = sorted((e for e in entries if not e["inSeason"]), key=lambda e: e["name"])
    return in_season + others


def available_sports(results_dir):
    results_dir = Path(results_dir)
    slugs = []
    for path in sorted(results_dir.glob(f"*{RATINGS_SUFFIX}")):
        slug = path.name[: -len(RATINGS_SUFFIX)]
        if (results_dir / f"{slug}{FINAL_SUFFIX}").exists():
            slugs.append(slug)
    return slugs


def load_results(results_dir, slug):
    results_dir = Path(results_dir)
    games = pd.read_csv(results_dir / f"{slug}{RATINGS_SUFFIX}", low_memory=False)
    final = pd.read_csv(results_dir / f"{slug}{FINAL_SUFFIX}", dtype={"division": str})
    return games, final


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def export_site_data(results_dir, out_dir, today, generated):
    out_dir = Path(out_dir)
    entries = []
    for slug in available_sports(results_dir):
        games, final = load_results(results_dir, slug)
        if games.empty:
            continue
        write_json(out_dir / "sports" / f"{slug}.json", build_sport(slug, games, final, today, generated))
        entries.append(index_entry(slug, games, today))
    index = {"generated": generated, "date": today.isoformat(), "sports": order_index(entries)}
    write_json(out_dir / "index.json", index)
    return index


def main():
    parser = argparse.ArgumentParser(description="Export JSON data files for the GitHub Pages site")
    parser.add_argument("--date", type=date.fromisoformat, help="Export date (YYYY-MM-DD); defaults to today in Eastern time")
    parser.add_argument("--results-dir", default="results", help="Directory with Elo result CSVs")
    parser.add_argument("--out-dir", default="site/data", help="Directory to write JSON files")
    args = parser.parse_args()

    now = datetime.now(EASTERN)
    today = args.date or now.date()
    index = export_site_data(args.results_dir, args.out_dir, today, now.isoformat(timespec="minutes"))
    in_season = [e["name"] for e in index["sports"] if e["inSeason"]]
    print(f"Exported {len(index['sports'])} sports to {args.out_dir} ({len(in_season)} in season: {', '.join(in_season)})")


if __name__ == "__main__":
    main()
