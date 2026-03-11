"""
LangChain agent with OpenAI ChatGPT for food recommendations
"""

import os

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from tools import (
    search_restaurants_tool,
    search_food_reviews_tool,
    search_regional_food_tool,
    get_city_food_culture_tool,
    get_trending_dishes_tool,
    get_location_name_tool,
    get_local_dishes_tool,
    brave_search_tool,
)

SYSTEM_PROMPT = """You are a world-class food travel guide and culinary expert.

ABSOLUTE HARD LIMIT: Your final response to the user MUST be 50 words or fewer. Count carefully. If your draft exceeds 50 words, cut it down before responding. This is non-negotiable.

When a user selects a location on the globe, ALWAYS:
1. First use get_location_name_tool to identify the real city/place name from coordinates if the location name looks like raw coordinates.
2. Use brave_search_tool for an easy and fast overview of the local food scene.
3. Use get_local_dishes_tool to discover traditional and popular local dishes.
4. Use search_restaurants_tool to find specific nearby restaurants.

When the user asks for a comprehensive overview or a SPECIFIC restaurant/dish:
- ALWAYS prioritize brave_search_tool to get fast, high-quality context and 'what makes it special' summaries from the web.

When the user asks about reviews:
- Use search_food_reviews_tool.

Response format: Use short bullet points or 1–2 sentences max. Include dish names, ratings, and key highlights. Use food emojis. NEVER exceed 50 words — this is your most important constraint."""

TOOLS = [
    search_restaurants_tool,
    search_food_reviews_tool,
    search_regional_food_tool,
    get_city_food_culture_tool,
    get_trending_dishes_tool,
    get_location_name_tool,
    get_local_dishes_tool,
    brave_search_tool,
]

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        api_key = os.getenv("GROQ_API_KEY")
        llm = ChatGroq(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            api_key=api_key,
            temperature=0.7,
        )
        _agent = create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)
    return _agent


def run_agent(
    message: str,
    lat: float,
    lon: float,
    location_name: str,
    preferences: str = "",
    restaurant_yelp_id: str | None = None,
) -> tuple[str, list[str]]:
    """
    Run the agent with location context. Returns (response_text, list of tool names used).
    """
    context = f"User is at {location_name} (lat={lat}, lon={lon}). Use these coordinates when calling tools."
    if preferences:
        context += f" User preferences: {preferences}."
    if restaurant_yelp_id:
        context += f" User is asking about a SPECIFIC restaurant: {restaurant_yelp_id}. Use search_food_reviews_tool with the restaurant name to find reviews."
    full_input = f"{context}\n\nUser question: {message}"

    agent = get_agent()
    result = agent.invoke({"messages": [("user", full_input)]})

    messages = result.get("messages", [])

    output = "I couldn't find recommendations for that location."
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai" and msg.content and not getattr(msg, "tool_calls", None):
            output = msg.content
            break

    tools_used = []
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name and name not in tools_used:
                tools_used.append(name)

    return output, tools_used


async def run_agent_stream(
    message: str,
    lat: float,
    lon: float,
    location_name: str,
    preferences: str = "",
    restaurant_yelp_id: str | None = None,
):
    """
    Stream agent response token-by-token. Yields (event_type, data) tuples:
    - ("token", str) for each text chunk
    - ("done", {"tools_used": [...], "full_response": "..."}) when complete
    """
    context = f"User is at {location_name} (lat={lat}, lon={lon}). Use these coordinates when calling tools."
    if preferences:
        context += f" User preferences: {preferences}."
    if restaurant_yelp_id:
        context += f" User is asking about a SPECIFIC restaurant: {restaurant_yelp_id}. Use search_food_reviews_tool with the restaurant name to find reviews."
    full_input = f"{context}\n\nUser question: {message}"

    agent = get_agent()
    tools_used = []
    full_response = ""

    def extract_text(msg):
        if not hasattr(msg, "content") or not msg.content:
            return ""
        if isinstance(msg.content, str):
            return msg.content
        if isinstance(msg.content, list):
            return "".join(getattr(c, "text", c) if hasattr(c, "text") else str(c) for c in msg.content)
        return str(msg.content)

    def collect_tools(msgs):
        names = []
        for m in msgs:
            for tc in getattr(m, "tool_calls", None) or []:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                if name and name not in names:
                    names.append(name)
        return names

    try:
        async for event in agent.astream(
            {"messages": [("user", full_input)]},
            stream_mode=["messages", "values"],
        ):
            if isinstance(event, tuple) and len(event) == 2:
                mode, data = event
                if mode == "messages":
                    for item in (data if isinstance(data, list) else [data]):
                        msg = item[0] if isinstance(item, tuple) else item
                        text = extract_text(msg)
                        if text:
                            full_response += text
                            yield ("token", text)
                elif mode == "values":
                    msgs = data.get("messages", []) if isinstance(data, dict) else []
                    tools_used = collect_tools(msgs) or tools_used
            else:
                for item in (event if isinstance(event, list) else [event]):
                    msg = item[0] if isinstance(item, tuple) else item
                    text = extract_text(msg)
                    if text:
                        full_response += text
                        yield ("token", text)

        if not full_response:
            full_response = "I couldn't find recommendations for that location."
    except Exception:
        full_response = "Sorry, I had trouble processing that request. Please try again."

    yield ("done", {"tools_used": tools_used, "full_response": full_response})
