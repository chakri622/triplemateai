"""Flight/airport helper tools backed by the airportsdata dataset.

Provides lookups from IATA codes, city names, and country names to airport
records, plus curated "main airport" resolution for major cities and countries
and a great-circle distance helper. The airportsdata dataset is loaded once at
import time and indexed by IATA code.
"""

import os
import re
from math import asin, cos, radians, sin, sqrt

import airportsdata
import pycountry
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# Loaded once and indexed by IATA code. Entries without an IATA code are dropped.
_AIRPORTS_BY_IATA = airportsdata.load("IATA")

# Aviationstack real-time flight status API. The free plan is HTTP-only.
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
_AVIATIONSTACK_URL = "http://api.aviationstack.com/v1/flights"

# Words that add no signal when matching a location query. Stripped by
# clean_text so "London Heathrow Airport" and "london" both match the city.
_STOP_WORDS = {
    "airport",
    "airports",
    "international",
    "intl",
    "regional",
    "municipal",
    "metropolitan",
    "field",
    "airfield",
    "terminal",
    "the",
    "of",
    "in",
    "near",
    "city",
    "to",
    "from",
    "for",
    "a",
    "an",
}

# Curated primary airport per major city (cleaned city name -> IATA). Resolves
# the ambiguity where a city name maps to several airports of different sizes.
_MAJOR_CITY_AIRPORTS = {
    "new york": "JFK",
    "london": "LHR",
    "paris": "CDG",
    "tokyo": "HND",
    "austin": "AUS",
    "chicago": "ORD",
    "los angeles": "LAX",
    "san francisco": "SFO",
    "washington": "IAD",
    "houston": "IAH",
    "dallas": "DFW",
    "miami": "MIA",
    "boston": "BOS",
    "seattle": "SEA",
    "atlanta": "ATL",
    "denver": "DEN",
    "toronto": "YYZ",
    "mumbai": "BOM",
    "delhi": "DEL",
    "bangalore": "BLR",
    "dubai": "DXB",
    "singapore": "SIN",
    "hong kong": "HKG",
    "sydney": "SYD",
    "melbourne": "MEL",
    "berlin": "BER",
    "munich": "MUC",
    "frankfurt": "FRA",
    "madrid": "MAD",
    "barcelona": "BCN",
    "rome": "FCO",
    "milan": "MXP",
    "amsterdam": "AMS",
    "istanbul": "IST",
    "moscow": "SVO",
    "beijing": "PEK",
    "shanghai": "PVG",
    "seoul": "ICN",
    "bangkok": "BKK",
    "kuala lumpur": "KUL",
    "jakarta": "CGK",
    "mexico city": "MEX",
    "sao paulo": "GRU",
    "rio de janeiro": "GIG",
    "buenos aires": "EZE",
    "cairo": "CAI",
    "johannesburg": "JNB",
    "doha": "DOH",
    "abu dhabi": "AUH",
}

# Curated primary international gateway per country (alpha-2 code -> IATA).
_COUNTRY_MAIN_AIRPORTS = {
    "US": "JFK",
    "GB": "LHR",
    "FR": "CDG",
    "DE": "FRA",
    "JP": "HND",
    "CN": "PEK",
    "IN": "DEL",
    "AU": "SYD",
    "CA": "YYZ",
    "AE": "DXB",
    "SG": "SIN",
    "ES": "MAD",
    "IT": "FCO",
    "NL": "AMS",
    "BR": "GRU",
    "MX": "MEX",
    "RU": "SVO",
    "KR": "ICN",
    "TH": "BKK",
    "ID": "CGK",
    "MY": "KUL",
    "TR": "IST",
    "EG": "CAI",
    "ZA": "JNB",
    "QA": "DOH",
    "AR": "EZE",
}


def clean_text(text: str) -> str:
    """Normalize a location query for matching.

    Lowercases, strips punctuation, removes stop words (e.g. "airport",
    "international"), and collapses whitespace.

    Args:
        text: Raw query string.

    Returns:
        The cleaned, space-separated string (may be empty).
    """
    if not text:
        return ""
    tokens = re.sub(r"[^\w\s]", " ", text.lower()).split()
    kept = [t for t in tokens if t not in _STOP_WORDS]
    return " ".join(kept)


def country_to_code(name: str) -> str | None:
    """Resolve a country name or code to an ISO 3166-1 alpha-2 code.

    Args:
        name: Country name, official name, or alpha-2/alpha-3 code.

    Returns:
        The alpha-2 country code, or None if it cannot be resolved.
    """
    if not name:
        return None
    query = name.strip()
    try:
        return pycountry.countries.lookup(query).alpha_2
    except LookupError:
        pass
    try:
        return pycountry.countries.search_fuzzy(query)[0].alpha_2
    except LookupError:
        return None


