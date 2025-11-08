#!/usr/bin/env python3
"""
Extract team reference data from Boston Globe high school sports standings.

This script fetches standings data for all sports and extracts a structured
CSV with sport, league, conference, team, and team URL information.
"""

import requests
import pandas as pd
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

# List of sports to process (based on common high school sports)
SPORTS = [
    'field-hockey',
    'football',
    'boys-soccer',
    'girls-soccer',
    'girls-volleyball',
    'boys-cross-country',
    'girls-cross-country',
    'boys-golf',
    'girls-golf',
    'boys-basketball',
    'girls-basketball',
    'boys-hockey',
    'girls-hockey',
    'boys-indoor-track',
    'girls-indoor-track',
    'wrestling',
    'coed-swimming',
    'boys-lacrosse',
    'girls-lacrosse',
    'baseball',
    'softball',
    'boys-tennis',
    'girls-tennis',
    'boys-track',
    'girls-track',
]

def get_current_season():
    """Determine the current school year in YYYYYY format."""
    now = datetime.now()
    if now.month >= 8:  # School year starts in August
        return f"{now.year}{str(now.year + 1)[2:]}"
    else:
        return f"{now.year - 1}{str(now.year)[2:]}"

def fetch_standings_for_sport(sport, season):
    """
    Fetch standings data for a given sport.

    Args:
        sport: Sport name (e.g., 'field-hockey')
        season: School year in YYYYYY format (e.g., '202526')

    Returns:
        str: HTML content of the standings page, or None if fetch fails
    """
    url = f"https://www.bostonglobe.com/partners/data-high-school-sports-services/prd/{season}/standings/{sport}.js"

    try:
        print(f"Fetching {sport}...", end=" ")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        print("✓")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"✗ ({str(e)[:50]})")
        return None

def extract_document_write_content(js_content):
    """
    Extract HTML content from document.write() statement in JS file.

    Args:
        js_content: String content of the JS file

    Returns:
        str: HTML content, or empty string if not found
    """
    # Look for document.write('...') pattern
    match = re.search(r"document\.write\(['\"](.+)['\"]\)", js_content, re.DOTALL)
    if match:
        html = match.group(1)
        # Unescape the HTML
        html = html.replace("\\'", "'").replace('\\"', '"')
        html = html.replace("\\n", "\n").replace("\\t", "\t")
        return html
    return ""

