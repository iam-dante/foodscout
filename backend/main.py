"""
FastAPI backend for Smart Food Discovery Agent
"""

import json
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from food import search_restaurants, brave_search_food_reviews
from agent import run_agent, run_agent_stream

app = FastAPI(title="Smart Food Discovery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    lat: float
    lon: float
    location_name: str
    message: str
    preferences: Optional[str] = ""
    restaurant_yelp_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    tools_used: list[str]
    restaurants: list[dict]
    type: str = "chat"


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        response, tools_used = run_agent(
            req.message,
            req.lat,
            req.lon,
            req.location_name,
            req.preferences or "",
            restaurant_yelp_id=req.restaurant_yelp_id,
        )
    except Exception as e:
        response = f"Sorry, I had trouble processing that request. Please try again. ({type(e).__name__})"
        tools_used = []

    restaurants = search_restaurants(req.lat, req.lon, limit=20)
    restaurants = [r for r in restaurants if "error" not in r and r.get("name")]

    return ChatResponse(
        response=response,
        tools_used=tools_used,
        restaurants=restaurants,
        type="chat",
    )


async def chat_stream_generator(req: ChatRequest):
    """SSE generator for streaming chat responses."""
    restaurants = search_restaurants(req.lat, req.lon, limit=20)
    restaurants = [r for r in restaurants if "error" not in r and r.get("name")]

    try:
        async for event_type, data in run_agent_stream(
            req.message,
            req.lat,
            req.lon,
            req.location_name,
            req.preferences or "",
            restaurant_yelp_id=req.restaurant_yelp_id,
        ):
            if event_type == "token":
                yield f"data: {json.dumps({'type': 'token', 'content': data})}\n\n"
            elif event_type == "done":
                yield f"data: {json.dumps({'type': 'done', 'tools_used': data['tools_used'], 'full_response': data.get('full_response', ''), 'restaurants': restaurants})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream chat response as Server-Sent Events."""
    return StreamingResponse(
        chat_stream_generator(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/food/restaurants")
async def get_restaurants(
    lat: float = Query(...),
    lon: float = Query(...),
):
    results = search_restaurants(lat, lon, limit=20)
    return {"restaurants": results}





@app.get("/food/reviews")
async def get_food_reviews(
    city: str = Query(...),
    dish_or_restaurant: Optional[str] = Query(None),
):
    """Search for food reviews using Brave Search."""
    reviews = brave_search_food_reviews(city, dish_or_restaurant or "")
    return {"reviews": reviews}


@app.get("/health")
async def health():
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CHATGPT_API_KEY")
    return {"status": "ok", "openai_configured": bool(api_key)}
