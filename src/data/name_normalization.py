"""Shared display-name normalization helpers for match context labels."""

from __future__ import annotations

import re


UNKNOWN_OPPONENT = "Unknown opponent"
UNKNOWN_GROUND = "Unknown ground"


_OPPONENT_MAPPING_ROWS = [
    ("Balmoral Redbacks CC 1st XI", "Balmoral Redbacks Cricket Club"),
    ("Banyule", "Banyule Cricket Club"),
    ("Barling", "Barling Cricket Club"),
    ("Bell Ramblers", "Bell Ramblers Cricket Club"),
    ("Bellfield", "Bellfield Cricket Club"),
    ("Bellfield 2nd XI", "Bellfield Cricket Club"),
    ("Bellfield CC 1st XI", "Bellfield Cricket Club"),
    ("Bellfield CC OD", "Bellfield Cricket Club"),
    ("Bellfield Bulls CC 1st XI", "Bellfield Bulls Cricket Club"),
    ("Bellfield Bulls CC 2nd XI", "Bellfield Bulls Cricket Club"),
    ("Bellfield Bulls CC 3rd XI", "Bellfield Bulls Cricket Club"),
    ("Bellfield Bulls CC 4th XI", "Bellfield Bulls Cricket Club"),
    ("Bellfield Rocketz CC OD", "Bellfield Rocketz Cricket Club"),
    ("Brunswick", "Brunswick Cricket Club"),
    ("Bundoora Park", "Bundoora Park Cricket Club"),
    ("Bundoora Park 2nd XI", "Bundoora Park Cricket Club"),
    ("Bundoora Park 3rd XI", "Bundoora Park Cricket Club"),
    ("Bundoora Park 4th XI", "Bundoora Park Cricket Club"),
    ("Burnley CYMS", "Burnley CYMS Cricket Club"),
    ("Cameron", "Cameron Cricket Club"),
    ("Cameron 2nd XI", "Cameron Cricket Club"),
    ("Cameron 3rd XI", "Cameron Cricket Club"),
    ("Cameron CC 1st XI", "Cameron Cricket Club"),
    ("Cameron CC 2nd XI", "Cameron Cricket Club"),
    ("Cameron CC OD", "Cameron Cricket Club"),
    ("Camrea", "Camrea Cricket Club"),
    ("Camrea 3rd XI", "Camrea Cricket Club"),
    ("Camrea CC 2nd XI", "Camrea Cricket Club"),
    ("Camrea Cricket Club", "Camrea Cricket Club"),
    ("Camrea CC OD", "Camrea Cricket Club"),
    ("Camrea OD", "Camrea Cricket Club"),
    ("Camrea Stingrays CC 1st XI", "Camrea Stingrays Cricket Club"),
    ("Camrea Stingrays CC 2nd XI", "Camrea Stingrays Cricket Club"),
    ("Chargers", "Chargers Cricket Club"),
    ("Cobras", "Cobras Cricket Club"),
    ("Cobras 3rd XI", "Cobras Cricket Club"),
    ("Cobras 4th XI", "Cobras Cricket Club"),
    ("Cobras 4's", "Cobras Cricket Club"),
    ("Cobras Blue", "Cobras Cricket Club"),
    ("Croxton Park", "Croxton Park Cricket Club"),
    ("Darebin Chargers", "Darebin Chargers Cricket Club"),
    ("Darebin Chargers 3rd XI", "Darebin Chargers Cricket Club"),
    ("Darebin Chargers Red", "Darebin Chargers Cricket Club"),
    ("Darebin Northern Riders", "Darebin Northern Riders Cricket Club"),
    ("Darebin Northern Riders 2nd XI", "Darebin Northern Riders Cricket Club"),
    ("Deccan Chargers", "Deccan Chargers Cricket Club"),
    ("Dennis", "Dennis Cricket Club"),
    ("Dennis 2nd XI", "Dennis Cricket Club"),
    ("Dennis 3rd XI", "Dennis Cricket Club"),
    ("Dennis 4th XI", "Dennis Cricket Club"),
    ("Dennis CC 1st XI", "Dennis Cricket Club"),
    ("Dennis CC 2nd XI", "Dennis Cricket Club"),
    ("Dennis CC OD", "Dennis Cricket Club"),
    ("Dennis OD", "Dennis Cricket Club"),
    ("Donath", "Donath Cricket Club"),
    ("Donath 3rd XI", "Donath Cricket Club"),
    ("Donath CC 1st XI", "Donath Cricket Club"),
    ("Donath CC 2nd XI", "Donath Cricket Club"),
    ("East Brunswick", "East Brunswick Cricket Club"),
    ("East Brunswick 2nd XI", "East Brunswick Cricket Club"),
    ("Fairfield", "Fairfield Cricket Club"),
    ("Fairfield CC 1st XI", "Fairfield Cricket Club"),
    ("Fairfield CC 2nd XI", "Fairfield Cricket Club"),
    ("Fairfield CC 2nd X1", "Fairfield Cricket Club"),
    ("Fairfield CC OD", "Fairfield Cricket Club"),
    ("Fateh Warrior", "Fateh Warrior Cricket Club"),
    ("Heidelberg West", "Heidelberg West Cricket Club"),
    ("Heidelberg West OD", "Heidelberg West Cricket Club"),
    ("Holy Trinity", "Holy Trinity Cricket Club"),
    ("Holy Trinity 2nd XI", "Holy Trinity Cricket Club"),
    ("Holy Trinity 3rd XI", "Holy Trinity Cricket Club"),
    ("Holy Trinity 4th XI", "Holy Trinity Cricket Club"),
    ("Holy Trinity 4's", "Holy Trinity Cricket Club"),
    ("Holy Trinity Blue OD", "Holy Trinity Cricket Club"),
    ("Holy Trinity CC 2nd XI", "Holy Trinity Cricket Club"),
    ("Holy Trinity CC 3rd XI", "Holy Trinity Cricket Club"),
    ("Holy Trinity CC OD", "Holy Trinity Cricket Club"),
    ("Holy Trinity White OD", "Holy Trinity Cricket Club"),
    ("Hume Lions #2", "Hume Lions Cricket Club"),
    ("Hygrade", "Hygrade Cricket Club"),
    ("Hygrade 3rd XI", "Hygrade Cricket Club"),
    ("Indian Tigers", "Indian Tigers Cricket Club"),
    ("Ivanhoe Mavericks", "Ivanhoe Mavericks Cricket Club"),
    ("Ivanhoe Mavericks CC 1st XI", "Ivanhoe Mavericks Cricket Club"),
    ("Ivanhoe Mavericks CC 2nd XI", "Ivanhoe Mavericks Cricket Club"),
    ("Mavericks", "Ivanhoe Mavericks Cricket Club"),
    ("Mavericks #1", "Ivanhoe Mavericks Cricket Club"),
    ("Mavericks Senior Men", "Ivanhoe Mavericks Cricket Club"),
    ("Jacana", "Jacana Cricket Club"),
    ("Jafari SC", "Jafari Sports Club"),
    ("Keon Park", "Keon Park Cricket Club"),
    ("Keon Park 2nd XI", "Keon Park Cricket Club"),
    ("Keon Park 3rd XI", "Keon Park Cricket Club"),
    ("Keon Park 5's", "Keon Park Cricket Club"),
    ("Keon Park CC 2nd XI", "Keon Park Cricket Club"),
    ("Keon Park CC OD", "Keon Park Cricket Club"),
    ("Keon Park Green", "Keon Park Cricket Club"),
    ("Kinglake", "Kinglake Cricket Club"),
    ("Kinglake CC OD", "Kinglake Cricket Club"),
    ("Kingsbury", "Kingsbury Cricket Club"),
    ("LTUCC Eagles", "La Trobe University Cricket Club"),
    ("LTUCC  Eagles", "La Trobe University Cricket Club"),
    ("La Trobe Uni", "La Trobe University Cricket Club"),
    ("La Trobe University", "La Trobe University Cricket Club"),
    ("La Trobe University #3", "La Trobe University Cricket Club"),
    ("Lalor", "Lalor Cricket Club"),
    ("Lalor 2nd XI", "Lalor Cricket Club"),
    ("Lalor Warriors", "Lalor Warriors Cricket Club"),
    ("Lalor Warriors 2nd XI", "Lalor Warriors Cricket Club"),
    ("Lalor Warriors OD", "Lalor Warriors Cricket Club"),
    ("Mayston-Bunborough", "Mayston-Bunborough Cricket Club"),
    ("Mayston-Bunborough 2nd XI", "Mayston-Bunborough Cricket Club"),
    ("Melbourne Lankans", "Melbourne Lankans Cricket Club"),
    ("Melbourne Lankans #1", "Melbourne Lankans Cricket Club"),
    ("Melbourne Rhinos", "Melbourne Rhinos Cricket Club"),
    ("Mernda United", "Mernda United Cricket Club"),
    ("Mill Park", "Mill Park Cricket Club"),
    ("North Alphington Sat Senior Winter Cricket", "North Alphington Cricket Club"),
    ("North Brunswick/Rosebank 3rd XI", "North Brunswick/Rosebank Cricket Club"),
    ("Northcote United", "Northcote United Cricket Club"),
    ("Northcote United 3rd XI", "Northcote United Cricket Club"),
    ("Northcote United 4th XI", "Northcote United Cricket Club"),
    ("Northern Bulls Cricket Club", "Northern Bulls Cricket Club"),
    ("Northern Riders", "Northern Riders Cricket Club"),
    ("Northern Socials", "Northern Socials Cricket Club"),
    ("Northern Socials 2nd XI", "Northern Socials Cricket Club"),
    ("Northern Socials 3rd XI", "Northern Socials Cricket Club"),
    ("Northern Socials CC 1st XI", "Northern Socials Cricket Club"),
    ("Northern Socials CC 2s XI", "Northern Socials Cricket Club"),
    ("Northern Socials CC OD", "Northern Socials Cricket Club"),
    ("Northern Socials OD", "Northern Socials Cricket Club"),
    ("Northern Tigers", "Northern Tigers Cricket Club"),
    ("Oakhill Clelands", "Oakhill Clelands Cricket Club"),
    ("Old Ivanhoe", "Old Ivanhoe Cricket Club"),
    ("Old Ivanhoe 3rd XI", "Old Ivanhoe Cricket Club"),
    ("Old Ivanhoe Grammarians CC 2nd XI", "Old Ivanhoe Grammarians Cricket Club"),
    ("Old Ivanhoe Grammarians CC 3rd XI", "Old Ivanhoe Grammarians Cricket Club"),
    ("Olympic Colts", "Olympic Colts Cricket Club"),
    ("Olympic Colts 2nd XI", "Olympic Colts Cricket Club"),
    ("Olympic Colts CC 1st XI", "Olympic Colts Cricket Club"),
    ("Olympic Colts CC OD", "Olympic Colts Cricket Club"),
    ("Plenty United", "Plenty United Cricket Club"),
    ("Plenty United 2nd XI", "Plenty United Cricket Club"),
    ("Preston Baseballers", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers 2nd XI", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers 3rd XI", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers 3rd  XI", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers 4th XI", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers CC 1st XI", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers CC 2nd XI", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers CC 3rd XI", "Preston Baseballers Cricket Club"),
    ("Preston Baseballers CC OD", "Preston Baseballers Cricket Club"),
    ("Preston Druids", "Preston Druids Cricket Club"),
    ("Preston Druids 3rd XI", "Preston Druids Cricket Club"),
    ("Preston Druids 5th XI", "Preston Druids Cricket Club"),
    ("Preston Footballers", "Preston Footballers Cricket Club"),
    ("Preston Footballers 2nd XI", "Preston Footballers Cricket Club"),
    ("Preston Footballers 3rd XI", "Preston Footballers Cricket Club"),
    ("Preston Footballers 3's", "Preston Footballers Cricket Club"),
    ("Preston Himalayan", "Preston Himalayan Cricket Club"),
    ("Preston YCW District", "Preston YCW District Cricket Club"),
    ("Preston YCW District 2nd XI", "Preston YCW District Cricket Club"),
    ("Preston YCW District 3rd XI", "Preston YCW District Cricket Club"),
    ("Preston YCW District CC 1st XI", "Preston YCW District Cricket Club"),
    ("Preston YCW District CC OD", "Preston YCW District Cricket Club"),
    ("Reservoir Cobras", "Reservoir Cobras Cricket Club"),
    ("Reservoir Cobras 3rd XI", "Reservoir Cobras Cricket Club"),
    ("Reservoir Cobras CC 1st XI", "Reservoir Cobras Cricket Club"),
    ("Reservoir Cobras CC 2nd XI", "Reservoir Cobras Cricket Club"),
    ("Reservoir Mayston", "Reservoir Mayston Cricket Club"),
    ("Reservoir Mayston 2nd XI", "Reservoir Mayston Cricket Club"),
    ("Reservoir Mayston 3's", "Reservoir Mayston Cricket Club"),
    ("Rivergum", "Rivergum Cricket Club"),
    ("Rivergum 2nd XI", "Rivergum Cricket Club"),
    ("Rivergum 3rd XI", "Rivergum Cricket Club"),
    ("Rivergum 4th XI", "Rivergum Cricket Club"),
    ("Rivergum 4's", "Rivergum Cricket Club"),
    ("Rivergum CC 3rd XI", "Rivergum Cricket Club"),
    ("Rosebank", "Rosebank Cricket Club"),
    ("Rosebank 3rd XI", "Rosebank Cricket Club"),
    ("Royal Park Reds 4th XI", "Royal Park Reds Cricket Club"),
    ("Royal Park Reds CC 1st XI", "Royal Park Reds Cricket Club"),
    ("Royal Park Reds CC OD", "Royal Park Reds Cricket Club"),
    ("Sagarmatha", "Sagarmatha Cricket Club"),
    ("Strathewen", "Strathewen Cricket Club"),
    ("Strathewen 4's", "Strathewen Cricket Club"),
    ("Strathewen CC 1st XI", "Strathewen Cricket Club"),
    ("Strathewen Cougars CC 1st XI", "Strathewen Cougars Cricket Club"),
    ("Strathewen Cougars CC 1stXI", "Strathewen Cougars Cricket Club"),
    ("Taipans", "Taipans Cricket Club"),
    ("Thomastown", "Thomastown Cricket Club"),
    ("Thomastown United", "Thomastown United Cricket Club"),
    ("Unknown opponent", UNKNOWN_OPPONENT),
    ("Viewbank", "Viewbank Cricket Club"),
    ("West Ivanhoe United", "West Ivanhoe United Cricket Club"),
    ("West Lalor", "West Lalor Cricket Club"),
    ("West Lalor 2nd XI", "West Lalor Cricket Club"),
    ("West Preston", "West Preston Cricket Club"),
    ("West Preston 2nd XI", "West Preston Cricket Club"),
    ("West Preston 3rd XI", "West Preston Cricket Club"),
    ("West Preston CC 1st XI", "West Preston Cricket Club"),
    ("West Preston CC 3rd XI", "West Preston Cricket Club"),
    ("West Preston Sharks 2nd XI", "West Preston Sharks Cricket Club"),
    ("Wollert Rhinos CC 1st XI", "Wollert Rhinos Cricket Club"),
    ("Wollert Warriors Senior Men A", "Wollert Warriors Cricket Club"),
]

MANUAL_OPPONENT_CLUB_MAPPINGS = {
    re.sub(r"\s+", " ", raw).strip().casefold(): canonical for raw, canonical in _OPPONENT_MAPPING_ROWS
}


def normalize_opponent_club_name(value: object, fallback: str = UNKNOWN_OPPONENT) -> str:
    """Return a club-level opponent display name without team suffix noise."""

    text = _clean_text(value, fallback="")
    if not text:
        return fallback

    mapped = _manual_opponent_mapping(text)
    if mapped:
        return mapped

    normalized = _remove_team_suffixes(text)
    mapped = _manual_opponent_mapping(normalized)
    if mapped:
        return mapped

    normalized = _expand_cricket_club_abbreviation(normalized)
    normalized = _dedupe_cricket_club(normalized)
    normalized = _remove_team_suffixes(normalized)
    normalized = _dedupe_cricket_club(normalized)
    normalized = _collapse_spaces(normalized).strip(" -")
    if not normalized:
        return fallback
    mapped = _manual_opponent_mapping(normalized)
    if mapped:
        return mapped
    if normalized.casefold() in {"unknown", "unknown opponent", "nan", "none"}:
        return fallback
    if not re.search(r"\b(Cricket Club|Sports Club)\b", normalized, flags=re.IGNORECASE):
        normalized = f"{normalized} Cricket Club"
    return _dedupe_cricket_club(normalized)


def normalize_ground_name(value: object, fallback: str = UNKNOWN_GROUND) -> str:
    text = _clean_text(value, fallback="")
    return _collapse_spaces(text).strip() or fallback


def _manual_opponent_mapping(value: str) -> str | None:
    return MANUAL_OPPONENT_CLUB_MAPPINGS.get(_collapse_spaces(value).casefold())


def _clean_text(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "nat"}:
        return fallback
    return _collapse_spaces(text)


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _remove_team_suffixes(value: str) -> str:
    text = _collapse_spaces(value).strip(" -")
    suffix_patterns = [
        r"\s+(?:[1-5](?:st|nd|rd|th)?\s*)?X[I1]$",
        r"\s+[1-5]s\s*X[I1]$",
        r"\s+[1-5]'s$",
        r"\s+Senior Men(?:\s+A)?$",
        r"\s+(?:Blue|White|Green|Red)\s+OD$",
        r"\s+(?:OD|T20)$",
        r"\s+(?:Blue|White|Green|Red)$",
        r"\s+#\d+$",
    ]
    changed = True
    while changed:
        changed = False
        for pattern in suffix_patterns:
            updated = re.sub(pattern, "", text, flags=re.IGNORECASE).strip(" -")
            if updated != text:
                text = _collapse_spaces(updated)
                changed = True
    text = re.sub(
        r"\bCricket Club\s+(?:[1-5]s|[1-5]'s|[1-5](?:st|nd|rd|th)?\s*X[I1]|OD|T20|Blue OD|White OD|Green|Red|#\d+)\s+Cricket Club\b",
        "Cricket Club",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bCricket Club\s+(?:[1-5]s|[1-5]'s|[1-5](?:st|nd|rd|th)?\s*X[I1]|OD|T20|Blue OD|White OD|Green|Red|#\d+)$",
        "Cricket Club",
        text,
        flags=re.IGNORECASE,
    )
    return _collapse_spaces(text).strip(" -")


def _expand_cricket_club_abbreviation(value: str) -> str:
    return re.sub(r"\bCC\b", "Cricket Club", value, flags=re.IGNORECASE)


def _dedupe_cricket_club(value: str) -> str:
    text = _collapse_spaces(value)
    text = re.sub(r"\bCricket Club\s+Cricket Club\b", "Cricket Club", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\bCricket Club\s+(?:[1-5]s|[1-5]'s|[1-5](?:st|nd|rd|th)?\s*X[I1]|OD|T20|Blue OD|White OD|Green|Red|#\d+)\s+Cricket Club\b",
        "Cricket Club",
        text,
        flags=re.IGNORECASE,
    )
    return _collapse_spaces(text)