def get_airport(iata: str) -> dict | None:
    """Look up a single airport record by its IATA code.

    Args:
        iata: Three-letter IATA code (case-insensitive), e.g. "AUS".

    Returns:
        The airport record dict, or None if the code is unknown.
    """
    if not iata:
        return None
    return _AIRPORTS_BY_IATA.get(iata.strip().upper())


def find_airports_by_city(city: str, country: str | None = None) -> list[dict]:
    """Find airports whose city matches the given name.

    Matching is done on cleaned text, so "London Airport" matches "London".

    Args:
        city: City name to match (case-insensitive).
        country: Optional country name or code to narrow the results.

    Returns:
        A list of matching airport records, possibly empty.
    """
    city_norm = clean_text(city)
    if not city_norm:
        return []

    country_code = country_to_code(country) if country else None

    matches = []
    for airport in _AIRPORTS_BY_IATA.values():
        if clean_text(airport["city"]) != city_norm:
            continue
        if country_code and airport["country"] != country_code:
            continue
        matches.append(airport)
    return matches


def get_airports_by_country(country: str) -> list[dict]:
    """Return all airports located in the given country.

    Args:
        country: Country name or alpha-2/alpha-3 code.

    Returns:
        A list of airport records, possibly empty.
    """
    country_code = country_to_code(country)
    if not country_code:
        return []
    return [a for a in _AIRPORTS_BY_IATA.values() if a["country"] == country_code]


def get_main_airport_for_city(city: str, country: str | None = None) -> dict | None:
    """Return the primary airport record for a city.

    Uses the curated major-city map first, then falls back to the first
    airport found in that city.

    Args:
        city: City name.
        country: Optional country name or code to disambiguate.

    Returns:
        The airport record, or None if nothing matched.
    """
    city_norm = clean_text(city)
    if city_norm in _MAJOR_CITY_AIRPORTS:
        return get_airport(_MAJOR_CITY_AIRPORTS[city_norm])

    matches = find_airports_by_city(city, country=country)
    return matches[0] if matches else None


def get_main_airport_for_country(country: str) -> dict | None:
    """Return the primary international gateway airport for a country.

    Uses the curated country map first, then falls back to the first airport
    found in that country.

    Args:
        country: Country name or alpha-2/alpha-3 code.

    Returns:
        The airport record, or None if nothing matched.
    """
    country_code = country_to_code(country)
    if not country_code:
        return None
    if country_code in _COUNTRY_MAIN_AIRPORTS:
        return get_airport(_COUNTRY_MAIN_AIRPORTS[country_code])

    airports = get_airports_by_country(country_code)
    return airports[0] if airports else None


def resolve_location_to_iata(query: str, country: str | None = None) -> str | None:
    """Resolve a free-text location to a single IATA code.

    Resolution order:
      1. An exact IATA code.
      2. A country name/code -> that country's main airport.
      3. A major-city name -> its curated primary airport.
      4. Any city name -> the first matching airport.

    Args:
        query: An IATA code, city name, or country name.
        country: Optional country name or code to disambiguate a city.

    Returns:
        The resolved IATA code, or None if nothing matched.
    """
    if not query:
        return None

    candidate = query.strip().upper()
    if len(candidate) == 3 and candidate in _AIRPORTS_BY_IATA:
        return candidate

    # A whole-query country match (e.g. "Japan" -> "HND").
    country_code = country_to_code(query.strip())
    if country_code:
        airport = get_main_airport_for_country(country_code)
        if airport:
            return airport["iata"]

    airport = get_main_airport_for_city(query, country=country)
    return airport["iata"] if airport else None


