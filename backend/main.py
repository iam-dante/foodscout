"""
FastAPI backend for Smart Food Discovery Agent
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from food import search_restaurants, get_food_events
from agent import run_agent

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
    cuisine: Optional[str] = None


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
        )
    except Exception as e:
        response = f"Sorry, I had trouble processing that request. Please try again. ({type(e).__name__})"
        tools_used = []

    restaurants = search_restaurants(req.lat, req.lon, req.cuisine, limit=10)
    restaurants = [r for r in restaurants if "error" not in r and r.get("name")]

    return ChatResponse(
        response=response,
        tools_used=tools_used,
        restaurants=restaurants,
        type="chat",
    )


@app.get("/food/restaurants")
async def get_restaurants(
    lat: float = Query(...),
    lon: float = Query(...),
    cuisine: Optional[str] = Query(None),
):
    results = search_restaurants(lat, lon, cuisine, limit=20)
    return {"restaurants": results}


@app.get("/food/events")
async def get_events(city: str = Query(...)):
    events = get_food_events(city)
    return {"events": events}


@app.get("/health")
async def health():
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CHATGPT_API_KEY")
    return {"status": "ok", "openai_configured": bool(api_key)}
