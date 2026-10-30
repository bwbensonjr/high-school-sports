#!/usr/bin/env python3
"""
Ingest MIAA tournament alignment documents into normalized CSV data.

MIAA assigns each member school a tournament division per sport for a
two-year alignment cycle. The cycle page links one PDF per sport; this
script downloads and parses them into data/miaa/alignment-{cycle}.csv,
builds the Globe team to MIAA school crosswalk, and reports coverage.
"""

import argparse
import difflib
import glob
import hashlib
import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from divisions import (
    ASSIGNED,
    CROSSWALK_COLUMNS,
    MIAA_DIR,
    NON_MEMBER,
    DivisionLookup,
    available_cycles,
    division_label,
    load_alignment,
    load_crosswalk,
    load_sport_map,
    normalize_name,
    school_key,
    school_year_start,
)

MIAA_BASE_URL = "https://www.miaa.net"
USER_AGENT = "Mozilla/5.0 (high-school-sports alignment ingest)"

ALIGNMENT_COLUMNS = [
    "cycle",
    "miaa_sport",
    "season",
    "gender",
    "school",
    "aligned_school",
    "city",
    "section",
    "division",
    "cem_enrollment",
    "is_private",
    "appeal",
    "coop_role",
    "host_school",
    "source_url",
]

MANIFEST_COLUMNS = ["cycle", "miaa_sport", "season", "url", "sha256", "rows", "status", "detail"]

# Left-side columns are located by their label on the header line that contains "MailCITY"
LEFT_LABELS = {
    "TEAM": "school",
    "SCHOOL": "school",
    "Aligned": "aligned_school",
    "MailCITY": "city",
    "Sport": "sport",
    "Gender": "gender",
    "Coop": "coop_role",
    "HostSchool": "host_school",
    "HostSchool*": "host_school",
}

VALID_DIVISIONS = {str(n) for n in range(1, 9)}
SECTION_PATTERN = re.compile(r"^[A-Z]{1,3}$")
# Text clipped at a column edge is glued to the next column's first word, e.g. "SchooBridgewater"
CLIPPED_OVERFLOW_PATTERN = re.compile(r"^[A-Z]?[a-z]{2,}(?=[A-Z][a-z])")
FOOTER_PATTERN = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}\b|\bPage \d+\b")
NON_SECTION_FLAGS = {"AA", "CC", "Y"}


class AlignmentParseError(Exception):
    pass


def cycle_school_years(cycle):
    """Return the two school-year start years for a cycle like '2025-27'."""
    match = re.fullmatch(r"(\d{4})-(\d{2})", cycle)
    if not match:
        raise ValueError(f"Cycle must look like 2025-27, got {cycle!r}")
    start = int(match.group(1))
    if int(match.group(2)) != (start + 2) % 100:
        raise ValueError(f"Cycle {cycle!r} must span two school years")
    return start, start + 1


def collect_documents(index_html):
    """
    Find the per-sport alignment documents listed on an MIAA cycle page.

    Each season's documents are a list following a "Fall/Winter/Spring
    Alignments" label. Entries listed under a "(to come)" label without a
    link are not yet published.
    """
    soup = BeautifulSoup(index_html, "html.parser")
    season_label = re.compile(r"\b(Fall|Winter|Spring)\s+Alignments\b", re.I)
    documents = []
    for ul in soup.find_all("ul"):
        label = ul.find_previous(string=season_label)
        if label is None:
            continue
        items = ul.find_all("li", recursive=False)
        links = [li.find("a") for li in items]
        is_alignment_list = any(a and "lignment" in (a.get("title") or "") for a in links)
        # Unpublished sports are listed without links under a "(to come)" label
        intro = ul.find_previous(["p", "h2", "h3", "h4"])
        is_unpublished_list = (
            items
            and all(a is None for a in links)
            and intro is not None
            and "to come" in intro.get_text().lower()
        )
        if not (is_alignment_list or is_unpublished_list):
            continue
        season = season_label.search(str(label)).group(1).lower()
        for li, a in zip(items, links):
            name = li.get_text(" ", strip=True)
            url = None
            if a is not None and a.get("href"):
                href = str(a["href"])
                url = href if href.startswith("http") else MIAA_BASE_URL + href
            documents.append({"miaa_sport": name, "season": season, "url": url})
    return documents


