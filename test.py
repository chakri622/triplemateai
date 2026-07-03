from tools.flight_tool import (
    airport_distance_km,
    clean_text,
    country_to_code,
    find_flights,
    flight_distance,
    get_airports_by_country,
    get_main_airport_for_city,
    get_main_airport_for_country,
    lookup_airport,
    resolve_location_to_iata,
)
from tools.tavily_tool import tavily_search, web_search


def test_tavily():
    print("=== Tavily search ===")
    print(tavily_search("best hotels in Austin", max_results=3))


def test_flight_helpers():
    print("\n=== Flight helpers ===")
    print("clean_text:", clean_text("London Heathrow International Airport"))
    print("country_to_code('United Kingdom'):", country_to_code("United Kingdom"))
    print("main city (Austin):", get_main_airport_for_city("Austin")["iata"])
    print("main country (Japan):", get_main_airport_for_country("Japan")["iata"])
    print("resolve 'Austin':", resolve_location_to_iata("Austin"))
    print("resolve 'India':", resolve_location_to_iata("India"))
    print("airports in Qatar:", len(get_airports_by_country("Qatar")))
    print("AUS -> LAX:", airport_distance_km("AUS", "LAX"), "km")


def test_langchain_tools():
    print("\n=== LangChain tools ===")
    print("lookup_airport:", lookup_airport.invoke({"query": "Austin"}))
    print(
        "flight_distance:",
        flight_distance.invoke({"origin": "Austin", "destination": "Tokyo"}),
    )
    print(
        "find_flights:",
        find_flights.invoke({"origin": "Austin", "destination": "Dallas", "limit": 3}),
    )
    print("web_search:", web_search.invoke({"query": "best hotels in Austin", "max_results": 2}))


if __name__ == "__main__":
    test_flight_helpers()
    test_langchain_tools()
    test_tavily()