def parse_standings_html(html_content, sport):
    """
    Parse HTML content to extract team reference data.

    Args:
        html_content: HTML string containing standings data
        sport: Sport name

    Returns:
        list: List of dictionaries with sport, league, conference, team, and URL data
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    teams_data = []

    # Boston Globe uses tables with td.ds-grouping for leagues and td.ds-subgrouping for conferences
    # Structure:
    #   <tr><td class="ds-grouping">League Name</td></tr>
    #   <tr><td class="ds-subgrouping">Conference/Division Name</td></tr>
    #   <tr class="ds-hdr">...header row...</tr>
    #   <tr>...team rows...</tr>

    tables = soup.find_all('table', class_='ds-std')

    for table in tables:
        current_league = ''
        current_conference = ''

        rows = table.find_all('tr')

        for row in rows:
            # Check if this is a league grouping row
            grouping = row.find('td', class_='ds-grouping')
            if grouping:
                current_league = grouping.get_text(strip=True)
                current_conference = ''  # Reset conference when we hit a new league
                continue

            # Check if this is a conference/division subgrouping row
            subgrouping = row.find('td', class_='ds-subgrouping')
            if subgrouping:
                current_conference = subgrouping.get_text(strip=True)
                continue

            # Check if this is a header row
            if row.find('td', class_='ds-hdr'):
                continue

            # Otherwise, try to extract team data
            name_cell = row.find('td', class_='ds-name')
            if name_cell:
                link = name_cell.find('a')

                if link:
                    team_name = link.get_text(strip=True)
                    team_url = link.get('href', '')

                    # Make URL absolute if it's relative
                    if team_url and not team_url.startswith('http'):
                        team_url = 'https://www.bostonglobe.com' + team_url

                    # Only add if we have a valid team name
                    if team_name and len(team_name) > 1:
                        teams_data.append({
                            'sport': sport,
                            'league': current_league,
                            'conference': current_conference,
                            'team': team_name,
                            'team_url': team_url
                        })

    return teams_data

def extract_teams_from_table(table, sport, league, conference):
    """
    Extract team names and URLs from a standings table.

    Args:
        table: BeautifulSoup table element
        sport: Sport name
        league: League name
        conference: Conference/division name

    Returns:
        list: List of team data dictionaries
    """
    teams = []
    rows = table.find_all('tr')

    for row in rows[1:]:  # Skip header row
        cells = row.find_all(['td', 'th'])
        if len(cells) > 0:
            team_cell = cells[0]

            # Try to get text and URL from link first
            link = team_cell.find('a')
            if link:
                team_name = link.get_text(strip=True)
                team_url = link.get('href', '')

                # Make URL absolute if it's relative
                if team_url and not team_url.startswith('http'):
                    team_url = 'https://www.bostonglobe.com' + team_url
            else:
                team_name = team_cell.get_text(strip=True)
                team_url = ''

            # Filter out empty rows or obvious non-team content
            if team_name and len(team_name) > 1:
                # Skip common header text
                skip_keywords = ['team', 'school', 'record', 'league', 'overall',
                                'home', 'away', 'conf', 'w-l-t', 'w', 'l', 't']
                if not any(team_name.lower() == kw for kw in skip_keywords):
                    teams.append({
                        'sport': sport,
                        'league': league,
                        'conference': conference,
                        'team': team_name,
                        'team_url': team_url
                    })

    return teams

def main():
    """Main function to extract team references from all sports."""
    print("=" * 60)
    print("Extracting Team References from Boston Globe Standings")
    print("=" * 60)
    print()

    season = get_current_season()
    print(f"Season: {season}")
    print(f"Processing {len(SPORTS)} sports...")
    print()

    all_teams_data = []

    for sport in SPORTS:
        # Fetch standings
        js_content = fetch_standings_for_sport(sport, season)

        if js_content:
            # Extract HTML from document.write()
            html_content = extract_document_write_content(js_content)

            # Parse HTML to extract teams
            teams = parse_standings_html(html_content, sport)
            all_teams_data.extend(teams)

            if teams:
                print(f"  → Extracted {len(teams)} teams from {sport}")

    print()
    print("=" * 60)

    if all_teams_data:
        # Create DataFrame
        df = pd.DataFrame(all_teams_data)

        # Sort by sport, league, conference, team
        df = df.sort_values(['sport', 'league', 'conference', 'team'])

        # Remove duplicates (same team might appear in multiple standings)
        # Keep first occurrence to preserve league/conference info
        df = df.drop_duplicates(subset=['sport', 'team'], keep='first')

        # Save to CSV
        data_dir = Path('data')
        data_dir.mkdir(exist_ok=True)
        output_file = data_dir / 'team_references.csv'

        df.to_csv(output_file, index=False)

        print(f"✓ Saved {len(df)} teams to {output_file}")
        print()

        # Print summary statistics
        print("Summary by Sport:")
        print("-" * 60)
        sport_counts = df.groupby('sport').size().sort_values(ascending=False)
        for sport, count in sport_counts.items():
            print(f"  {sport:30s}: {count:4d} teams")

        print()
        print(f"Total unique teams: {len(df)}")
        print(f"Total unique leagues: {df['league'].nunique()}")
        print(f"Teams with URLs: {df['team_url'].notna().sum()} ({df['team_url'].notna().sum()/len(df)*100:.1f}%)")

    else:
        print("⚠ No teams data extracted")

    print("=" * 60)

if __name__ == '__main__':
    main()
