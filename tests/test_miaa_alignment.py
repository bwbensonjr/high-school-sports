from pathlib import Path

import pytest

from miaa_alignment import (
    AlignmentParseError,
    collect_documents,
    cycle_school_years,
    parse_alignment_pdf,
    parse_right_values,
)

PDF_DIR = Path("data/miaa/pdf/2025-27")

CYCLE_PAGE = """
<html><body>
<p>Final Fall Alignments:</p>
<ul>
  <li><a href="/field-hockey-final" title="Field Hockey Final 2025-26 Alignment">Field Hockey</a></li>
  <li><a href="/volleyball-fall-final" title="Volleyball - Fall Final Alignment">Volleyball</a></li>
</ul>
<p>Final Winter Alignments</p>
<ul>
  <li><a href="/boys-basketball" title="Boys Basketball 2025-26 / 2026-27 Alignment">Boys Basketball</a></li>
</ul>
<p>For Informational Purposes only (to come):</p>
<ul><li>Boys Alpine Ski</li></ul>
<p>Spring Alignment Process / Timeline:</p>
<ul><li>Spring sport proposed alignments released by April 1, 2025</li></ul>
</body></html>
"""


def require_pdf(name):
    path = PDF_DIR / f"{name}.pdf"
    if not path.exists():
        pytest.skip(f"{path} not cached; run miaa_alignment.py ingest first")
    return path


def test_cycle_school_years():
    assert cycle_school_years("2025-27") == (2025, 2026)
    with pytest.raises(ValueError):
        cycle_school_years("2025-26")


def test_collect_documents_seasons_and_missing():
    documents = collect_documents(CYCLE_PAGE)
    by_name = {d["miaa_sport"]: d for d in documents}
    assert by_name["Field Hockey"]["season"] == "fall"
    assert by_name["Field Hockey"]["url"] == "https://www.miaa.net/field-hockey-final"
    assert by_name["Boys Basketball"]["season"] == "winter"
    assert by_name["Boys Alpine Ski"]["url"] is None
    # Prose bullets are not treated as sports
    assert len(documents) == 4


def test_parse_right_values_statewide_division():
    values = parse_right_values([("1188", 400), ("Y", 450), ("1", 520)], [("private", 450), ("appeal", 490)])
    assert values == {"section": "", "division": "1", "cem_enrollment": "1188", "is_private": True, "appeal": ""}


def test_parse_right_values_appeal_flag_by_column():
    values = parse_right_values([("1307", 400), ("Y", 490), ("5", 520)], [("private", 450), ("appeal", 490)])
    assert values["is_private"] is False
    assert values["appeal"] == "CC"


def test_parse_right_values_sectional_division():
    values = parse_right_values([("1819", 400), ("CW", 510), ("1", 520)])
    assert values["section"] == "CW"
    assert values["division"] == "1"


def test_parse_right_values_rejects_unknown_division():
    with pytest.raises(AlignmentParseError):
        parse_right_values([("1819", 400), ("55", 520)])


def test_parse_boys_soccer_pdf():
    rows = parse_alignment_pdf(require_pdf("soccer-boys-final-2025-26-and-2026-27-alignment"))
    assert len(rows) == 338
    assert {r["division"] for r in rows} == {"1", "2", "3", "4", "5"}
    bc_high = next(r for r in rows if r["school"] == "Boston College High School")
    assert bc_high["division"] == "1"
    assert bc_high["is_private"] is True


def test_parse_boys_basketball_pdf_layout():
    rows = parse_alignment_pdf(require_pdf("boys-basketball-2025-26-2026-27-alignment"))
    assert len(rows) == 360
    assert all(r["gender"] == "Boys" for r in rows)


def test_parse_baseball_pdf_without_gender_column():
    rows = parse_alignment_pdf(require_pdf("baseball-alignment-2025-26-and-2026-27"))
    assert len(rows) == 323
    middleboro = next(r for r in rows if r["school"] == "Middleboro High School")
    assert middleboro["division"] == "3"


def test_parse_sectional_swim_pdf():
    rows = parse_alignment_pdf(require_pdf("boys-winter-swim-2025-26-2026-27-alignment"))
    assert {r["section"] for r in rows} == {"CW", "N", "S"}
    assert all(r["school"] and r["city"] for r in rows)