def airport_distance_km(origin_iata: str, destination_iata: str) -> float | None:
    """Great-circle distance in kilometers between two airports.

    Args:
        origin_iata: Origin IATA code.
        destination_iata: Destination IATA code.

    Returns:
        Distance in kilometers rounded to one decimal, or None if either
        airport is unknown.
    """
    origin = get_airport(origin_iata)
    destination = get_airport(destination_iata)
    if not origin or not destination:
        return None

    lat1, lon1 = radians(origin["lat"]), radians(origin["lon"])
    lat2, lon2 = radians(destination["lat"]), radians(destination["lon"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    earth_radius_km = 6371.0
    return round(2 * earth_radius_km * asin(sqrt(a)), 1)


def format_airport(airport: dict) -> str:
    """Format an airport record into a readable one-line string."""
    return (
        f"{airport['iata']} - {airport['name']}, "
        f"{airport['city']}, {airport['subd']}, {airport['country']}"
    )


def _format_flight(flight: dict) -> str:
    """Format a single Aviationstack flight record into a readable line."""
    airline = (flight.get("airline") or {}).get("name") or "Unknown airline"
    number = (flight.get("flight") or {}).get("iata") or "?"
    status = flight.get("flight_status") or "unknown"

    departure = flight.get("departure") or {}
    arrival = flight.get("arrival") or {}
    dep = departure.get("iata") or "???"
    arr = arrival.get("iata") or "???"
    dep_time = departure.get("scheduled") or "n/a"
    arr_time = arrival.get("scheduled") or "n/a"

    return (
        f"{airline} {number} ({status}): "
        f"{dep} {dep_time} -> {arr} {arr_time}"
    )


def search_flights(
    origin: str,
    destination: str,
    airline: str | None = None,
    limit: int = 10,
) -> str:
    """Search real-time flights for a route via the Aviationstack API.

    Resolves origin and destination (IATA code, city, or country) to airports,
    then queries Aviationstack for current flights on that route. Note: this
    returns flight status/schedule data, not prices or bookable fares.

    Args:
        origin: Origin location (IATA code, city, or country).
        destination: Destination location (IATA code, city, or country).
        airline: Optional airline name to filter by.
        limit: Maximum number of flights to return.

    Returns:
        A newline-separated list of flights, or a message describing why no
        results were returned.
    """
    if not AVIATIONSTACK_API_KEY:
        return "AVIATIONSTACK_API_KEY is not set in the environment."

    origin_iata = resolve_location_to_iata(origin)
    dest_iata = resolve_location_to_iata(destination)
    if not origin_iata:
        return f"No airport found for origin '{origin}'."
    if not dest_iata:
        return f"No airport found for destination '{destination}'."

    params = {
        "access_key": AVIATIONSTACK_API_KEY,
        "dep_iata": origin_iata,
        "arr_iata": dest_iata,
        "limit": limit,
    }
    if airline:
        params["airline_name"] = airline

    try:
        response = requests.get(_AVIATIONSTACK_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        return f"Flight search request failed: {exc}"

    if isinstance(payload, dict) and payload.get("error"):
        message = payload["error"].get("message", payload["error"])
        return f"Flight search API error: {message}"

    flights = payload.get("data", []) if isinstance(payload, dict) else []
    if not flights:
        return f"No flights found for {origin_iata} -> {dest_iata}."

    header = f"Flights {origin_iata} -> {dest_iata} ({len(flights)} found):"
    lines = [f"{i}. {_format_flight(f)}" for i, f in enumerate(flights, start=1)]
    return header + "\n" + "\n".join(lines)


@tool
def lookup_airport(query: str, country: str | None = None) -> str:
    """Resolve a place name or IATA code to its main airport.

    Accepts an IATA code (e.g. "AUS"), a city name (e.g. "Austin"), or a
    country name (e.g. "Japan") and returns the primary airport's IATA code
    and details. Use this to turn a user's location into a bookable airport.

    Args:
        query: An IATA code, city name, or country name.
        country: Optional country name or code to disambiguate a city.
    """
    iata = resolve_location_to_iata(query, country=country)
    if not iata:
        return f"No airport found for '{query}'."
    return format_airport(get_airport(iata))


@tool
def flight_distance(origin: str, destination: str) -> str:
    """Return the great-circle distance between two locations' main airports.

    Each argument may be an IATA code, a city name, or a country name.

    Args:
        origin: Origin location (IATA code, city, or country).
        destination: Destination location (IATA code, city, or country).
    """
    origin_iata = resolve_location_to_iata(origin)
    dest_iata = resolve_location_to_iata(destination)
    if not origin_iata:
        return f"No airport found for origin '{origin}'."
    if not dest_iata:
        return f"No airport found for destination '{destination}'."

    distance = airport_distance_km(origin_iata, dest_iata)
    return f"{origin_iata} -> {dest_iata}: {distance} km"


@tool
def find_flights(
    origin: str,
    destination: str,
    airline: str | None = None,
    limit: int = 10,
) -> str:
    """Find real-time flights between two locations.

    Each location may be an IATA code, city name, or country name. Returns
    current flight schedules and statuses for the route (airline, flight
    number, times, status). Does not include ticket prices.

    Args:
        origin: Where the trip starts (IATA code, city, or country).
        destination: Where the trip ends (IATA code, city, or country).
        airline: Optional airline name to filter by.
        limit: Maximum number of flights to return (default 10).
    """
    return search_flights(origin, destination, airline=airline, limit=limit)


if __name__ == "__main__":
    print("clean_text:", clean_text("London Heathrow International Airport"))
    print("country_to_code('United States'):", country_to_code("United States"))
    print("main city (Austin):", format_airport(get_main_airport_for_city("Austin")))
    print("main country (Japan):", format_airport(get_main_airport_for_country("Japan")))
    print("resolve 'Austin':", resolve_location_to_iata("Austin"))
    print("resolve 'India':", resolve_location_to_iata("India"))
    print("resolve 'Heathrow Airport':", resolve_location_to_iata("LHR"))
    print("airports in Qatar:", len(get_airports_by_country("Qatar")))
    print("AUS -> LAX:", airport_distance_km("AUS", "LAX"), "km")
    print("\nsearch_flights (Austin -> Dallas):")
    print(search_flights("Austin", "Dallas", limit=5))
