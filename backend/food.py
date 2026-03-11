"""
Food discovery APIs - Overpass, Ticketmaster, Wikipedia, Tasty (RapidAPI)
"""

import os
import re
from typing import Optional

import httpx

NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WIKIPEDIA_REST = "https://en.wikipedia.org/w/rest.php/v1/page"
TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
TASTY_URL = "https://tasty.p.rapidapi.com/recipes/list"


def search_restaurants(
    lat: float,
    lon: float,
    cuisine: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Use Overpass API (OpenStreetMap) to find restaurants/cafes/bars near coordinates.
    Free, no API key needed.
    """
    radius_m = 2000  # 2km radius
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="restaurant"](around:{radius_m},{lat},{lon});
      node["amenity"="cafe"](around:{radius_m},{lat},{lon});
      node["amenity"="bar"](around:{radius_m},{lat},{lon});
      node["amenity"="fast_food"](around:{radius_m},{lat},{lon});
    );
    out center {limit};
    """
    try:
        headers = {"User-Agent": "SmartFoodDiscovery/1.0 (Educational; https://github.com)"}
        with httpx.Client(timeout=15) as client:
            resp = client.post(OVERPASS_URL, data={"data": query}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return [{"error": str(e)}]

    results = []
    seen = set()
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand") or "Unnamed"
        key = (name, el.get("lat"), el.get("lon"))
        if key in seen:
            continue
        seen.add(key)

        cuisine_tag = tags.get("cuisine", "")
        if cuisine and cuisine.lower() not in cuisine_tag.lower():
            continue

        results.append({
            "name": name,
            "cuisine": cuisine_tag or "Various",
            "address": tags.get("addr:street", "") or tags.get("address", ""),
            "opening_hours": tags.get("opening_hours", ""),
            "lat": el.get("lat"),
            "lon": el.get("lon"),
        })
        if len(results) >= limit:
            break

    return results


def get_food_events(city: str) -> list[dict]:
    """
    Use Ticketmaster API to find food festivals and culinary events in a city.
    Requires TICKETMASTER_API_KEY in .env
    """
    api_key = os.getenv("TICKETMASTER_API_KEY")
    if not api_key:
        return []

    params = {
        "apikey": api_key,
        "city": city,
        "keyword": "food",
        "size": 10,
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(TICKETMASTER_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    events = []
    emb = data.get("_embedded", {})
    for ev in emb.get("events", []):
        events.append({
            "name": ev.get("name", ""),
            "date": ev.get("dates", {}).get("start", {}).get("localDate", ""),
            "venue": ev.get("_embedded", {}).get("venues", [{}])[0].get("name", ""),
            "url": ev.get("url", ""),
        })
    return events


def get_city_food_culture(city: str) -> str:
    """
    Use Wikipedia REST API to fetch cuisine/culture section of a city's page.
    Free, no API key needed.
    """
    titles = [f"{city}", f"{city} cuisine", f"Cuisine of {city}"]
    headers = {"User-Agent": "SmartFoodDiscovery/1.0 (Educational)"}
    base = "https://en.wikipedia.org/w/rest.php/v1/page"

    for title in titles:
        try:
            slug = title.replace(" ", "_")
            url = f"{base}/{slug}/html"
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue
                html = resp.text
        except Exception:
            continue

        if not html or len(html) < 200:
            continue

        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()[:4000]

        patterns = [
            r"(?i)(cuisine|food|gastronomy|culinary)[\s\S]{0,500}",
            r"(?i)(local dishes?|traditional food|street food)[\s\S]{0,300}",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                snippet = m.group(0)[:800].strip()
                if len(snippet) > 100:
                    return snippet

        if len(text) > 200:
            return text[:800].strip()

    return ""


def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Use Nominatim reverse geocoding to get the place name from coordinates.
    Free, no API key needed.
    """
    headers = {"User-Agent": "SmartFoodDiscovery/1.0 (Educational)"}
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(NOMINATIM_REVERSE, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {"error": str(e)}

    address = data.get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or ""
    )
    state = address.get("state", "")
    country = address.get("country", "")
    display_name = data.get("display_name", "")

    return {
        "city": city,
        "state": state,
        "country": country,
        "display_name": display_name,
        "full_address": address,
    }


def get_local_dishes(lat: float, lon: float, city: str = "") -> list[dict]:
    """
    Discover local/traditional dishes for a location by combining reverse geocoding
    with Wikipedia food culture data and Overpass amenity tags.
    """
    if not city:
        geo = reverse_geocode(lat, lon)
        city = geo.get("city") or geo.get("country") or "Unknown"

    culture_text = get_city_food_culture(city)

    dishes = []
    food_keywords = re.findall(
        r"(?:traditional|local|popular|famous|signature|classic|must-try)[\s\w]*(?:dish|food|cuisine|meal|plate|recipe|specialty)[\w\s,]*",
        culture_text,
        re.IGNORECASE,
    )
    for kw in food_keywords[:5]:
        dishes.append({"name": kw.strip(), "source": "wikipedia", "city": city})

    restaurants = search_restaurants(lat, lon, limit=10)
    cuisine_counts: dict[str, int] = {}
    for r in restaurants:
        if "error" not in r:
            c = r.get("cuisine", "Various")
            for tag in c.split(";"):
                tag = tag.strip()
                if tag and tag != "Various":
                    cuisine_counts[tag] = cuisine_counts.get(tag, 0) + 1

    top_cuisines = sorted(cuisine_counts.items(), key=lambda x: -x[1])[:5]
    for cuisine_name, count in top_cuisines:
        dishes.append({
            "name": cuisine_name,
            "source": "local_restaurants",
            "count": count,
            "city": city,
        })

    return dishes


def get_trending_dishes(city: str) -> list[dict]:
    """
    Use Tasty API via RapidAPI to get popular recipes/dishes.
    Requires RAPIDAPI_KEY in .env
    """
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return []

    # Map city to cuisine keywords for Tasty
    city_cuisines = {
        "tokyo": "japanese ramen sushi",
        "paris": "french croissant",
        "mexico city": "mexican tacos",
        "new york": "pizza bagel",
        "rome": "italian pasta",
        "london": "british fish chips",
        "bangkok": "thai pad thai",
        "seoul": "korean kimchi",
    }
    query = city_cuisines.get(city.lower(), city)

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "tasty.p.rapidapi.com",
    }
    params = {"from": "0", "size": "8", "q": query}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(TASTY_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for r in data.get("results", [])[:8]:
        results.append({
            "name": r.get("name", ""),
            "description": r.get("description", "")[:150],
            "rating": r.get("user_rating", {}).get("score"),
        })
    return results
