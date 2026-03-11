"""
LangChain agent with OpenAI ChatGPT for food recommendations
"""

import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from tools import (
    search_restaurants_tool,
    get_food_events_tool,
    get_city_food_culture_tool,
    get_trending_dishes_tool,
    get_location_name_tool,
    get_local_dishes_tool,
)

SYSTEM_PROMPT = """You are a world-class food travel guide and culinary expert.

When a user selects a location on the globe, ALWAYS:
1. First use get_location_name_tool to identify the real city/place name from coordinates if the location name looks like raw coordinates.
2. Use get_local_dishes_tool to discover traditional and popular local dishes for that place.
3. Use search_restaurants_tool to find nearby restaurants.
4. Optionally use get_city_food_culture_tool to get cultural context.

Give passionate, opinionated restaurant and food recommendations. Mention specific dish names,
neighborhoods, and local food culture. Use food emojis generously. Always explain WHY each
recommendation is special. Be enthusiastic, specific, and concise."""

TOOLS = [
    search_restaurants_tool,
    get_food_events_tool,
    get_city_food_culture_tool,
    get_trending_dishes_tool,
    get_location_name_tool,
    get_local_dishes_tool,
]

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CHATGPT_API_KEY")
        llm = ChatOpenAI(
            model="gpt-5-mini-2025-08-07",
            api_key=api_key,
            temperature=0.7,
        )
        _agent = create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)
    return _agent


def run_agent(message: str, lat: float, lon: float, location_name: str, preferences: str = "") -> tuple[str, list[str]]:
    """
    Run the agent with location context. Returns (response_text, list of tool names used).
    """
    context = f"User is at {location_name} (lat={lat}, lon={lon}). Use these coordinates when calling tools."
    if preferences:
        context += f" User preferences: {preferences}."
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
