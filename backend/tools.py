"""
LangChain tools wrapping food.py functions
"""

from langchain_core.tools import tool

from food import (
    search_restaurants,
    brave_count_restaurants,
    get_city_food_culture,
    get_trending_dishes,
    reverse_geocode,
    get_local_dishes,
    brave_search_food_reviews,
    brave_search_food,
    brave_search_comprehensive,
)


@tool
def search_restaurants_tool(lat: float, lon: float, cuisine: str = "", limit: int = 15) -> str:
    """
    Search for restaurants, cafes, and bars near given coordinates.
    Use this when the user asks about restaurants, places to eat, or food spots in a location.
    We can get the count of restaurants in the area using Brave Search (when available).
    Place-type options: restaurant, cafe, bar, local, fast_food, bakery, pub, bistro, etc.
    lat: latitude, lon: longitude, cuisine: optional filter (e.g. Japanese, Italian, local, cafe), limit: max results.
    """
    lat = float(lat)
    lon = float(lon)
    cuisine_filter = cuisine or None

    results = search_restaurants(lat, lon, cuisine_filter, limit)
    if not results:
        return "No restaurants found nearby."
    if results and "error" in results[0]:
        return f"Error fetching restaurants: {results[0]['error']}"

    brave_count = brave_count_restaurants(lat, lon, cuisine=cuisine_filter)
    lines = []
    if brave_count > 0:
        lines.append(f"Estimated restaurant count in this area (Brave): {brave_count}")
        lines.append("")

    for r in results:
        line = f"- {r['name']} ({r.get('cuisine', 'Various')})"
        if r.get("rating"):
            line += f" ⭐ {r['rating']}"
        if r.get("review_count"):
            line += f" ({r['review_count']} reviews)"
        if r.get("address"):
            line += f" — {r['address']}"
        if r.get("opening_hours"):
            line += f" | Hours: {r['opening_hours']}"
        if r.get("url"):
            line += f" | {r['url']}"
        if r.get("description"):
            line += f" | {r['description'][:100]}"
        lines.append(line)
    return "\n".join(lines)


@tool
def search_food_reviews_tool(city: str, dish_or_restaurant: str = "") -> str:
    """
    Search the web for food reviews in a city, or for a specific dish or restaurant.
    Use when the user asks about reviews, what people say, ratings, or opinions about food in a location.
    city: the city/location name, dish_or_restaurant: optional specific dish or restaurant name.
    """
    results = brave_search_food_reviews(city, dish_or_restaurant)
    if not results:
        return f"No food reviews found for {city}."
    lines = [f"Food reviews for {city}" + (f" - {dish_or_restaurant}" if dish_or_restaurant else "") + ":"]
    for r in results[:8]:
        line = f"- {r['title']}"
        if r.get("description"):
            line += f": {r['description'][:150]}"
        if r.get("url"):
            line += f" ({r['url']})"
        lines.append(line)
    return "\n".join(lines)


@tool
def search_regional_food_tool(city: str, query_extra: str = "") -> str:
    """
    Search the web for regional and local food specialties of a city or area.
    Use when the user asks about what food a region is known for, local specialties, or regional cuisine.
    city: the city/region name, query_extra: optional extra search terms.
    """
    results = brave_search_food(city, query_extra)
    if not results:
        return f"No regional food info found for {city}."
    lines = [f"Regional food of {city}:"]
    for r in results[:8]:
        line = f"- {r['title']}: {r.get('description', '')[:150]}"
        if r.get("url"):
            line += f" ({r['url']})"
        lines.append(line)
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
        if d.get("description"):
            line += f": {d['description'][:100]}"
        if d.get("url"):
            line += f" ({d['url']})"
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
    Wikipedia food culture data, Brave Search, and nearby restaurant cuisine types to identify what
    foods are popular and traditional in the area. Use this to find out what to eat somewhere.
    """
    dishes = get_local_dishes(float(lat), float(lon), city)
    if not dishes:
        return "Could not find local dish information for this location."

    lines = ["Local food discoveries:"]
    wiki_dishes = [d for d in dishes if d.get("source") == "wikipedia"]
    brave_dishes = [d for d in dishes if d.get("source") == "brave_search"]
    restaurant_cuisines = [d for d in dishes if d.get("source") == "local_restaurants"]

    if wiki_dishes:
        lines.append("\nFrom local food culture:")
        for d in wiki_dishes:
            lines.append(f"  - {d['name']}")

    if brave_dishes:
        lines.append("\nFrom web search:")
        for d in brave_dishes:
            line = f"  - {d['name']}"
            if d.get("description"):
                line += f": {d['description'][:100]}"
            lines.append(line)

    if restaurant_cuisines:
        lines.append(f"\nPopular cuisine types near {restaurant_cuisines[0].get('city', 'here')}:")
        for d in restaurant_cuisines:
            lines.append(f"  - {d['name']} ({d.get('count', 0)} restaurants)")

    return "\n".join(lines)


@tool
def brave_search_tool(query: str) -> str:
    """
    Comprehensive web search for food, culture, and travel information.
    Use this for high-level overviews, 'what to do', or general questions about a city's food scene.
    It returns a concise, LLM-powered summary of the top web results.
    """
    return brave_search_comprehensive(query)
