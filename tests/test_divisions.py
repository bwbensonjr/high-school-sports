import pandas as pd
import pytest

from divisions import (
    ASSIGNED,
    NON_MEMBER,
    UNKNOWN,
    DivisionLookup,
    available_cycles,
    cycle_for_date,
    school_year_start,
)


def alignment_row(sport, season, school, division, city="Boston", section=""):
    return {"cycle": "2025-27", "miaa_sport": sport, "season": season, "gender": "", "school": school,
            "aligned_school": school, "city": city, "section": section, "division": division,
            "cem_enrollment": "", "is_private": "False", "appeal": "", "coop_role": "", "host_school": "",
            "source_url": ""}


@pytest.fixture
def miaa_dir(tmp_path):
    pd.DataFrame([
        alignment_row("Boys Soccer", "fall", "Excel High School", "5"),
        alignment_row("Boys Soccer", "fall", "Advanced Math & Science Acad. Charter", "4", city="Marlborough"),
        alignment_row("Baseball", "spring", "Excel High School", "5"),
        alignment_row("Baseball", "spring", "Ruth Batson Academy", "4"),
        alignment_row("Boys Basketball", "winter", "Ruth Batson Academy", "4"),
        alignment_row("Boys Swimming & Diving", "winter", "Excel High School", "2", section="S"),
    ]).to_csv(tmp_path / "alignment-2025-27.csv", index=False)
    pd.DataFrame([
        {"miaa_sport": "Boys Soccer", "season": "fall", "gender": "", "sport_slug": "boys-soccer"},
        {"miaa_sport": "Baseball", "season": "spring", "gender": "", "sport_slug": "baseball"},
        {"miaa_sport": "Boys Basketball", "season": "winter", "gender": "", "sport_slug": "boys-basketball"},
        {"miaa_sport": "Boys Swimming & Diving", "season": "winter", "gender": "", "sport_slug": "boys-swimming"},
    ]).to_csv(tmp_path / "sport-map.csv", index=False)
    pd.DataFrame([
        {"team_id": 1, "team_name": "South Boston", "sport": "", "school": "Excel High School", "status": "member",
         "method": "manual", "confirmed": "True", "note": ""},
        {"team_id": 2, "team_name": "Batson Academy", "sport": "", "school": "Ruth Batson Academy", "status": "member",
         "method": "manual", "confirmed": "True", "note": ""},
        {"team_id": 2, "team_name": "Batson Academy", "sport": "baseball", "school": "Excel High School",
         "status": "member", "method": "manual", "confirmed": "True", "note": "co-op guest"},
        {"team_id": 3, "team_name": "Moses Brown (R.I.)", "sport": "", "school": "", "status": "non-member",
         "method": "auto", "confirmed": "True", "note": "out-of-state"},
        {"team_id": 4, "team_name": "Unreviewed", "sport": "", "school": "Excel High School", "status": "member",
         "method": "auto", "confirmed": "False", "note": ""},
        {"team_id": 5, "team_name": "Advanced Math and Science", "sport": "", "school": "Advanced Math & Science Acad.",
         "status": "member", "method": "manual", "confirmed": "True", "note": ""},
    ]).to_csv(tmp_path / "team-crosswalk.csv", index=False)
    return tmp_path


def test_school_year_starts_august_first():
    assert school_year_start("2025-07-31") == 2024
    assert school_year_start("2025-08-01") == 2025
    assert school_year_start(pd.Timestamp("2026-01-10")) == 2025


def test_cycle_for_date(miaa_dir):
    cycles = available_cycles(miaa_dir)
    assert cycles == {"2025-27": (2025, 2026)}
    # A winter game stored in a file named for 2025 still belongs to school year 2025-26
    assert cycle_for_date("2026-01-10", cycles) == "2025-27"
    assert cycle_for_date("2027-06-01", cycles) == "2025-27"
    assert cycle_for_date("2024-12-01", cycles) is None


def test_division_for_assigned(miaa_dir):
    lookup = DivisionLookup(miaa_dir)
    assert lookup.division_for("boys-soccer", 1, "2025-10-01") == ("5", ASSIGNED)
    assert lookup.division_for("boys-basketball", 2, "2026-01-10") == ("4", ASSIGNED)


def test_division_for_date_outside_cycles(miaa_dir):
    lookup = DivisionLookup(miaa_dir)
    assert lookup.division_for("boys-soccer", 1, "2024-12-01") == (None, UNKNOWN)


def test_coop_override_uses_host_division(miaa_dir):
    lookup = DivisionLookup(miaa_dir)
    # Batson plays baseball as a guest of Excel, whose division governs the co-op
    assert lookup.division_for("baseball", 2, "2026-04-15") == ("5", ASSIGNED)


def test_non_member_and_unconfirmed(miaa_dir):
    lookup = DivisionLookup(miaa_dir)
    assert lookup.division_for("boys-soccer", 3, "2025-10-01") == (None, NON_MEMBER)
    assert lookup.division_for("boys-soccer", 4, "2025-10-01") == (None, UNKNOWN)
    assert lookup.division_for("boys-soccer", 999, "2025-10-01") == (None, UNKNOWN)


def test_sectional_division_label(miaa_dir):
    lookup = DivisionLookup(miaa_dir)
    assert lookup.division_for("boys-swimming", 1, "2026-01-10") == ("S 2", ASSIGNED)


def test_truncated_school_name_uses_full_variant(miaa_dir):
    lookup = DivisionLookup(miaa_dir)
    assert lookup.division_for("boys-soccer", 5, "2025-10-01") == ("4", ASSIGNED)
