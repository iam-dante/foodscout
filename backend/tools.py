"""
LangChain tools wrapping food.py functions
"""

from langchain_core.tools import tool

from food import (
    search_restaurants,
    get_food_events,
    get_city_food_culture,
    get_trending_dishes,
    reverse_geocode,
    get_local_dishes,
)


@tool
def search_restaurants_tool(lat: float, lon: float, cuisine: str = "", limit: int = 15) -> str:
    """
    Search for restaurants, cafes, and bars near given coordinates.
    Use this when the user asks about restaurants, places to eat, or food spots in a location.
    lat: latitude, lon: longitude, cuisine: optional filter (e.g. Japanese, Italian), limit: max results.
    """
    results = search_restaurants(float(lat), float(lon), cuisine or None, limit)
    if not results:
        return "No restaurants found nearby."
    if results and "error" in results[0]:
        return f"Error fetching restaurants: {results[0]['error']}"
    lines = []
    for r in results:
        line = f"- {r['name']} ({r['cuisine']})"
        if r.get("address"):
            line += f" — {r['address']}"
        if r.get("opening_hours"):
            line += f" | Hours: {r['opening_hours']}"
        lines.append(line)
    return "\n".join(lines)


@tool
def get_food_events_tool(city: str) -> str:
    """
    Get food festivals and culinary events in a city.
    Use when the user asks about food events, festivals, or culinary happenings.
    """
    events = get_food_events(city)
    if not events:
        return f"No food events found for {city}."
    lines = [f"Food events in {city}:"]
    for e in events:
        lines.append(f"- {e['name']} at {e.get('venue', 'TBA')} on {e.get('date', 'TBA')}")
    return "\n".join(lines)


@tool
def get_city_food_culture_tool(city: str) -> str:
    """
    Get cultural food context and cuisine information for a city from Wikipedia.
    Use when the user wants to know about local food culture, traditional dishes, or culinary heritage.
    """
    text = get_city_food_culture(city)
    if not text:
        return f"No food culture info found for {city}."
    return text[:1500]


@tool
def get_trending_dishes_tool(city: str) -> str:
    """
    Get popular recipes and trending dishes associated with a city or its cuisine.
    Use when the user asks what to try, must-eat dishes, or popular local food.
    """
    dishes = get_trending_dishes(city)
    if not dishes:
        return f"No trending dishes found for {city}."
    lines = [f"Trending dishes for {city}:"]
    for d in dishes:
        line = f"- {d['name']}"
        if d.get("rating"):
            line += f" (rating: {d['rating']})"
        if d.get("description"):
            line += f": {d['description'][:80]}..."
        lines.append(line)
    return "\n".join(lines)


@tool
def get_location_name_tool(lat: float, lon: float) -> str:
    """
    Get the real city/place name from latitude and longitude coordinates using reverse geocoding.
    ALWAYS use this first when the user clicks on the globe and the location name looks like
    raw coordinates (e.g. 'Location 48.9°N, 2.3°E'). Returns city, state, and country.
    """
    result = reverse_geocode(float(lat), float(lon))
    if "error" in result:
        return f"Could not identify location: {result['error']}"
    parts = [result.get("city"), result.get("state"), result.get("country")]
    name = ", ".join(p for p in parts if p)
    return f"Location: {name or result.get('display_name', 'Unknown')}"


@tool
def get_local_dishes_tool(lat: float, lon: float, city: str = "") -> str:
    """
    Discover local and traditional dishes for a location. Combines reverse geocoding,
    Wikipedia food culture data, and nearby restaurant cuisine types to identify what
    foods are popular and traditional in the area. Use this to find out what to eat somewhere.
    """
    dishes = get_local_dishes(float(lat), float(lon), city)
    if not dishes:
        return "Could not find local dish information for this location."

    lines = ["Local food discoveries:"]
    wiki_dishes = [d for d in dishes if d.get("source") == "wikipedia"]
    restaurant_cuisines = [d for d in dishes if d.get("source") == "local_restaurants"]

    if wiki_dishes:
        lines.append("\nFrom local food culture:")
        for d in wiki_dishes:
            lines.append(f"  - {d['name']}")

    if restaurant_cuisines:
        lines.append(f"\nPopular cuisine types near {restaurant_cuisines[0].get('city', 'here')}:")
        for d in restaurant_cuisines:
            lines.append(f"  - {d['name']} ({d.get('count', 0)} restaurants)")

    return "\n".join(lines)
