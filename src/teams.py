"""Canonical team-name normalization + WC2026 metadata.

martj42 names are canonical. The only cross-source mismatches with openfootball
are the two aliases below; everything else matches verbatim (verified by diffing
the 2026 team sets). W##/L## are bracket placeholders, not teams.
"""
import re

# openfootball / football-data.org spelling -> martj42 canonical
ALIASES = {
    "USA": "United States",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Türkiye": "Turkey",
    "Czechia": "Czech Republic",
    "Cabo Verde": "Cape Verde",
    "Côte d'Ivoire": "Ivory Coast",
}

_PLACEHOLDER = re.compile(r"^[WL]\d+$")  # W74 = winner of match 74, L101 = loser


def normalize(name):
    # martj42 occasionally ships a row with a blank team cell, which pandas reads
    # as NaN (a float) — guard against any non-string so a single bad upstream row
    # can't crash the whole pipeline.
    if not isinstance(name, str):
        return None
    name = name.strip()
    if not name:
        return None
    return ALIASES.get(name, name)


def is_placeholder(name):
    return bool(name) and bool(_PLACEHOLDER.match(name.strip()))


# Confederation of each 2026 participant — used as a model feature and for display.
CONFEDERATION = {
    # UEFA
    "Austria": "UEFA", "Belgium": "UEFA", "Bosnia and Herzegovina": "UEFA",
    "Croatia": "UEFA", "Czech Republic": "UEFA", "England": "UEFA", "France": "UEFA",
    "Germany": "UEFA", "Italy": "UEFA", "Netherlands": "UEFA", "Norway": "UEFA",
    "Portugal": "UEFA", "Scotland": "UEFA", "Spain": "UEFA", "Sweden": "UEFA",
    "Switzerland": "UEFA", "Turkey": "UEFA",
    # CONMEBOL
    "Argentina": "CONMEBOL", "Brazil": "CONMEBOL", "Colombia": "CONMEBOL",
    "Ecuador": "CONMEBOL", "Paraguay": "CONMEBOL", "Uruguay": "CONMEBOL",
    # CONCACAF
    "Canada": "CONCACAF", "Curaçao": "CONCACAF", "Haiti": "CONCACAF",
    "Mexico": "CONCACAF", "Panama": "CONCACAF", "United States": "CONCACAF",
    # CAF
    "Algeria": "CAF", "Cape Verde": "CAF", "DR Congo": "CAF", "Egypt": "CAF",
    "Ghana": "CAF", "Ivory Coast": "CAF", "Morocco": "CAF", "Senegal": "CAF",
    "South Africa": "CAF", "Tunisia": "CAF",
    # AFC
    "Australia": "AFC", "Iran": "AFC", "Iraq": "AFC", "Japan": "AFC",
    "Jordan": "AFC", "Qatar": "AFC", "Saudi Arabia": "AFC", "South Korea": "AFC",
    "Uzbekistan": "AFC",
    # OFC
    "New Zealand": "OFC",
}


def confederation(team):
    return CONFEDERATION.get(normalize(team), "OTHER")


WC2026_TEAMS = sorted(CONFEDERATION)
# team home-base elevation lives in venues.country_elev (team name == country)

# ISO codes for flag rendering (flagcdn.com/<code>.svg). UK nations use gb-* codes.
TEAM_ISO = {
    "Algeria": "dz", "Argentina": "ar", "Australia": "au", "Austria": "at",
    "Belgium": "be", "Bosnia and Herzegovina": "ba", "Brazil": "br", "Canada": "ca",
    "Cape Verde": "cv", "Colombia": "co", "Croatia": "hr", "Curaçao": "cw",
    "Czech Republic": "cz", "DR Congo": "cd", "Ecuador": "ec", "Egypt": "eg",
    "England": "gb-eng", "France": "fr", "Germany": "de", "Ghana": "gh",
    "Haiti": "ht", "Iran": "ir", "Iraq": "iq", "Ivory Coast": "ci", "Japan": "jp",
    "Jordan": "jo", "Mexico": "mx", "Morocco": "ma", "Netherlands": "nl",
    "New Zealand": "nz", "Norway": "no", "Panama": "pa", "Paraguay": "py",
    "Portugal": "pt", "Qatar": "qa", "Saudi Arabia": "sa", "Scotland": "gb-sct",
    "Senegal": "sn", "South Africa": "za", "South Korea": "kr", "Spain": "es",
    "Sweden": "se", "Switzerland": "ch", "Tunisia": "tn", "Turkey": "tr",
    "United States": "us", "Uruguay": "uy", "Uzbekistan": "uz",
}


def iso(team):
    return TEAM_ISO.get(normalize(team), "un")