def fetch(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    return response


def group_lines(words, tolerance=3):
    """Group pdfplumber words into text lines by vertical position."""
    lines = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def header_layout(line):
    """Return left column anchors and where the right-hand value region starts."""
    anchors = []
    right_start = None
    for word in line:
        field = LEFT_LABELS.get(word["text"])
        # Documents with both TEAM and SCHOOL columns use SCHOOL for the aligned school
        if field == "school" and any(name == "school" for _, name in anchors):
            field = "aligned_school"
        if field and right_start is None:
            if not anchors or anchors[-1][1] != field:
                anchors.append((word["x0"], field))
        elif anchors and anchors[-1][1] in ("host_school", "gender", "sport", "coop_role") and right_start is None:
            right_start = word["x0"]
    if right_start is None:
        raise AlignmentParseError("Could not locate value columns on header line")
    return anchors, right_start


def flag_columns(header_lines):
    """Locate the Private and Appeal columns from the stacked header words."""
    columns = []
    for line in header_lines:
        for word in line:
            text = word["text"].lower()
            center = (word["x0"] + word["x1"]) / 2
            if text == "private":
                columns.append(("private", center))
            elif text in ("appeal", "align"):
                columns.append(("appeal", center))
    return columns


def parse_right_values(tokens, flags=()):
    """
    Classify enrollment, private, appeal, and final division tokens.

    Tokens are (text, x_center) pairs. A bare "Y" marks either the private
    school bump or an appeal granted this cycle, depending on its column.
    """
    if not tokens:
        raise AlignmentParseError("Row has no division value")
    division = tokens[-1][0]
    section = ""
    rest = tokens[:-1]
    if rest and SECTION_PATTERN.match(rest[-1][0]) and rest[-1][0] not in NON_SECTION_FLAGS:
        section = rest[-1][0]
        rest = rest[:-1]
    if division not in VALID_DIVISIONS:
        raise AlignmentParseError(f"Unrecognized division value {division!r}")
    cem = ""
    is_private = False
    appeal = []
    for token, center in rest:
        if token.isdigit() and not cem and len(token) >= 2:
            cem = token
        elif token == "Y":
            nearest = min(flags, key=lambda f: abs(f[1] - center), default=("private", center))
            if nearest[0] == "private":
                is_private = True
            else:
                appeal.append("CC")
        elif token in ("AA", "CC"):
            appeal.append(token)
        elif token in VALID_DIVISIONS:
            appeal.append(f"to {token}")
        elif token in ("div", "div)"):
            continue
        else:
            raise AlignmentParseError(f"Unrecognized value {token!r}")
    return {
        "section": section,
        "division": division,
        "cem_enrollment": cem,
        "is_private": is_private,
        "appeal": " ".join(appeal),
    }


def parse_alignment_pdf(path):
    """Parse one MIAA alignment PDF into a list of row dicts."""
    import pdfplumber

    rows = []
    layout = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            lines = group_lines(page.extract_words(keep_blank_chars=False))
            for index, line in enumerate(lines):
                texts = [w["text"] for w in line]
                text = " ".join(texts)
                if "MailCITY" in texts:
                    anchors, right_start = header_layout(line)
                    layout = (anchors, right_start, flag_columns(lines[max(0, index - 6):index + 1]))
                    continue
                if "NUMBER OF TEAMS" in text:
                    # End of the alignment table; notes and summaries follow
                    layout = None
                    continue
                if layout is None or FOOTER_PATTERN.search(text):
                    continue
                anchors, right_start, flags = layout
                left = {field: [] for _, field in anchors}
                right = []
                for word in line:
                    if word["x0"] >= right_start - 2:
                        right.append((word["text"], (word["x0"] + word["x1"]) / 2))
                        continue
                    field = None
                    for x0, name in anchors:
                        if x0 <= word["x1"] - 1:
                            field = name
                    if field is not None:
                        text = word["text"]
                        if field != anchors[0][1] and not left[field]:
                            text = CLIPPED_OVERFLOW_PATTERN.sub("", text)
                        left[field].append(text)
                record = {field: " ".join(words) for field, words in left.items()}
                if not record.get("school") or not record.get("sport"):
                    # Titles, footers, totals, and blank lines carry no sport value
                    continue
                values = parse_right_values(right, flags)
                record.update(values)
                rows.append(record)
    if not rows:
        raise AlignmentParseError("No alignment rows found")
    return rows


def normalize_rows(rows, cycle, document):
    records = []
    for row in rows:
        coop = row.get("coop_role", "")
        coop_role, host = "", row.get("host_school", "")
        # Host cells sometimes carry markers like "?? Own Team" or "- Brookline"
        host = host.lstrip("?- ").strip()
        if host.lower() == "own team":
            host = ""
        # Some documents put "Host BOS" in a single Coop cell
        if coop:
            parts = coop.split(" ", 1)
            coop_role = parts[0].lower()
            if len(parts) > 1 and not host:
                host = parts[1].lstrip("?- ").strip()
        records.append({
            "cycle": cycle,
            "miaa_sport": document["miaa_sport"],
            "season": document["season"],
            "gender": row.get("gender", "").lower(),
            "school": row["school"],
            "aligned_school": row.get("aligned_school") or row["school"],
            "city": row.get("city", ""),
            "section": row["section"],
            "division": int(row["division"]),
            "cem_enrollment": row["cem_enrollment"],
            "is_private": row["is_private"],
            "appeal": row["appeal"],
            "coop_role": coop_role if coop_role in ("host", "guest") else "",
            "host_school": host if coop_role in ("host", "guest") else "",
            "source_url": document["url"],
        })
    return records


def ingest(cycle, index_url, refresh=False):
    """Download and parse every alignment document for a cycle."""
    cycle_school_years(cycle)
    pdf_dir = MIAA_DIR / "pdf" / cycle
    pdf_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching cycle page: {index_url}")
    documents = collect_documents(fetch(index_url).text)
    print(f"Found {len(documents)} documents")

    records = []
    manifest = []
    for document in documents:
        entry = {"cycle": cycle, "miaa_sport": document["miaa_sport"], "season": document["season"],
                 "url": document["url"] or "", "sha256": "", "rows": 0, "status": "", "detail": ""}
        manifest.append(entry)
        if document["url"] is None:
            entry["status"] = "missing"
            entry["detail"] = "not yet published"
            print(f"  missing: {document['miaa_sport']} ({document['season']})")
            continue
        pdf_path = pdf_dir / (document["url"].rstrip("/").rsplit("/", 1)[-1] + ".pdf")
        try:
            if refresh or not pdf_path.exists():
                response = fetch(document["url"])
                if "pdf" not in response.headers.get("Content-Type", ""):
                    raise AlignmentParseError(f"Expected a PDF, got {response.headers.get('Content-Type')}")
                pdf_path.write_bytes(response.content)
            entry["sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            rows = normalize_rows(parse_alignment_pdf(pdf_path), cycle, document)
        except (requests.RequestException, AlignmentParseError) as e:
            entry["status"] = "failed"
            entry["detail"] = str(e)
            print(f"  failed: {document['miaa_sport']} ({document['season']}): {e}")
            continue
        entry["status"] = "ok"
        entry["rows"] = len(rows)
        records.extend(rows)
        print(f"  ok: {document['miaa_sport']} ({document['season']}): {len(rows)} rows")

    MIAA_DIR.mkdir(parents=True, exist_ok=True)
    alignment_file = MIAA_DIR / f"alignment-{cycle}.csv"
    pd.DataFrame(records, columns=ALIGNMENT_COLUMNS).to_csv(alignment_file, index=False)
    manifest_file = MIAA_DIR / f"alignment-{cycle}-manifest.csv"
    pd.DataFrame(manifest, columns=MANIFEST_COLUMNS).to_csv(manifest_file, index=False)
    print(f"Wrote {len(records)} rows to {alignment_file}")
    print(f"Wrote manifest to {manifest_file}")
    return manifest


# State abbreviations such as "(R.I.)", "(Conn.)", "(S.C.)"; local disambiguators like "(Hingham)" have no period
OUT_OF_STATE_PATTERN = re.compile(r"\((?:[A-Z][A-Za-z]{0,4}\.(?:[A-Z]\.?)?|Maine|Canada|Ontario|Quebec)\)")
# Independent-school leagues whose members play NEPSAC rather than MIAA tournaments
PREP_CONFERENCES = {"ISL", "EIL", "MBIL", "IGC"}
MIAA_TOURNEY_PATTERN = re.compile(r"^MIAA Division (\d+)$")


def load_globe_teams(data_dir="data"):
    """
    Collect every Globe team from the per-sport game files.

    Returns a DataFrame of team_id, team_name, sports, conference, and a dict of
    tournament evidence {team_id: {(sport, school_year): {division labels}}}
    plus the set of team IDs seen in NEPSAC tournament games.
    """
    names = {}
    sports = {}
    conferences = {}
    evidence = {}
    nepsac = set()
    for path in glob.glob(f"{data_dir}/*-*.csv"):
        match = re.search(r"/([a-z()\-]+)-(\d{4})\.csv$", path)
        if not match:
            continue
        sport = match.group(1)
        games = pd.read_csv(path, dtype={"tourney_name": str})
        for side in ("home", "visitor"):
            for team_id, team_name, conference in zip(
                games[f"{side}_team_id"], games[f"{side}_team"], games[f"{side}_conference"]
            ):
                names.setdefault(team_id, []).append(team_name)
                sports.setdefault(team_id, set()).add(sport)
                conferences.setdefault(team_id, []).append(str(conference))
        if "tourney_name" not in games:
            continue
        for row in games[games["tourney_name"].notna()].itertuples():
            tourney = MIAA_TOURNEY_PATTERN.match(row.tourney_name)
            for team_id in (row.home_team_id, row.visitor_team_id):
                if tourney:
                    team_evidence = evidence.setdefault(team_id, {})
                    team_evidence.setdefault((sport, school_year_start(row.date)), set()).add(tourney.group(1))
                elif row.tourney_name.startswith("NEPSAC"):
                    nepsac.add(team_id)
    teams = []
    for team_id, team_names in names.items():
        # Prefer the plain school name over co-op variants like "Marblehead/Swampscott"
        plain = [n for n in team_names if "/" not in n] or team_names
        team_conferences = conferences[team_id]
        teams.append({
            "team_id": int(team_id),
            "team_name": max(set(plain), key=plain.count),
            "sports": sports[team_id],
            "conference": max(set(team_conferences), key=team_conferences.count),
        })
    return pd.DataFrame(teams), evidence, nepsac


def alignment_schools(alignment, sport_map, cycles):
    """Summarize each aligned school: normalized name, city, and divisions by (cycle, sport)."""
    merged = alignment.merge(sport_map, on=["miaa_sport", "season"], suffixes=("", "_map"))
    schools = {}
    for row in merged.itertuples():
        # Name variants of one school share a key; the first name seen represents it
        school = schools.setdefault(school_key(row.school), {
            "school": row.school,
            "norm": normalize_name(row.school),
            "cities": [],
            "divisions": {},
        })
        school["cities"].append(normalize_name(row.city))
        for year in cycles[row.cycle]:
            school["divisions"][(row.sport_slug, year)] = division_label(row.section, row.division)
    for school in schools.values():
        # Co-op guest rows list the aligned school's city, so use the most common one
        school["city"] = max(set(school["cities"]), key=school["cities"].count)
    return list(schools.values())


def score_candidate(team, school, evidence):
    """Score how likely a Globe team is the given MIAA school (higher is better)."""
    team_norm = normalize_name(team["team_name"])
    score = difflib.SequenceMatcher(None, team_norm, school["norm"]).ratio()
    team_tokens = set(team_norm.split())
    if team_tokens and team_tokens <= set(school["norm"].split()):
        score += 0.25
    if school["city"] and team_norm.startswith(school["city"]):
        score += 0.15
    # Tournament divisions the team actually played in should agree with the school's alignment
    agree = disagree = 0
    for (sport, year), divisions in evidence.get(team["team_id"], {}).items():
        aligned = school["divisions"].get((sport, year))
        if aligned is None:
            continue
        if aligned in divisions:
            agree += 1
        else:
            disagree += 1
    if agree + disagree:
        score += 0.6 * (agree - disagree) / (agree + disagree)
    return score, agree + disagree > 0


def propose_crosswalk(data_dir="data", miaa_dir=MIAA_DIR, min_score=0.45):
    """Add proposed crosswalk rows for Globe teams that have no confirmed mapping."""
    cycles = available_cycles(miaa_dir)
    alignment = load_alignment(miaa_dir)
    if not len(alignment):
        raise SystemExit("No alignment data found; run ingest first")
    schools = alignment_schools(alignment, load_sport_map(miaa_dir), cycles)
    by_norm = {}
    for school in schools:
        by_norm.setdefault(school["norm"], []).append(school)


    teams, evidence, nepsac = load_globe_teams(data_dir)
    existing = load_crosswalk(miaa_dir)
    # Confirmed rows and sport-specific overrides are never regenerated
    keep = existing[existing["confirmed"] | (existing["sport"] != "")]
    mapped = set(keep[keep["sport"] == ""]["team_id"])

    proposals = []
    for team in teams.sort_values("team_name").to_dict("records"):
        if team["team_id"] in mapped:
            continue
        row = {"team_id": team["team_id"], "team_name": team["team_name"], "sport": "",
               "school": "", "status": "member", "method": "auto", "confirmed": False, "note": ""}
        exact = by_norm.get(normalize_name(team["team_name"]), [])
        if OUT_OF_STATE_PATTERN.search(team["team_name"]):
            row.update(status=NON_MEMBER, confirmed=True, note="out-of-state")
        elif len(exact) == 1:
            row.update(school=exact[0]["school"], confirmed=True, note="exact normalized match")
        else:
            scored = sorted(((*score_candidate(team, s, evidence), s["school"]) for s in schools), reverse=True)
            best_score, used_evidence, best_school = scored[0]
            alternates = "; ".join(f"{name} ({score:.2f})" for score, _, name in scored[1:3])
            if team["team_id"] in nepsac and best_score < 0.8:
                row.update(status=NON_MEMBER, method="tourney", confirmed=True, note="NEPSAC tournament team")
            elif team["conference"] in PREP_CONFERENCES or team["conference"].startswith("NEPSAC"):
                row.update(status=NON_MEMBER, confirmed=True, note=f"{team['conference']} independent school")
            elif best_score >= min_score:
                row.update(school=best_school, method="tourney" if used_evidence else "auto",
                           note=f"score {best_score:.2f}; alternates: {alternates}")
            else:
                row.update(status="", note=f"no candidate; best {best_school} ({best_score:.2f})")
        proposals.append(row)

    crosswalk = pd.concat([keep, pd.DataFrame(proposals, columns=CROSSWALK_COLUMNS)], ignore_index=True)
    crosswalk = crosswalk.sort_values(["team_name", "sport"]).reset_index(drop=True)
    path = Path(miaa_dir) / "team-crosswalk.csv"
    crosswalk.to_csv(path, index=False, columns=CROSSWALK_COLUMNS)
    counts = pd.DataFrame(proposals)
    print(f"Kept {len(keep)} confirmed or sport-specific rows")
    if len(counts):
        print(f"Proposed {len(counts)} rows: {int(counts['confirmed'].sum())} auto-confirmed, "
              f"{int((~counts['confirmed'] & (counts['school'] != '')).sum())} need review, "
              f"{int(((counts['school'] == '') & (counts['status'] == '')).sum())} without a candidate")
    print(f"Wrote {path}")
    return crosswalk


def cycle_games(cycle, data_dir="data"):
    """Yield (sport, team_id, team_name, date, tourney_name) for every team appearance in a cycle."""
    years = set(cycle_school_years(cycle))
    for path in sorted(glob.glob(f"{data_dir}/*-*.csv")):
        match = re.search(r"/([a-z()\-]+)-(\d{4})\.csv$", path)
        if not match:
            continue
        games = pd.read_csv(path, dtype={"tourney_name": str})
        if "tourney_name" not in games:
            games["tourney_name"] = None
        for row in games.itertuples():
            if school_year_start(row.date) not in years:
                continue
            tourney = row.tourney_name if isinstance(row.tourney_name, str) else ""
            yield match.group(1), row.home_team_id, row.home_team, row.date, tourney
            yield match.group(1), row.visitor_team_id, row.visitor_team, row.date, tourney


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return lines


def coverage_report(cycle, data_dir="data", miaa_dir=MIAA_DIR):
    """Write data/miaa/coverage-{cycle}.md describing crosswalk coverage and validation."""
    lookup = DivisionLookup(miaa_dir)
    if cycle not in lookup.cycles:
        raise SystemExit(f"No alignment data for cycle {cycle}; run ingest first")
    alignment = load_alignment(miaa_dir)
    alignment = alignment[alignment["cycle"] == cycle]
    sport_map = load_sport_map(miaa_dir)
    crosswalk = load_crosswalk(miaa_dir)

    # Latest Globe name, status, and tournament divisions for each (sport, team)
    teams = {}
    for sport, team_id, team_name, game_date, tourney in cycle_games(cycle, data_dir):
        team = teams.setdefault((sport, int(team_id)), {"name": team_name, "date": game_date, "tourneys": set()})
        if game_date >= team["date"]:
            team.update(name=team_name, date=game_date)
        match = MIAA_TOURNEY_PATTERN.match(tourney)
        if match:
            team["tourneys"].add((match.group(1), school_year_start(game_date)))

    mapped_sports = set(sport_map["sport_slug"])
    coverage_rows = []
    unmatched = []
    disagreements = []
    unaligned_tournament_teams = []
    for sport in sorted({s for s, _ in teams} & mapped_sports):
        counts = {"assigned": 0, "non-member": 0, "member without alignment": 0, "unmatched": 0}
        for (team_sport, team_id), team in sorted(teams.items(), key=lambda kv: kv[1]["name"]):
            if team_sport != sport:
                continue
            division, status = lookup.division_for(sport, team_id, team["date"])
            if status == ASSIGNED:
                counts["assigned"] += 1
            elif status == NON_MEMBER:
                counts["non-member"] += 1
            elif lookup.schools.get((team_id, sport)) or lookup.schools.get((team_id, "")):
                counts["member without alignment"] += 1
            else:
                counts["unmatched"] += 1
                unmatched.append((sport, team["name"], team_id))
            for tourney_division, year in sorted(team["tourneys"]):
                school_year = f"{year}-{(year + 1) % 100:02d}"
                if division is None:
                    unaligned_tournament_teams.append((sport, team["name"], team_id, school_year, status, tourney_division))
                elif division != tourney_division:
                    disagreements.append((sport, team["name"], team_id, school_year, division, tourney_division))
        coverage_rows.append((sport, *counts.values()))

    # Alignment schools with no Globe team mapped to them, per project sport
    mapped_keys = {lookup.school_keys.get(school) for school in crosswalk[crosswalk["confirmed"]]["school"]}
    merged = alignment.merge(sport_map, on=["miaa_sport", "season"])

    def is_mapped(key):
        # Truncated names in the crosswalk also cover the extended variant (see DivisionLookup)
        return any(
            key == mapped
            or (key.startswith(f"{mapped} ") and lookup.school_city.get(key) == lookup.school_city.get(mapped))
            for mapped in mapped_keys if mapped
        )

    orphans = sorted({(row.sport_slug, row.school) for row in merged.itertuples()
                      if not is_mapped(lookup.school_keys.get(row.school))})

    # Globe team names that changed since the crosswalk row was written
    current_names = {}
    for (_, team_id), team in teams.items():
        current_names.setdefault(team_id, set()).add(team["name"])
    drift = [(row.team_id, row.team_name, ", ".join(sorted(current_names[row.team_id])))
             for row in crosswalk.itertuples()
             if row.team_id in current_names and row.team_name not in current_names[row.team_id]
             and not any("/" in n for n in current_names[row.team_id])]

    manifest_path = Path(miaa_dir) / f"alignment-{cycle}-manifest.csv"
    manifest = pd.read_csv(manifest_path, dtype=str, keep_default_na=False) if manifest_path.exists() else None
    project_sports = {re.sub(r"-\d{4}\.csv$", "", Path(p).name) for p in glob.glob(f"{data_dir}/*-[0-9][0-9][0-9][0-9].csv")}
    unmapped_miaa = []
    if manifest is not None:
        ok = manifest[manifest["status"] == "ok"]
        unmapped_miaa = sorted(set(zip(ok["miaa_sport"], ok["season"])) - set(zip(sport_map["miaa_sport"], sport_map["season"])))
    unmapped_project = sorted(project_sports - mapped_sports)

    lines = [f"# MIAA Alignment Coverage {cycle}", "",
             "Generated by `python miaa_alignment.py report --cycle " + cycle + "`.", ""]
    if manifest is not None:
        lines += ["## Alignment documents", ""]
        lines += markdown_table(["MIAA sport", "Season", "Rows", "Status", "Detail"],
                                manifest[["miaa_sport", "season", "rows", "status", "detail"]].itertuples(index=False))
        lines.append("")
    lines += ["## Sport mapping gaps", "",
              "MIAA documents without a project sport: " + (", ".join(f"{s} ({season})" for s, season in unmapped_miaa) or "none"),
              "",
              "Project sports without an MIAA alignment: " + (", ".join(unmapped_project) or "none"), ""]
    lines += ["## Globe team coverage by sport", "",
              "Counts are Globe teams that played the sport during the cycle. "
              "\"Member without alignment\" means the school is mapped but MIAA lists no team for it in that sport.", ""]
    lines += markdown_table(["Sport", "Assigned", "Non-member", "Member without alignment", "Unmatched"], coverage_rows)
    lines += ["", f"## Tournament division disagreements ({len(disagreements)})", ""]
    lines += (markdown_table(["Sport", "Team", "Team ID", "School year", "Alignment", "Tournament"], disagreements)
              if disagreements else ["None."])
    lines += ["", f"## MIAA tournament teams without an alignment division ({len(unaligned_tournament_teams)})", "",
              "These teams played in an MIAA tournament but have no row in the sport's alignment document, "
              "typically new programs, co-ops listed under another school, or a missing crosswalk override.", ""]
    lines += (markdown_table(["Sport", "Team", "Team ID", "School year", "Status", "Tournament"], unaligned_tournament_teams)
              if unaligned_tournament_teams else ["None."])
    lines += ["", f"## Unmatched Globe teams ({len(unmatched)})", ""]
    lines += markdown_table(["Sport", "Team", "Team ID"], unmatched) if unmatched else ["None."]
    lines += ["", f"## Globe name changes ({len(drift)})", ""]
    lines += markdown_table(["Team ID", "Crosswalk name", "Current Globe name"], drift) if drift else ["None."]
    lines += ["", f"## Alignment schools without a Globe team ({len(orphans)})", ""]
    lines += markdown_table(["Sport", "School"], orphans) if orphans else ["None."]

    path = Path(miaa_dir) / f"coverage-{cycle}.md"
    path.write_text("\n".join(lines) + "\n")
    print(f"Disagreements: {len(disagreements)}, tournament teams without alignment: {len(unaligned_tournament_teams)}, "
          f"unmatched teams: {len(unmatched)}, "
          f"unmapped MIAA sports: {len(unmapped_miaa)}, unmapped project sports: {len(unmapped_project)}")
    print(f"Wrote {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest MIAA tournament alignments and map them to Globe teams",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python miaa_alignment.py ingest --cycle 2025-27 --index-url https://www.miaa.net/2025-26-2026-27-tournament-alignment-cycle
  python miaa_alignment.py crosswalk
  python miaa_alignment.py report --cycle 2025-27
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Download and parse alignment documents for a cycle")
    ingest_parser.add_argument("--cycle", required=True, help="Alignment cycle, e.g. 2025-27")
    ingest_parser.add_argument("--index-url", required=True, help="MIAA cycle page listing the alignment documents")
    ingest_parser.add_argument("--refresh", action="store_true", help="Re-download documents even if cached")

    subparsers.add_parser("crosswalk", help="Propose crosswalk rows for Globe teams without a confirmed mapping")

    report_parser = subparsers.add_parser("report", help="Write the coverage and validation report for a cycle")
    report_parser.add_argument("--cycle", required=True, help="Alignment cycle, e.g. 2025-27")

    args = parser.parse_args()
    if args.command == "ingest":
        ingest(args.cycle, args.index_url, refresh=args.refresh)
    elif args.command == "crosswalk":
        propose_crosswalk()
    elif args.command == "report":
        coverage_report(args.cycle)


if __name__ == "__main__":
    main()
