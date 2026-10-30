import pandas as pd

from divisions import load_crosswalk, normalize_name
from miaa_alignment import propose_crosswalk


def test_normalize_name_suffixes():
    assert normalize_name("Doherty") == normalize_name("Doherty Memorial High School")
    assert normalize_name("Millbury") == normalize_name("Millbury Mem.Jr./Sr.H.S.")
    assert normalize_name("Martha’s Vineyard") == normalize_name("Martha's Vineyard Reg. High Sch.")
    assert normalize_name("Mt. Greylock") == normalize_name("Mount Greylock Regional School")
    assert normalize_name("St. Bernard’s") == normalize_name("Saint Bernard's High School")


def test_normalize_name_keeps_distinguishing_words():
    assert normalize_name("Cape Cod Academy") != normalize_name("Cape Cod Regional Tech HS")
    assert normalize_name("Notre Dame Academy (H)") != normalize_name("Notre Dame Academy (W)")


def write_fixture(tmp_path):
    data_dir = tmp_path / "data"
    miaa_dir = data_dir / "miaa"
    miaa_dir.mkdir(parents=True)
    pd.DataFrame([
        {"cycle": "2025-27", "miaa_sport": "Boys Soccer", "season": "fall", "gender": "boys",
         "school": "Doherty Memorial High School", "aligned_school": "Doherty Memorial High School",
         "city": "Worcester", "section": "", "division": "2", "cem_enrollment": "1200", "is_private": "False",
         "appeal": "", "coop_role": "", "host_school": "", "source_url": ""},
        {"cycle": "2025-27", "miaa_sport": "Boys Soccer", "season": "fall", "gender": "boys",
         "school": "Burncoat High School", "aligned_school": "Burncoat High School",
         "city": "Worcester", "section": "", "division": "3", "cem_enrollment": "900", "is_private": "False",
         "appeal": "", "coop_role": "", "host_school": "", "source_url": ""},
    ]).to_csv(miaa_dir / "alignment-2025-27.csv", index=False)
    pd.DataFrame([{"miaa_sport": "Boys Soccer", "season": "fall", "gender": "", "sport_slug": "boys-soccer"}]).to_csv(
        miaa_dir / "sport-map.csv", index=False)
    pd.DataFrame([
        {"date": "2025-09-10", "game_id": 1, "status": "FINAL", "home_team": "Doherty", "home_team_id": 10,
         "home_score": 2, "home_outcome": 1, "visitor_team": "Burncoat", "visitor_team_id": 11, "visitor_score": 1,
         "visitor_outcome": 0, "home_conference": "CMAC", "visitor_conference": "CMAC", "time": "",
         "overtime": "", "is_shootout_win": 0, "tourney_name": "", "tourney_level": ""},
        {"date": "2025-09-12", "game_id": 2, "status": "FINAL", "home_team": "Moses Brown (R.I.)", "home_team_id": 12,
         "home_score": 2, "home_outcome": 1, "visitor_team": "Doherty", "visitor_team_id": 10, "visitor_score": 1,
         "visitor_outcome": 0, "home_conference": "Independent", "visitor_conference": "CMAC", "time": "",
         "overtime": "", "is_shootout_win": 0, "tourney_name": "", "tourney_level": ""},
    ]).to_csv(data_dir / "boys-soccer-2025.csv", index=False)
    return data_dir, miaa_dir


def test_propose_crosswalk_matches_and_preserves_confirmed(tmp_path):
    data_dir, miaa_dir = write_fixture(tmp_path)
    # A confirmed manual decision that disagrees with what matching would propose
    pd.DataFrame([{"team_id": 11, "team_name": "Burncoat", "sport": "", "school": "Doherty Memorial High School",
                   "status": "member", "method": "manual", "confirmed": "True", "note": "reviewed"}]).to_csv(
        miaa_dir / "team-crosswalk.csv", index=False)

    propose_crosswalk(data_dir=str(data_dir), miaa_dir=miaa_dir)
    crosswalk = load_crosswalk(miaa_dir).set_index("team_id")

    assert crosswalk.loc[10, "school"] == "Doherty Memorial High School"
    assert bool(crosswalk.loc[10, "confirmed"])
    assert crosswalk.loc[11, "school"] == "Doherty Memorial High School"
    assert crosswalk.loc[11, "method"] == "manual"
    assert crosswalk.loc[12, "status"] == "non-member"
