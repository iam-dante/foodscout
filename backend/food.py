"""
Food discovery APIs - Overpass, Wikipedia, Brave Search
"""

import os
import re
from typing import Optional

import httpx

NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WIKIPEDIA_REST = "https://en.wikipedia.org/w/rest.php/v1/page"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_LOCAL_POIS_URL = "https://api.search.brave.com/res/v1/local/pois"
BRAVE_LOCAL_DESC_URL = "https://api.search.brave.com/res/v1/local/descriptions"


def _brave_headers() -> dict:
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return {}
    return {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }


def _brave_web_search(query: str, count: int = 10, extra_snippets: bool = True) -> dict:
    """Run a Brave Web Search and return the raw JSON response."""
    headers = _brave_headers()
    if not headers:
        return {}
    params = {"q": query, "count": min(count, 20)}
    if extra_snippets:
        params["extra_snippets"] = "true"
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(BRAVE_SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {}


def brave_search_food(city: str, query_extra: str = "") -> list[dict]:
    """
    Use Brave Search to find food-related information for a city/region.
    Returns a list of results with title, url, description, and extra_snippets.
    """
    q = f"best local food dishes cuisine {city}"
    if query_extra:
        q += f" {query_extra}"
    data = _brave_web_search(q, count=10)
    results = []
    for r in data.get("web", {}).get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("description", ""),
            "extra_snippets": r.get("extra_snippets", []),
        })
    return results


def brave_search_food_reviews(city: str, dish_or_restaurant: str = "") -> list[dict]:
    """
    Use Brave Search to find food reviews for a city, a specific dish, or a restaurant.
    """
    q = f"food reviews {city}"
    if dish_or_restaurant:
        q += f" {dish_or_restaurant}"
    data = _brave_web_search(q, count=10)
    results = []
    for r in data.get("web", {}).get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("description", ""),
            "extra_snippets": r.get("extra_snippets", []),
        })
    return results


def brave_search_restaurants(
    lat: float,
    lon: float,
    city: str = "",
    cuisine: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Use Brave Search with local enrichments to find restaurants near a location.
    Returns restaurant info with names, addresses, ratings when available.
    Falls back to location-based text search.
    """
    q = f"restaurants near {city}" if city else f"restaurants near {lat},{lon}"
    if cuisine:
        q = f"{cuisine} {q}"

    data = _brave_web_search(q, count=limit)

    locations = data.get("locations", {}).get("results", [])
    if locations:
        return _enrich_brave_locations(locations[:limit])

    results = []
    for r in data.get("web", {}).get("results", []):
        results.append({
            "name": r.get("title", ""),
            "cuisine": cuisine or "Various",
            "address": "",
            "opening_hours": "",
            "lat": lat,
            "lon": lon,
            "description": r.get("description", ""),
            "url": r.get("url", ""),
        })
    return results[:limit]


def _enrich_brave_locations(locations: list[dict]) -> list[dict]:
    """Fetch POI details for Brave local location results."""
    headers = _brave_headers()
    if not headers or not locations:
        return [{
            "name": loc.get("title", "Unknown"),
            "cuisine": "Various",
            "address": "",
            "opening_hours": "",
            "lat": None,
            "lon": None,
        } for loc in locations]

    ids = [loc["id"] for loc in locations if loc.get("id")]
    if not ids:
        return []

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                BRAVE_LOCAL_POIS_URL,
                headers=headers,
                params=[("ids", id_) for id_ in ids[:20]],
            )
            resp.raise_for_status()
            pois_data = resp.json()
    except Exception:
        pois_data = {}

    results = []
    for poi in pois_data.get("results", []):
        results.append({
            "name": poi.get("name", "Unknown"),
            "cuisine": ", ".join(poi.get("categories", [])) or "Various",
            "address": poi.get("address", {}).get("streetAddress", ""),
            "opening_hours": "",
            "lat": poi.get("coordinates", {}).get("latitude"),
            "lon": poi.get("coordinates", {}).get("longitude"),
            "rating": poi.get("rating", {}).get("ratingValue"),
            "review_count": poi.get("rating", {}).get("ratingCount"),
            "phone": poi.get("phone"),
            "url": poi.get("website"),
        })

    if not results:
        for loc in locations:
            results.append({
                "name": loc.get("title", "Unknown"),
                "cuisine": "Various",
                "address": "",
                "opening_hours": "",
                "lat": None,
                "lon": None,
            })

    return results


def search_restaurants(
    lat: float,
    lon: float,
    cuisine: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Find restaurants near coordinates. Tries Brave Search (local enrichments)
    first, then falls back to Overpass API (OpenStreetMap).
    """
    geo = reverse_geocode(lat, lon)
    city = geo.get("city") or geo.get("country") or ""

    brave_results = brave_search_restaurants(lat, lon, city, cuisine, limit)
    if brave_results:
        return brave_results

    radius_m = 2000
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
    Use Brave Search to find food festivals and culinary events in a city.
    """
    q = f"food festivals culinary events {city} 2026"
    data = _brave_web_search(q, count=10)
    events = []
    for r in data.get("web", {}).get("results", []):
        events.append({
            "name": r.get("title", ""),
            "date": r.get("age", "TBA"),
            "venue": "",
            "url": r.get("url", ""),
            "description": r.get("description", ""),
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
    with Wikipedia food culture data, Brave Search results, and Overpass amenity tags.
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

    brave_results = brave_search_food(city)
    for r in brave_results[:5]:
        dishes.append({
            "name": r["title"],
            "source": "brave_search",
            "description": r["description"][:200],
            "url": r["url"],
            "city": city,
        })

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
    Use Brave Search to find trending and popular dishes for a city.
    """
    q = f"trending popular must-try dishes food {city}"
    data = _brave_web_search(q, count=10, extra_snippets=True)
    results = []
    for r in data.get("web", {}).get("results", []):
        results.append({
            "name": r.get("title", ""),
            "description": r.get("description", "")[:200],
            "url": r.get("url", ""),
            "extra_snippets": r.get("extra_snippets", []),
        })
    return results
