"""
Resolve MIAA tournament divisions for Globe teams.

Alignment data lives in data/miaa/ and is produced by miaa_alignment.py:
- alignment-{cycle}.csv: school, sport, and division for a two-year cycle
- sport-map.csv: MIAA alignment documents to project sport slugs
- team-crosswalk.csv: Globe team IDs to MIAA school names
"""

import glob
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd

MIAA_DIR = Path("data/miaa")

CROSSWALK_COLUMNS = ["team_id", "team_name", "sport", "school", "status", "method", "confirmed", "note"]

ASSIGNED = "assigned"
NON_MEMBER = "non-member"
UNKNOWN = "unknown"

# Words that vary between Globe team names and MIAA school names
NAME_STOPWORDS = {
    "high", "school", "schl", "sch", "hs", "h", "s", "regional", "reg", "senior", "sr", "jr",
    "memorial", "mem", "the", "of", "public", "middle", "mid", "and",
}


def school_year_start(game_date):
    """Return the starting year of the school year containing a date (school years begin August 1)."""
    if isinstance(game_date, str):
        game_date = datetime.strptime(game_date[:10], "%Y-%m-%d").date()
    elif isinstance(game_date, datetime):
        game_date = game_date.date()
    elif hasattr(game_date, "date") and not isinstance(game_date, date):
        game_date = game_date.date()
    return game_date.year if game_date.month >= 8 else game_date.year - 1


def available_cycles(miaa_dir=MIAA_DIR):
    """Map each ingested cycle name to the school-year start years it covers."""
    cycles = {}
    for path in glob.glob(str(Path(miaa_dir) / "alignment-*.csv")):
        match = re.search(r"alignment-(\d{4})-(\d{2})\.csv$", path)
        if match:
            start = int(match.group(1))
            cycles[f"{match.group(1)}-{match.group(2)}"] = (start, start + 1)
    return cycles


def cycle_for_date(game_date, cycles):
    """Return the ingested cycle covering a date, or None."""
    year = school_year_start(game_date)
    for cycle, years in cycles.items():
        if year in years:
            return cycle
    return None


def normalize_name(name):
    """Reduce a school or team name to comparable lowercase tokens."""
    name = str(name).replace("’", "'")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower().replace("&", " and ")
    name = re.sub(r"\bst\.?(?=\s)", "saint", name)
    name = re.sub(r"\bmt\.?(?=\s)", "mount", name)
    name = re.sub(r"[.,'()]", " ", name)
    tokens = [t for t in re.split(r"[\s\-/]+", name) if t and t not in NAME_STOPWORDS]
    return " ".join(tokens)


def school_key(school):
    """
    Identify a school across alignment documents, which abbreviate or truncate
    names differently ("... Charter H" vs "... Charter"). The city column is not
    used because co-op rows list the aligned school's city.
    """
    return normalize_name(school)


def division_label(section, division):
    """Statewide divisions are plain numbers; sectional ones carry the section, e.g. 'N 1'."""
    division = str(int(division))
    return f"{section} {division}" if isinstance(section, str) and section else division


def load_alignment(miaa_dir=MIAA_DIR):
    frames = [pd.read_csv(p, dtype=str, keep_default_na=False)
              for p in sorted(glob.glob(str(Path(miaa_dir) / "alignment-*.csv")))
              if re.search(r"alignment-\d{4}-\d{2}\.csv$", p)]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_sport_map(miaa_dir=MIAA_DIR):
    path = Path(miaa_dir) / "sport-map.csv"
    if not path.exists():
        return pd.DataFrame(columns=["miaa_sport", "season", "gender", "sport_slug"])
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_crosswalk(miaa_dir=MIAA_DIR):
    path = Path(miaa_dir) / "team-crosswalk.csv"
    if not path.exists():
        return pd.DataFrame(columns=CROSSWALK_COLUMNS)
    crosswalk = pd.read_csv(path, dtype=str, keep_default_na=False)
    crosswalk["team_id"] = crosswalk["team_id"].astype(int)
    crosswalk["confirmed"] = crosswalk["confirmed"].str.lower() == "true"
    return crosswalk


class DivisionLookup:
    """Resolve (sport slug, Globe team ID, date) to an MIAA division and status."""

    def __init__(self, miaa_dir=MIAA_DIR):
        self.cycles = available_cycles(miaa_dir)
        alignment = load_alignment(miaa_dir)
        sport_map = load_sport_map(miaa_dir)
        crosswalk = load_crosswalk(miaa_dir)

        # (cycle, sport slug, school key) -> division label, plus each school name variant's key
        self.divisions = {}
        self.school_keys = {}
        cities = {}
        if len(alignment):
            merged = alignment.merge(sport_map, on=["miaa_sport", "season"], suffixes=("", "_map"))
            for row in merged.itertuples():
                if row.gender_map and row.gender and row.gender_map != row.gender:
                    continue
                key = school_key(row.school)
                self.school_keys.setdefault(row.school, key)
                cities.setdefault(key, []).append(row.city)
                self.divisions.setdefault((row.cycle, row.sport_slug, key), division_label(row.section, row.division))
        self.sports_with_alignment = {(cycle, slug) for cycle, slug, _ in self.divisions}
        # Co-op rows list the aligned school's city, so use each school's most common city
        self.school_city = {key: max(set(values), key=values.count) for key, values in cities.items()}
        self.keys_by_sport = {}
        for cycle, slug, key in self.divisions:
            self.keys_by_sport.setdefault((cycle, slug), set()).add(key)

        # Only reviewed crosswalk rows are used; sport-specific rows override the school-wide row
        self.schools = {}
        for row in crosswalk[crosswalk["confirmed"]].itertuples():
            self.schools[(row.team_id, row.sport)] = (row.school, row.status)

    def has_alignment(self, sport, game_date):
        cycle = cycle_for_date(game_date, self.cycles)
        return (cycle, sport) in self.sports_with_alignment

    def division_for(self, sport, team_id, game_date):
        """Return (division label or None, status) for a team in a sport on a date."""
        cycle = cycle_for_date(game_date, self.cycles)
        if cycle is None:
            return None, UNKNOWN
        try:
            team_id = int(team_id)
        except (TypeError, ValueError):
            return None, UNKNOWN
        mapping = self.schools.get((team_id, sport)) or self.schools.get((team_id, ""))
        if mapping is None:
            return None, UNKNOWN
        school, status = mapping
        if status == NON_MEMBER:
            return None, NON_MEMBER
        key = self.school_keys.get(school) or school_key(school)
        division = self.divisions.get((cycle, sport, key))
        if division is None:
            key = self.truncated_variant(cycle, sport, key)
            division = self.divisions.get((cycle, sport, key))
        if division is None:
            return None, UNKNOWN
        return division, ASSIGNED

    def truncated_variant(self, cycle, sport, key):
        """
        Find the one school in a sport whose name extends this truncated one
        ("Advanced Math & Science Acad." vs "... Acad. Charter") in the same
        city. Distinct schools like "Pioneer Charter School of Science" and
        "... II" are told apart by city; the extension must be of the mapped
        name so "Foxborough Regional Charter" never falls back to "Foxborough".
        """
        if key is None:
            return None
        city = self.school_city.get(key)
        candidates = [
            other for other in self.keys_by_sport.get((cycle, sport), ())
            if other.startswith(key + " ") and (city is None or self.school_city.get(other) == city)
        ]
        return candidates[0] if len(candidates) == 1 else None
